# AutoLektor

Python tool for generating Polish voiceover, subtitles and video variants from a source video and text input.

AutoLektor automates a simple video post-production workflow: it generates a text-to-speech voiceover, creates subtitles from the generated audio and renders multiple output video variants.

## Features

- Generate Polish voiceover from text using `edge-tts`
- Automatically adjust voiceover speed to match the source video duration
- Generate subtitles from voiceover audio using Whisper
- Render multiple video variants:
  - dubbed video with subtitles
  - dubbed video without subtitles
  - original video with subtitles
- Modular project structure with providers and services
- Preflight checks, logging and automated tests

## Tech Stack

- Python
- edge-tts
- OpenAI Whisper
- FFmpeg / FFprobe
- pytest

## How It Works

```text
Input video + text file
        ↓
Generate voiceover with edge-tts
        ↓
Adjust voiceover speed if needed
        ↓
Generate subtitles with Whisper
        ↓
Render video variants with FFmpeg
        ↓
Output: video files, audio track and subtitles
```

## Installation

### Prerequisites

- Python 3.14 recommended
- FFmpeg and FFprobe installed system-wide
- pip

### Setup

```bash
git clone https://github.com/karoljaro/AutoLektor.git
cd AutoLektor

python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

## Configuration

Edit `config.py` to configure:

- input video path
- input text file path
- output file names
- TTS voice
- Whisper model
- transcription language

By default, the project is configured for Polish voiceover and subtitles.

## Usage

### 1. Prepare input files

Place the source video in the project root:

```text
wideo_angielskie.mp4
```

Place the text file in the `Video/` directory:

```text
Video/tekst.txt
```

### 2. Run the script

```bash
python main.py
```

## Output Files

After processing, the project generates:

```text
1_wideo_lektor_napisy.mp4    # dubbed video with subtitles
2_wideo_tylko_lektor.mp4     # dubbed video only
3_wideo_tylko_napisy.mp4     # original audio with subtitles
Video/lektor_pl.mp3          # generated voiceover
Video/lektor_pl.srt          # generated subtitles
```

## Project Structure

```text
AutoLektor/
├── main.py                  # Entry point and orchestration
├── config.py                # Project configuration
├── logger.py                # Logging setup
├── helpers/                 # File, time and duration utilities
├── providers/               # Wrappers for TTS, Whisper and FFmpeg
├── services/                # Voiceover, subtitle and video logic
├── tests/                   # Automated tests
└── Video/                   # Working directory
```

For more details, see [`ARCHITECTURE.md`](./ARCHITECTURE.md).

## Tests

Run the test suite:

```bash
pytest
```

The tests are mocked and do not require FFmpeg, Whisper models or network access.

## Notes

- Video rendering time depends on the source video length and selected output variant.
- Whisper models are downloaded on first use and cached locally.
- The project is currently optimized for Polish voiceover and subtitles, but other languages can be configured in `config.py`.

## License

MIT

## Author

Karol Jaroń
