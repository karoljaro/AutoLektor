# syntax=docker/dockerfile:1.7

# Build variants:
#   CPU (default): docker build -t autolektor-api .
#   NVIDIA CUDA:  docker build --build-arg TORCH_FLAVOR=cu130 -t autolektor-api:cuda .
#
# Docker build does not reliably have access to the host GPU. Select the
# PyTorch build explicitly; at runtime PyTorch/Whisper detects whether an
# exposed NVIDIA GPU is available.

ARG PYTHON_VERSION=3.14
ARG TORCH_VERSION=2.12.1
ARG TORCH_FLAVOR=cpu

FROM python:${PYTHON_VERSION}-slim-trixie AS builder

ARG TORCH_VERSION
ARG TORCH_FLAVOR

ENV VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:${PATH}" \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore

WORKDIR /build

RUN python -m venv "${VIRTUAL_ENV}"

COPY requirements.txt ./requirements.txt

RUN --mount=type=cache,target=/root/.cache/pip <<'BUILD'
set -eu

case "${TORCH_FLAVOR}" in
    cpu|cu130)
        ;;
    *)
        echo >&2 "Unsupported TORCH_FLAVOR=${TORCH_FLAVOR}. Use: cpu or cu130."
        exit 2
        ;;
esac

# Tests do not belong in the production image. Whisper is installed separately
# so the selected PyTorch build cannot be replaced by dependency resolution.
grep -Eiv '^[[:space:]]*(pytest|openai-whisper)([<>=!~]|[[:space:]])' \
    requirements.txt > /tmp/app-requirements.txt

WHISPER_SPEC="$(
    grep -Ei '^[[:space:]]*openai-whisper([<>=!~]|[[:space:]])' requirements.txt \
        | head -n 1 \
        | tr -d '[:space:]'
)"
test -n "${WHISPER_SPEC}"

python -m pip install --upgrade pip setuptools wheel

TORCH_INDEX_URL="https://download.pytorch.org/whl/${TORCH_FLAVOR}"
TORCH_SPEC="torch==${TORCH_VERSION}+${TORCH_FLAVOR}"

if [ "${TORCH_FLAVOR}" = "cpu" ]; then
    # Install the exact CPU wheel without CUDA/NVIDIA dependencies.
    python -m pip install \
        --no-deps \
        --only-binary=:all: \
        --index-url "${TORCH_INDEX_URL}" \
        "${TORCH_SPEC}"

    # Install ordinary Torch dependencies, deliberately omitting packages used
    # only by CUDA builds.
    python - <<'PY' > /tmp/torch-requirements.txt
from importlib.metadata import requires

for requirement in requires("torch") or ():
    plain = requirement.split(";", 1)[0].strip().lower()
    if "extra ==" in requirement.lower():
        continue
    if plain.startswith(("nvidia-", "cuda-", "triton")):
        continue
    print(requirement)
PY

    python -m pip install -r /tmp/torch-requirements.txt
    python -m pip install -r /tmp/app-requirements.txt

    # Whisper's Triton path is CUDA-only. The CPU image uses its CPU fallback,
    # so omitting Triton avoids a large, unnecessary package.
    python -m pip install --no-deps "${WHISPER_SPEC}"

    python - <<'PY' > /tmp/whisper-requirements.txt
from importlib.metadata import requires

for requirement in requires("openai-whisper") or ():
    plain = requirement.split(";", 1)[0].strip().lower()
    if "extra ==" in requirement.lower():
        continue
    if plain.startswith(("torch", "triton")):
        continue
    print(requirement)
PY

    python -m pip install --no-warn-conflicts -r /tmp/whisper-requirements.txt
else
    # Install one precise CUDA build. PyTorch pulls the matching CUDA 13.0
    # runtime components only; it does not install every CUDA version.
    python -m pip install \
        --only-binary=:all: \
        --index-url "${TORCH_INDEX_URL}" \
        "${TORCH_SPEC}"

    python -m pip install -r /tmp/app-requirements.txt
    python -m pip install "${WHISPER_SPEC}"
    python -m pip check
fi

TORCH_FLAVOR="${TORCH_FLAVOR}" python - <<'PY'
from importlib.metadata import distributions
import os

import edge_tts  # noqa: F401
import fastapi  # noqa: F401
import torch
import whisper

flavor = os.environ["TORCH_FLAVOR"]
cuda = torch.version.cuda

if flavor == "cpu":
    if cuda is not None:
        raise RuntimeError(f"Expected CPU-only PyTorch, got CUDA {cuda}")

    forbidden = sorted(
        name
        for distribution in distributions()
        if (name := (distribution.metadata.get("Name") or "").lower()).startswith(
            ("nvidia-", "cuda-")
        )
    )
    if forbidden:
        raise RuntimeError(f"Unexpected CUDA packages: {', '.join(forbidden)}")
else:
    expected = flavor.removeprefix("cu")
    actual = (cuda or "").replace(".", "")
    if actual != expected:
        raise RuntimeError(
            f"Expected PyTorch {flavor}, got torch.version.cuda={cuda!r}"
        )

print(
    "Validated image dependencies: "
    f"torch={torch.__version__}, cuda={cuda}, whisper={whisper.__version__}"
)
PY
BUILD


FROM python:${PYTHON_VERSION}-slim-trixie AS runtime

ARG TORCH_VERSION
ARG TORCH_FLAVOR

ENV VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    HOME=/home/autolektor \
    XDG_CACHE_HOME=/home/autolektor/.cache \
    NUMBA_CACHE_DIR=/home/autolektor/.cache/numba \
    TMPDIR=/tmp/autolektor \
    AUTOLEKTOR_TORCH_FLAVOR="${TORCH_FLAVOR}" \
    AUTOLEKTOR_TORCH_VERSION="${TORCH_VERSION}"

RUN export DEBIAN_FRONTEND=noninteractive \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        ffmpeg \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 10001 autolektor \
    && useradd \
        --uid 10001 \
        --gid 10001 \
        --create-home \
        --home-dir /home/autolektor \
        --shell /usr/sbin/nologin \
        autolektor \
    && mkdir -p \
        /home/autolektor/.cache/whisper \
        /home/autolektor/.cache/numba \
        /tmp/autolektor \
    && chown -R 10001:10001 /home/autolektor /tmp/autolektor

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app

# Copy all top-level Python modules. This includes logger.py and prevents
# future local modules from being accidentally omitted from the image.
COPY --chown=10001:10001 *.py ./
COPY --chown=10001:10001 helpers/ ./helpers/
COPY --chown=10001:10001 providers/ ./providers/
COPY --chown=10001:10001 services/ ./services/

# Fail during the build if an application module or local import is missing.
RUN python -c "import api; print('Application import OK')"

USER 10001:10001

EXPOSE 8000
STOPSIGNAL SIGTERM

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).read()" || exit 1

# One worker is intentional: each worker may load a separate Whisper model.
CMD ["python", "-m", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
