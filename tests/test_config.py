from __future__ import annotations

import importlib

import config


CONFIG_ENV_VARS = (
    "AUTOLEKTOR_VOICE",
    "AUTOLEKTOR_WHISPER_MODEL",
    "AUTOLEKTOR_TRANSCRIPTION_LANGUAGE",
    "AUTOLEKTOR_NORMALIZE_WHITESPACE",
    "AUTOLEKTOR_VIDEO_CODEC",
    "AUTOLEKTOR_AUDIO_CODEC",
)


def reload_config(monkeypatch):
    for name in CONFIG_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    return importlib.reload(config)


def test_config_defaults(monkeypatch) -> None:
    loaded = reload_config(monkeypatch)

    assert loaded.VOICE == "pl-PL-ZofiaNeural"
    assert loaded.WHISPER_MODEL == "large-v3"
    assert loaded.TRANSCRIPTION_LANGUAGE == "pl"
    assert loaded.NORMALIZE_WHITESPACE is False
    assert loaded.VIDEO_CODEC == "libx264"
    assert loaded.AUDIO_CODEC == "aac"


def test_config_reads_environment_overrides(monkeypatch) -> None:
    for name in CONFIG_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AUTOLEKTOR_VOICE", "  en-US-AvaNeural  ")
    monkeypatch.setenv("AUTOLEKTOR_WHISPER_MODEL", "small")
    monkeypatch.setenv("AUTOLEKTOR_TRANSCRIPTION_LANGUAGE", "en")
    monkeypatch.setenv("AUTOLEKTOR_NORMALIZE_WHITESPACE", "true")
    monkeypatch.setenv("AUTOLEKTOR_VIDEO_CODEC", "libx265")
    monkeypatch.setenv("AUTOLEKTOR_AUDIO_CODEC", "libopus")

    loaded = importlib.reload(config)

    assert loaded.VOICE == "en-US-AvaNeural"
    assert loaded.WHISPER_MODEL == "small"
    assert loaded.TRANSCRIPTION_LANGUAGE == "en"
    assert loaded.NORMALIZE_WHITESPACE is True
    assert loaded.VIDEO_CODEC == "libx265"
    assert loaded.AUDIO_CODEC == "libopus"
    reload_config(monkeypatch)


def test_config_bool_false_values(monkeypatch) -> None:
    for name in CONFIG_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AUTOLEKTOR_NORMALIZE_WHITESPACE", "0")

    loaded = importlib.reload(config)

    assert loaded.NORMALIZE_WHITESPACE is False
    reload_config(monkeypatch)
