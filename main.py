import asyncio
import math
import os
import subprocess
import warnings

import edge_tts
import whisper

# Suppress non-essential warnings
warnings.filterwarnings("ignore")

# ==========================================
# 1. VARIABLE CONFIGURATION
# ==========================================


# Text input file used by the script
TEXT_FILE = "tekst.txt"

VOICE = "pl-PL-ZofiaNeural"  # or "pl-PL-ZofiaNeural"

# Working and output file names
POLISH_AUDIO_FILE = "lektor_pl.mp3"
SOURCE_VIDEO = "wideo_angielskie.mp4"  # Remember to rename it to your own file!

VIDEO_DUBBED_WITH_SUBTITLES = "1_wideo_lektor_napisy.mp4"
VIDEO_DUBBED_ONLY = "2_wideo_tylko_lektor.mp4"
VIDEO_SUBTITLES_ONLY = "3_wideo_tylko_napisy.mp4"


# ==========================================
# 2. HELPER FUNCTIONS
# ==========================================

def get_duration(file_path):
    """Use system ffprobe to measure file duration in seconds."""
    command = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        file_path
    ]
    result = subprocess.run(command, stdout=subprocess.PIPE, text=True, check=True)
    return float(result.stdout.strip())


def read_text_from_file(file_name):
    print(f"\n[STEP 0/3] Loading text from file {file_name}...")
    if not os.path.exists(file_name):
        print(f"-> [ERROR] File not found: {file_name}!")
        return None

    with open(file_name, "r", encoding="utf-8") as file_handle:
        text = file_handle.read()

    # Magic roller: remove unnecessary tabs, repeated spaces, and line breaks
    text = " ".join(text.split())

    if not text:
        print(f"-> [ERROR] File {file_name} is empty!")
        return None

    print("-> Text loaded and cleaned up from whitespace.")
    return text


async def create_voiceover(text):
    print(f"\n[STEP 1/3] Generating the base voiceover ({VOICE})...")
    # Generate the voice at normal speed (trial version)
    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(POLISH_AUDIO_FILE)

    # Measure the duration of the video and generated audio
    video_duration = get_duration(SOURCE_VIDEO)
    audio_duration = get_duration(POLISH_AUDIO_FILE)

    print(f"-> Video duration: {video_duration:.2f} s")
    print(f"-> Audio duration: {audio_duration:.2f} s")

    # If the voiceover runs longer than the video, calculate and fix it
    if audio_duration > video_duration:
        ratio = audio_duration / video_duration
        # math.ceil rounds up, e.g. 12.1% -> 13% (gives a safety margin)
        percent = math.ceil((ratio - 1) * 100)

        print(f"-> [ACTION] Audio is too long! Speeding up the voiceover automatically by +{percent}%...")

        new_rate = f"+{percent}%"
        fast_communicate = edge_tts.Communicate(text, VOICE, rate=new_rate)
        await fast_communicate.save(POLISH_AUDIO_FILE)  # Overwrite the old file with the new one
        print(f"-> Saved adjusted, sped-up version: {POLISH_AUDIO_FILE}")
    else:
        print("-> Audio fits within the video duration. Speed unchanged.")


def create_subtitles():
    print("\n[STEP 2/3] Generating SRT subtitles from the voice track...")
    model = whisper.load_model("base")
    result = model.transcribe(POLISH_AUDIO_FILE, language="pl")

    # Our own reliable time formatting function for subtitles
    def format_time(seconds):
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        # Format as e.g. 00:00:03,500
        return f"{hours:02d}:{minutes:02d}:{secs:06.3f}".replace(".", ",")

    print("-> Saving the SRT file...")

    # Manually create and save the SRT file to avoid library issues
    with open("lektor_pl.srt", "w", encoding="utf-8") as srt_file:
        # Whisper stores each sentence in the "segments" list
        for i, segment in enumerate(result["segments"], start=1):
            start = format_time(segment["start"])
            end = format_time(segment["end"])
            text = segment["text"].strip()

            # Write the SRT entry
            srt_file.write(f"{i}\n{start} --> {end}\n{text}\n\n")

    print("-> Saved: lektor_pl.srt")


def merge_videos():
    print("\n[STEP 3/3] Rendering three video variants (FFmpeg)...")
    subtitles_file = "lektor_pl.srt"

    if not os.path.exists(SOURCE_VIDEO):
        print(f"-> [ERROR] Video not found: {SOURCE_VIDEO}")
        return

    # VARIANT 1: Voiceover + Subtitles (our standard version)
    print("-> Rendering Variant 1: Voiceover + Subtitles (this will take the longest)...")
    full_command = [
        "ffmpeg", "-y",
        "-i", SOURCE_VIDEO,
        "-i", POLISH_AUDIO_FILE,
        "-map", "0:v:0",  # Video from original
        "-map", "1:a:0",  # Audio from the Polish voiceover
        "-vf", f"fps=30,subtitles={subtitles_file}",  # Stabilize fps and add subtitles
        "-c:v", "libx264",
        "-c:a", "aac",
        VIDEO_DUBBED_WITH_SUBTITLES
    ]

    # VARIANT 2: Voiceover only, no subtitles
    print("-> Rendering Variant 2: Voiceover only (very fast!)...")
    voiceover_only_command = [
        "ffmpeg", "-y",
        "-i", SOURCE_VIDEO,
        "-i", POLISH_AUDIO_FILE,
        "-map", "0:v:0",  # Video from original
        "-map", "1:a:0",  # Audio from the Polish voiceover
        "-c:v", "copy",  # Copy the video 1:1, no rendering!
        "-c:a", "aac",
        VIDEO_DUBBED_ONLY
    ]

    # VARIANT 3: Subtitles only (original English audio + Polish subtitles)
    print("-> Rendering Variant 3: Subtitles only with the original audio...")
    subtitles_only_command = [
        "ffmpeg", "-y",
        "-i", SOURCE_VIDEO,
        "-map", "0:v:0",  # Video from original
        "-map", "0:a:0",  # Audio from the original (English)
        "-vf", f"fps=30,subtitles={subtitles_file}",  # Subtitles
        "-c:v", "libx264",
        "-c:a", "copy",  # Copy the original audio without quality loss
        VIDEO_SUBTITLES_ONLY
    ]

    # Run all three commands one after another
    try:
        subprocess.run(full_command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"   [DONE] {VIDEO_DUBBED_WITH_SUBTITLES}")

        subprocess.run(voiceover_only_command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"   [DONE] {VIDEO_DUBBED_ONLY}")

        subprocess.run(subtitles_only_command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"   [DONE] {VIDEO_SUBTITLES_ONLY}")

        print("\n[SUCCESS] All 3 video variants have been generated!")
    except subprocess.CalledProcessError as e:
        print(f"\n[FFmpeg ERROR] Something went wrong while merging the files: {e}")


# ==========================================
# 3. MAIN FLOW
# ==========================================

async def main():
    print("=== VIDEO AUTOMATION START ===")

    # Try to load text from file
    loaded_text = read_text_from_file(TEXT_FILE)

    # If the file does not exist or is empty, stop
    if not loaded_text:
        print("=== PROCESS STOPPED ===")
        return

    # If the text was loaded, continue the magic
    await create_voiceover(loaded_text)
    create_subtitles()
    merge_videos()

    print("=== END ===")


# Run the script
if __name__ == "__main__":
    asyncio.run(main())
