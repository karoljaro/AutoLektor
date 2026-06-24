# AutoLektor

AutoLektor generates voiceover, subtitles and rendered video variants from a source MP4 file and text.

The project currently has two entry points:

- HTTP API for n8n and integrations: `api.py`
- simple terminal CLI: `main.py`

Both entry points use the shared render pipeline from `pipeline.py`.

## Features

- Generate a voiceover from text using `edge-tts`
- Adjust voiceover speed to fit the source video duration
- Generate SRT subtitles from the generated voiceover using Whisper
- Render one selected output variant per request or CLI call
- Use the source video FPS when burning subtitles into video
- Return stable business errors from the API for n8n workflows

## Output Variants

| Variant | Output | Description |
| --- | --- | --- |
| `voiceover` | `voiceover.mp3` | Generated voiceover only |
| `subtitles` | `subtitles.srt` | Generated subtitles only |
| `dubbed` | `dubbed.mp4` | Source video with generated voiceover |
| `subtitled` | `subtitled.mp4` | Source video with original audio and burned subtitles |
| `full` | `full.mp4` | Source video with generated voiceover and burned subtitles |

## Requirements

- Python 3.14
- FFmpeg and FFprobe available on `PATH`
- pip

Install Python dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configuration

`config.py` contains project defaults only:

- `VOICE`
- `WHISPER_MODEL`
- `TRANSCRIPTION_LANGUAGE`
- `NORMALIZE_WHITESPACE`
- `VIDEO_CODEC`
- `AUDIO_CODEC`

Input video paths, text paths and output paths are passed through the API or CLI. They are not configured in `config.py`.

## CLI Usage

Basic call with a text file:

```bash
.venv/bin/python main.py input.mp4 --text-file text.txt --variant full -o output.mp4
```

Inline text:

```bash
.venv/bin/python main.py input.mp4 --text "Text for voiceover and subtitles" --variant voiceover
```

Optional voice and subtitle language:

```bash
.venv/bin/python main.py input.mp4 --text-file text.txt --variant subtitles --language en
```

CLI contract:

- `video`: source MP4 path
- `--text` or `--text-file`: exactly one text input is required
- `--variant`: required, one of `voiceover`, `subtitles`, `dubbed`, `subtitled`, `full`
- `-o/--output`: optional output path
- `--voice`: optional `edge-tts` voice override
- `--language`: optional Whisper transcription language override

If `-o/--output` is not provided, the result is saved next to the input video:

```text
input_voiceover.mp3
input_subtitles.srt
input_dubbed.mp4
input_subtitled.mp4
input_full.mp4
```

Relative paths are resolved from the current working directory where the command is run.

You can also expose the CLI through your shell `PATH` with a small wrapper or executable script. In that setup the command can be run from any directory, and relative input/output paths still resolve from the directory where you started the command.

## API Usage

Start the API:

```bash
.venv/bin/python -m uvicorn api:app --host 127.0.0.1 --port 8000
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

Render with inline text:

```bash
curl -X POST http://127.0.0.1:8000/render \
  -F "video=@input.mp4;type=video/mp4" \
  -F "text=Text for voiceover and subtitles" \
  -F "variant=full" \
  --output full.mp4
```

Render with a text file:

```bash
curl -X POST http://127.0.0.1:8000/render \
  -F "video=@input.mp4;type=video/mp4" \
  -F "text_file=@text.txt;type=text/plain" \
  -F "variant=voiceover" \
  --output voiceover.mp3
```

Optional API form fields:

- `voice`: overrides `config.VOICE`
- `language`: overrides `config.TRANSCRIPTION_LANGUAGE`

Text rule: provide exactly one of `text` or `text_file`.

Video upload rules:

- expected MP4 by `.mp4` suffix or `video/mp4` content type
- empty uploads are rejected
- upload size limit is `500 MiB`

API business errors return JSON shaped for n8n:

```json
{
  "error": "ERROR_NAME",
  "detail": "human readable detail",
  "stage": "input|upload|voiceover|subtitles|video_render",
  "retryable": false
}
```

## Smoke Test

Run lightweight HTTP smoke tests for `voiceover` and `dubbed`:

```bash
.venv/bin/python scripts/smoke_http.py
```

Run all variants, including Whisper-based variants:

```bash
.venv/bin/python scripts/smoke_http.py --include-whisper --all-variants
```

## Tests

Run the unit test suite:

```bash
.venv/bin/python -m pytest
```

The unit tests mock TTS, Whisper and FFmpeg-heavy work where appropriate.

## Project Structure

```text
AutoLektor/
├── api.py                  # FastAPI app and HTTP request handling
├── main.py                 # CLI entry point
├── pipeline.py             # Shared render pipeline and variant contract
├── config.py               # Project defaults
├── exceptions.py           # Domain errors for API/n8n
├── helpers/                # File, duration, time and preflight helpers
├── providers/              # edge-tts, Whisper and FFmpeg wrappers
├── services/               # Voiceover, subtitle and legacy video services
├── scripts/                # Smoke-test helpers
├── tests/                  # Automated tests
└── example/                # Local ignored examples
```

For more details, see [`ARCHITECTURE.md`](./ARCHITECTURE.md).

## Notes

- Whisper models are downloaded on first use and cached by Whisper.
- Rendering time depends on video length, selected variant and Whisper model size.
- `example/` is ignored by git and can be used for local sample files.

## License

MIT

## Author

Karol Jaroń
