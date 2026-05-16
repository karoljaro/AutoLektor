# Video Automation - Auto-Dubbed & Subtitled Video Generator

Refactored version with clean, modular architecture.

## Features

- 🎤 Automatic text-to-speech voiceover generation (Polish)
- ⏱️ Auto-adjust voiceover speed to match video duration
- 📝 Automatic subtitle generation from voiceover
- 🎬 Generate 3 video variants:
    1. **Dubbed with subtitles** (Polish voiceover + Polish subtitles)
    2. **Dubbed only** (Polish voiceover, no subtitles)
    3. **Subtitles only** (Original audio + Polish subtitles)

## Installation

### Prerequisites

- Python 3.14 (recommended)
- FFmpeg and FFprobe installed on your system
- pipenv or pip

### Setup

```bash
# Clone or navigate to project
cd AutoLektor

# Create virtual environment
python -m venv .venv

# Activate virtual environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Configuration

Edit `config.py` to customize:

- Input text file path
- Output file names
- Voice settings
- Whisper model (base, small, medium, large)

## Usage

### Prepare Input

1. Place your source video in the project root:
   ```
   wideo_angielskie.mp4
   ```

2. Place your text file in the Video/ folder:
   ```
   Video/tekst.txt
   ```

### Run the Script

```bash
python main.py
```

### Process Steps

```
[STEP 0/3] Load text from file
           ↓
[STEP 1/3] Generate and auto-adjust voiceover
           ├─ Generate audio with edge-tts
           ├─ Measure durations
           └─ Auto-speed if needed
           ↓
[STEP 2/3] Generate subtitles
           ├─ Transcribe with Whisper
           └─ Save SRT file
           ↓
[STEP 3/3] Render video variants
           ├─ Variant 1: Dubbed + Subtitles (longest)
           ├─ Variant 2: Dubbed only (fast)
           └─ Variant 3: Subtitles only
           ↓
Output files: 1_*, 2_*, 3_*
```

## Output Files

After running, you'll get:

- `1_wideo_lektor_napisy.mp4` - Dubbed with Polish subtitles
- `2_wideo_tylko_lektor.mp4` - Dubbed only
- `3_wideo_tylko_napisy.mp4` - Subtitles only
- `Video/lektor_pl.mp3` - Generated audio track
- `Video/lektor_pl.srt` - Generated subtitle file

## Project Structure

See `ARCHITECTURE.md` for detailed architecture documentation.

```
AutoLektor/
├── main.py                  # Entry point & orchestration
├── config.py                # Configuration
├── helpers/                 # Utilities (file, time, duration)
├── providers/               # Library wrappers (TTS, Whisper, FFmpeg)
├── services/                # Business logic (voiceover, subtitles, video)
└── Video/                   # Working directory
```

## Extending the Project

### Add a New Provider

Example: Adding Google Cloud TTS

```python
# providers/google_tts_provider.py
class GoogleTTSProvider:
    def __init__(self, credentials_path):
        self.credentials = load_credentials(credentials_path)

    async def generate_voiceover(self, text, output_path):
        # Implementation
        pass
```

Then swap in a service:

```python
tts_provider = GoogleTTSProvider(credentials_path)
voiceover_service = VoiceoverService(tts_provider)
```

### Add a New Service

No need to modify existing code - just create a new service and use it in `main()`.

## Supported Languages

Currently configured for Polish (pl), but you can modify:

- `VOICE` in `config.py` for other TTS voices
- `TRANSCRIPTION_LANGUAGE` for subtitle generation
- All voices supported by edge-tts and Whisper

## Performance Tips

1. **Use smaller Whisper model** for faster subtitle generation:
   ```python
   WHISPER_MODEL = "tiny"  # or "base" (default)
   ```

2. **Run with faster-whisper** for better performance:
    - Install: `pip install faster-whisper`
    - Modify `providers/whisper_provider.py`

3. **Video rendering can be slow** - be patient with Variant 1

## Troubleshooting

| Issue                       | Solution                           |
|-----------------------------|------------------------------------|
| ffmpeg/ffprobe not found    | Install FFmpeg system-wide         |
| Audio file not found        | Check `config.py` paths            |
| Whisper model download slow | Models are cached after first use  |
| Subtitle timing off         | Check audio file duration vs video |

## Dependencies

- `edge-tts` - Text-to-speech
- `openai-whisper` - Speech-to-text
- `ffmpeg-python` - Video operations (via subprocess)

See `requirements.txt` for exact versions.

## License

MIT (or your preferred license)

## Author

Video Automation Project

---

**Documentation**: See `ARCHITECTURE.md` for technical details.

