"""HTTP smoke test for the AutoLektor FastAPI app.

Generates a tiny test MP4, starts Uvicorn, calls the API through real HTTP,
and verifies returned media files. By default it checks the lightweight
variants that avoid Whisper downloads/inference.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEXT = "To jest krotki test lektora przez API."


@dataclass(frozen=True)
class VariantCheck:
    name: str
    output_name: str
    expected_content_type: str
    requires_whisper: bool = False


VARIANTS = {
    "voiceover": VariantCheck("voiceover", "voiceover.mp3", "audio/mpeg"),
    "dubbed": VariantCheck("dubbed", "dubbed.mp4", "video/mp4"),
    "subtitles": VariantCheck("subtitles", "subtitles.srt", "application/x-subrip", requires_whisper=True),
    "subtitled": VariantCheck("subtitled", "subtitled.mp4", "video/mp4", requires_whisper=True),
    "full": VariantCheck("full", "full.mp4", "video/mp4", requires_whisper=True),
}


def run(command: list[str], *, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, check=True, capture_output=True, text=True)


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def make_test_video(path: Path, duration: int) -> None:
    run([
        "ffmpeg",
        "-hide_banner",
        "-nostdin",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c=black:s=320x180:d={duration}",
        "-f",
        "lavfi",
        "-i",
        "anullsrc=channel_layout=mono:sample_rate=44100",
        "-shortest",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        str(path),
    ])


def media_duration(path: Path) -> float:
    result = run([
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(path),
    ])
    return float(result.stdout.strip())


def multipart_body(fields: dict[str, str], files: dict[str, tuple[str, str, bytes]]) -> tuple[bytes, str]:
    boundary = f"autolektor-{uuid.uuid4().hex}"
    chunks: list[bytes] = []

    for name, value in fields.items():
        chunks.extend([
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
            value.encode(),
            b"\r\n",
        ])

    for name, (filename, content_type, content) in files.items():
        chunks.extend([
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode(),
            f"Content-Type: {content_type}\r\n\r\n".encode(),
            content,
            b"\r\n",
        ])

    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def request_json(url: str, timeout: float = 1.0) -> dict[str, object]:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def post_render(base_url: str, variant: str, video_path: Path, text_path: Path, output_path: Path) -> str:
    body, content_type = multipart_body(
        fields={"variant": variant},
        files={
            "video": ("input.mp4", "video/mp4", video_path.read_bytes()),
            "text_file": ("text.txt", "text/plain", text_path.read_bytes()),
        },
    )
    request = urllib.request.Request(
        f"{base_url}/render",
        data=body,
        method="POST",
        headers={"Content-Type": content_type},
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            output_path.write_bytes(response.read())
            return response.headers.get("content-type", "")
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"/render {variant} failed with HTTP {exc.code}: {details}") from exc


def wait_for_health(base_url: str, timeout_seconds: float) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            payload = request_json(f"{base_url}/health")
            if payload == {"status": "ok"}:
                return
            last_error = RuntimeError(f"unexpected health payload: {payload}")
        except Exception as exc:  # noqa: BLE001 - keep startup polling simple
            last_error = exc
        time.sleep(0.25)
    raise RuntimeError(f"API did not become healthy: {last_error}")


@contextlib.contextmanager
def uvicorn_server(port: int, log_path: Path):
    with log_path.open("w", encoding="utf-8") as log_file:
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "api:app", "--host", "127.0.0.1", "--port", str(port)],
            cwd=ROOT,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
        )
    try:
        yield process
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)


def selected_variants(names: list[str], include_whisper: bool) -> list[VariantCheck]:
    selected = [VARIANTS[name] for name in names]
    blocked = [variant.name for variant in selected if variant.requires_whisper and not include_whisper]
    if blocked:
        joined = ", ".join(blocked)
        raise SystemExit(f"Variants require --include-whisper: {joined}")
    return selected


def main() -> int:
    parser = argparse.ArgumentParser(description="Run HTTP smoke tests against the AutoLektor API.")
    parser.add_argument("--variant", action="append", choices=sorted(VARIANTS), help="Variant to test. Can be repeated.")
    parser.add_argument("--include-whisper", action="store_true", help="Allow variants that run Whisper.")
    parser.add_argument("--duration", type=int, default=3, help="Generated test video duration in seconds.")
    parser.add_argument("--work-dir", type=Path, default=None, help="Directory for generated smoke-test files.")
    args = parser.parse_args()

    variant_names = args.variant or ["voiceover", "dubbed"]
    checks = selected_variants(variant_names, args.include_whisper)

    work_dir = args.work_dir or Path(tempfile.mkdtemp(prefix="autolektor-smoke-"))
    work_dir.mkdir(parents=True, exist_ok=True)
    video_path = work_dir / "input.mp4"
    text_path = work_dir / "text.txt"
    log_path = work_dir / "server.log"

    text_path.write_text(DEFAULT_TEXT, encoding="utf-8")
    make_test_video(video_path, args.duration)

    port = free_port()
    base_url = f"http://127.0.0.1:{port}"
    print(f"[smoke] work_dir={work_dir}")
    print(f"[smoke] start={base_url}")

    with uvicorn_server(port, log_path):
        wait_for_health(base_url, timeout_seconds=15)
        print("[smoke] health=ok")

        for check in checks:
            output_path = work_dir / check.output_name
            content_type = post_render(base_url, check.name, video_path, text_path, output_path)
            if check.expected_content_type not in content_type:
                raise RuntimeError(
                    f"{check.name}: expected content-type {check.expected_content_type}, got {content_type}"
                )
            if output_path.stat().st_size <= 0:
                raise RuntimeError(f"{check.name}: empty output file")
            if output_path.suffix in {".mp3", ".mp4"}:
                duration = media_duration(output_path)
                if duration <= 0:
                    raise RuntimeError(f"{check.name}: non-positive media duration {duration}")
                print(f"[smoke] {check.name}=ok path={output_path} duration={duration:.3f}s")
            else:
                print(f"[smoke] {check.name}=ok path={output_path} size={output_path.stat().st_size}B")

    print(f"[smoke] server_log={log_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
