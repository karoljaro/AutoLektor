# AutoLektor Architecture

AutoLektor has two entry points and one shared render pipeline:

- `api.py`: FastAPI adapter for n8n and HTTP integrations
- `main.py`: simple `argparse` CLI adapter
- `pipeline.py`: shared variant contract and rendering orchestration

The adapters are responsible for input/output concerns. The pipeline is responsible for deciding which media steps are needed for a selected variant.

## Project Structure

```text
AutoLektor/
├── api.py                  # FastAPI app, upload handling and HTTP responses
├── main.py                 # CLI parser, path normalization and exit codes
├── pipeline.py             # Shared render pipeline and variant definitions
├── config.py               # Project defaults only
├── exceptions.py           # Domain errors exposed by the API
├── logger.py               # Logging setup
├── helpers/                # File, duration, time and preflight helpers
├── providers/              # External tool/library wrappers
├── services/               # Voiceover/subtitle business services
├── scripts/                # Smoke-test helpers
├── tests/                  # Automated tests
└── example/                # Ignored local sample files
```

## Entry Points

### API Adapter: `api.py`

The API exposes:

- `GET /health`
- `POST /render`

`POST /render` accepts `multipart/form-data`:

- `video`: uploaded MP4 video
- `text` or `text_file`: exactly one text input
- `variant`: render variant
- `voice`: optional `edge-tts` voice override
- `language`: optional Whisper language override

Responsibilities:

- validate text input rules
- validate basic video upload constraints
- save upload into a temporary workspace
- validate the saved file has a readable video stream through `ffprobe`
- call `pipeline.render_variant(...)`
- return the generated file as `FileResponse`
- clean the temporary workspace after response or error
- expose expected failures as stable JSON errors for n8n

The API does not own rendering logic. It delegates rendering to `pipeline.py`.

### CLI Adapter: `main.py`

The CLI uses standard-library `argparse`.

Required inputs:

- source `video` path
- exactly one of `--text` or `--text-file`
- `--variant`

Optional inputs:

- `-o/--output`
- `--voice`
- `--language`

Responsibilities:

- parse terminal arguments
- resolve relative paths from the current working directory
- calculate default output paths as `<input_stem>_<variant>.<ext>`
- run local preflight checks for `ffmpeg`, `ffprobe`, source video and text file
- call `pipeline.render_variant(...)`
- return exit code `0` on success and `1` on runtime failure

The CLI can be exposed through `PATH` with a wrapper or executable script. Relative paths still resolve from the directory where the command is started.

## Shared Pipeline

`pipeline.py` defines the variant contract:

| Variant | Output | Internal steps |
| --- | --- | --- |
| `voiceover` | MP3 | voiceover |
| `subtitles` | SRT | voiceover, subtitles |
| `dubbed` | MP4 | voiceover, video render |
| `subtitled` | MP4 | voiceover, subtitles, video render |
| `full` | MP4 | voiceover, subtitles, video render |

Core API:

```python
async def render_variant(
    *,
    text: str,
    source_video: Path,
    output_path: Path,
    variant: str,
    work_dir: Path,
    voice: str | None = None,
    language: str | None = None,
) -> Path:
    ...
```

Responsibilities:

- trim and validate text
- resolve the selected `VariantSpec`
- create needed parent directories
- create voiceover through `VoiceoverService`
- create subtitles through `SubtitleService` when required
- create MP4 output through `FFmpegProvider` when required
- map provider/service failures to domain errors

The caller owns workspace lifetime:

- API keeps the workspace until `FileResponse` finishes
- CLI uses `TemporaryDirectory`

## Configuration

`config.py` contains project defaults only:

- `VOICE`
- `WHISPER_MODEL`
- `TRANSCRIPTION_LANGUAGE`
- `NORMALIZE_WHITESPACE`
- `VIDEO_CODEC`
- `AUDIO_CODEC`

Input video paths, input text paths and output paths are not configuration. They come from the API request or CLI arguments.

FPS is not configured. For video variants with burned subtitles, `FFmpegProvider` reads the source video FPS through `ffprobe`.

## Services

### `VoiceoverService`

Generates voiceover through a TTS provider and adjusts speech speed when the generated audio is longer than the source video.

Inputs:

- text
- source video path
- output audio path

Dependencies:

- `TTSProvider`
- `helpers.duration_helpers.get_duration`

### `SubtitleService`

Generates SRT subtitles from generated voiceover audio.

Inputs:

- audio path
- output SRT path
- transcription language

Dependencies:

- `WhisperProvider`
- `helpers.time_helpers.format_time`

## Providers

Providers wrap external tools and libraries:

- `TTSProvider`: `edge-tts`
- `WhisperProvider`: OpenAI Whisper
- `FFmpegProvider`: `ffmpeg` and `ffprobe`

`FFmpegProvider` behavior:

- `dubbed`: copies the source video stream and replaces audio
- `subtitled`: burns subtitles into source video and keeps original audio
- `full`: burns subtitles and replaces audio with generated voiceover
- subtitle-burning variants detect FPS from the source file through `ffprobe`

## Error Boundaries

`exceptions.py` defines domain errors used by API responses and pipeline wrapping.

Expected API error response shape:

```json
{
  "error": "ERROR_NAME",
  "detail": "human readable detail",
  "stage": "input|upload|voiceover|subtitles|video_render",
  "retryable": false
}
```

Main stages:

- `input`
- `upload`
- `voiceover`
- `subtitles`
- `video_render`

The API hides low-level provider details from HTTP responses. The CLI currently logs runtime failures and exits with code `1`.

## Data Flow

### API Flow

```text
HTTP multipart request
        ↓
api.resolve_text_input
        ↓
api.validate_video_upload
        ↓
api.save_upload into temp workspace
        ↓
pipeline.render_variant
        ↓
FileResponse
        ↓
BackgroundTask cleanup
```

### CLI Flow

```text
Terminal arguments
        ↓
main.parse_args
        ↓
path normalization and preflight checks
        ↓
main.resolve_cli_text
        ↓
TemporaryDirectory workspace
        ↓
pipeline.render_variant
        ↓
output file path
```

### Pipeline Flow

```text
text + source video + variant
        ↓
VoiceoverService -> TTSProvider
        ↓
SubtitleService -> WhisperProvider       optional
        ↓
FFmpegProvider -> ffmpeg/ffprobe          optional
        ↓
selected output file
```

## Tests

Test coverage is split by boundary:

- `tests/test_api.py`: HTTP adapter contract, upload validation and domain errors
- `tests/test_main.py`: CLI parser, path resolution and pipeline call
- `tests/test_pipeline.py`: variant orchestration without real TTS/Whisper/FFmpeg
- `tests/test_providers.py`: provider command construction and FPS detection
- `tests/test_services.py`: service behavior
- `tests/test_helpers.py`: helpers
- `tests/test_preflight.py`: command/path preflight behavior

Run:

```bash
.venv/bin/python -m pytest
```

## Smoke Tests

HTTP smoke tests live in `scripts/smoke_http.py`.

Default lightweight check:

```bash
.venv/bin/python scripts/smoke_http.py
```

Full variant check:

```bash
.venv/bin/python scripts/smoke_http.py --include-whisper --all-variants
```

The full check can download/load Whisper models and is slower.
