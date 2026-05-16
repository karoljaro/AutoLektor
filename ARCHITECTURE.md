# Video Automation Project - Architecture

## Project Structure

```
AutoLektor/
├── main.py                      # Orchestration entry point
├── config.py                    # Centralized configuration
├── helpers/                     # Helper utilities
│   ├── __init__.py             # File operations (read_text_from_file)
│   ├── time_helpers.py         # Time formatting (format_time)
│   └── duration_helpers.py     # Media duration (get_duration)
├── providers/                   # External library wrappers
│   ├── __init__.py             # TTS Provider (edge-tts wrapper)
│   ├── whisper_provider.py     # Speech-to-text (Whisper wrapper)
│   └── ffmpeg_provider.py      # Video operations (FFmpeg wrapper)
├── services/                    # Business logic layer
│   ├── __init__.py             # Voiceover Service
│   ├── subtitle_service.py     # Subtitle generation logic
│   └── video_service.py        # Video rendering logic
└── Video/                       # Working directory
    ├── tekst.txt               # Input text
    ├── lektor_pl.mp3           # Generated audio
    └── lektor_pl.srt           # Generated subtitles
```

## Architecture Layers

### 1. **Config Layer** (`config.py`)
- Centralized configuration management
- All constants and settings in one place
- Easy to maintain and modify

### 2. **Helper Layer** (`helpers/`)
- **file_helpers.py**: Text file operations
- **time_helpers.py**: SRT time format conversion
- **duration_helpers.py**: Media file duration measurement

### 3. **Provider Layer** (`providers/`)
Wraps external libraries with clear interfaces:
- **TTSProvider**: Edge-TTS text-to-speech
- **WhisperProvider**: OpenAI Whisper speech-to-text
- **FFmpegProvider**: FFmpeg video operations

### 4. **Service Layer** (`services/`)
Orchestrates business logic:
- **VoiceoverService**: Generates and auto-adjusts voiceover speed
- **SubtitleService**: Generates SRT subtitles from audio
- **VideoService**: Renders 3 video variants

### 5. **Main Layer** (`main.py`)
- Initializes all services and providers
- Orchestrates the workflow
- Minimal business logic

## Data Flow

```
Input Text File
        ↓
[STEP 0] read_text_from_file (helpers)
        ↓
[STEP 1] VoiceoverService → TTSProvider
        ├─ Generate audio
        ├─ Check duration
        └─ Auto-adjust speed if needed
        ↓
[STEP 2] SubtitleService → WhisperProvider
        ├─ Transcribe audio
        └─ Generate SRT file
        ↓
[STEP 3] VideoService → FFmpegProvider
        ├─ Render Variant 1: Voiceover + Subtitles
        ├─ Render Variant 2: Voiceover only
        └─ Render Variant 3: Subtitles only
        ↓
Output: 3 Video Files
```

## Design Patterns

### Dependency Injection
Services receive providers as dependencies:
```python
voiceover_service = VoiceoverService(tts_provider)
subtitle_service = SubtitleService(whisper_provider)
```

### Separation of Concerns
- Providers: Handle library-specific details
- Services: Contain business logic
- Helpers: Provide utility functions
- Config: Manage all constants
- Main: Orchestrate the workflow

### Single Responsibility Principle
Each class/module has one clear purpose:
- `TTSProvider` → wraps TTS
- `VoiceoverService` → manages voiceover generation and speed adjustment
- `file_helpers` → file operations

## How to Extend

### Add a new provider:
1. Create `providers/new_provider.py`
2. Define a class with clear methods
3. Import and use in services

### Add a new service:
1. Create `services/new_service.py`
2. Use providers as dependencies
3. Implement business logic
4. Import in `main.py`

### Add configuration:
1. Add constants to `config.py`
2. Import where needed

## Testing

Each layer can be tested independently:
- **Helpers**: Unit tests for utility functions
- **Providers**: Mock external libraries
- **Services**: Integration tests with providers
- **Main**: End-to-end tests

## Benefits of This Structure

✓ **Maintainability**: Easy to find and modify code  
✓ **Testability**: Each layer can be tested independently  
✓ **Extensibility**: Easy to add new providers/services  
✓ **Reusability**: Services can be reused in different contexts  
✓ **Clarity**: Clear separation of concerns  
✓ **Scalability**: Easy to add new features without breaking existing code

