# Docker Commands

This file keeps ready-to-use build and run commands for the AutoLektor API
image. The image contains AutoLektor only. n8n should use it as an external API
image from another repository or deployment.

## Build Arguments

Supported Dockerfile build arguments:

| Argument | Default | Values |
| --- | --- | --- |
| `PYTHON_VERSION` | `3.14` | Python image version available on Docker Hub |
| `TORCH_VERSION` | `2.12.1` | PyTorch version available in the selected PyTorch wheel index |
| `TORCH_FLAVOR` | `cpu` | `cpu`, `cu130` |

`TORCH_FLAVOR=cpu` builds a CPU-only image and avoids CUDA packages.
`TORCH_FLAVOR=cu130` builds an NVIDIA CUDA 13.0 image.

## Docker Build

Default CPU image:

```bash
docker build -t autolektor-api:cpu .
```

CPU image with all project build arguments shown explicitly:

```bash
docker build \
  --build-arg PYTHON_VERSION=3.14 \
  --build-arg TORCH_VERSION=2.12.1 \
  --build-arg TORCH_FLAVOR=cpu \
  -t autolektor-api:cpu \
  .
```

GPU image:

```bash
docker build \
  --build-arg TORCH_FLAVOR=cu130 \
  -t autolektor-api:gpu \
  .
```

GPU image with all project build arguments shown explicitly:

```bash
docker build \
  --build-arg PYTHON_VERSION=3.14 \
  --build-arg TORCH_VERSION=2.12.1 \
  --build-arg TORCH_FLAVOR=cu130 \
  -t autolektor-api:gpu \
  .
```

Rebuild without Docker cache:

```bash
docker build --no-cache -t autolektor-api:cpu .
```

## Podman Build

Use Docker image format if the image `HEALTHCHECK` should be preserved.

CPU image:

```bash
podman build --format docker -t autolektor-api:cpu .
```

GPU image:

```bash
podman build \
  --format docker \
  --build-arg TORCH_FLAVOR=cu130 \
  -t autolektor-api:gpu \
  .
```

## Runtime Environment

Supported application environment variables:

| Variable | Default | Meaning |
| --- | --- | --- |
| `AUTOLEKTOR_VOICE` | `pl-PL-ZofiaNeural` | edge-tts voice |
| `AUTOLEKTOR_WHISPER_MODEL` | `large-v3` | Whisper model name |
| `AUTOLEKTOR_TRANSCRIPTION_LANGUAGE` | `pl` | transcription language |
| `AUTOLEKTOR_NORMALIZE_WHITESPACE` | `false` | collapse text whitespace before TTS |
| `AUTOLEKTOR_VIDEO_CODEC` | `libx264` | ffmpeg video codec |
| `AUTOLEKTOR_AUDIO_CODEC` | `aac` | ffmpeg audio codec |

Useful image/runtime paths:

| Path | Purpose |
| --- | --- |
| `/home/autolektor/.cache/whisper` | Whisper model cache |
| `/home/autolektor/.cache/numba` | Numba cache |
| `/tmp/autolektor` | temporary files |

## Docker Run

Default CPU run:

```bash
docker run --rm -p 8000:8000 autolektor-api:cpu
```

CPU run with persistent Whisper cache:

```bash
docker run --rm \
  -p 8000:8000 \
  -v autolektor-whisper:/home/autolektor/.cache/whisper \
  autolektor-api:cpu
```

CPU run with all project runtime options shown explicitly:

```bash
docker run --rm \
  --name autolektor-api \
  -p 8000:8000 \
  -e AUTOLEKTOR_VOICE=pl-PL-ZofiaNeural \
  -e AUTOLEKTOR_WHISPER_MODEL=large-v3 \
  -e AUTOLEKTOR_TRANSCRIPTION_LANGUAGE=pl \
  -e AUTOLEKTOR_NORMALIZE_WHITESPACE=false \
  -e AUTOLEKTOR_VIDEO_CODEC=libx264 \
  -e AUTOLEKTOR_AUDIO_CODEC=aac \
  -v autolektor-whisper:/home/autolektor/.cache/whisper \
  autolektor-api:cpu
```

GPU run:

The GPU image contains the selected CUDA PyTorch runtime, but it does not
replace the host NVIDIA driver. The host where this image runs must have a
working NVIDIA driver and container GPU support, for example Docker with NVIDIA
Container Toolkit or an equivalent Podman/NVIDIA CDI setup.

```bash
docker run --rm \
  --gpus all \
  -p 8000:8000 \
  -v autolektor-whisper:/home/autolektor/.cache/whisper \
  autolektor-api:gpu
```

GPU run with all project runtime options shown explicitly:

```bash
docker run --rm \
  --name autolektor-api \
  --gpus all \
  -p 8000:8000 \
  -e AUTOLEKTOR_VOICE=pl-PL-ZofiaNeural \
  -e AUTOLEKTOR_WHISPER_MODEL=large-v3 \
  -e AUTOLEKTOR_TRANSCRIPTION_LANGUAGE=pl \
  -e AUTOLEKTOR_NORMALIZE_WHITESPACE=false \
  -e AUTOLEKTOR_VIDEO_CODEC=libx264 \
  -e AUTOLEKTOR_AUDIO_CODEC=aac \
  -v autolektor-whisper:/home/autolektor/.cache/whisper \
  autolektor-api:gpu
```

Run with a smaller Whisper model for quicker tests:

```bash
docker run --rm \
  -p 8000:8000 \
  -e AUTOLEKTOR_WHISPER_MODEL=small \
  -v autolektor-whisper:/home/autolektor/.cache/whisper \
  autolektor-api:cpu
```

## Podman Run

With Podman, add `:U` to the volume mount when the non-root container user
needs ownership remapping.

CPU run:

```bash
podman run --rm \
  -p 8000:8000 \
  -v autolektor-whisper:/home/autolektor/.cache/whisper:U \
  autolektor-api:cpu
```

GPU run example:

```bash
podman run --rm \
  --device nvidia.com/gpu=all \
  -p 8000:8000 \
  -v autolektor-whisper:/home/autolektor/.cache/whisper:U \
  autolektor-api:gpu
```

## Health Check

Check the API after the container starts:

```bash
curl http://127.0.0.1:8000/health
```

Expected response:

```json
{"status":"ok"}
```

## Notes

- The container listens on port `8000`.
- The image runs as non-root user `autolektor` with UID/GID `10001`.
- One `uvicorn` worker is intentional because each worker can load a separate
  Whisper model.
- The first Whisper-based request can download the selected model into the
  mounted Whisper cache.
