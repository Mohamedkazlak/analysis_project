from __future__ import annotations

import logging

import httpx

from core.config import settings


logger = logging.getLogger(__name__)


class SpeechServiceError(RuntimeError):
    """
    Raised when an STT or TTS provider fails.
    """


# ============================================================
# SPEECH TO TEXT
# Groq Whisper
# ============================================================

async def transcribe_audio(
    audio: bytes,
    filename: str,
    content_type: str,
) -> str:
    """
    Convert recorded audio into text.

    Provider:
        Groq

    Model:
        whisper-large-v3-turbo

    Arabic / English:
        Automatic detection when STT_LANGUAGE is empty.
    """

    if not settings.STT_BASE_URL:
        raise SpeechServiceError(
            "STT_BASE_URL is not configured"
        )

    if not settings.STT_API_KEY:
        raise SpeechServiceError(
            "STT_API_KEY is not configured"
        )

    if not settings.STT_MODEL:
        raise SpeechServiceError(
            "STT_MODEL is not configured"
        )

    if not audio:
        raise SpeechServiceError(
            "Audio input is empty"
        )

    url = (
        f"{settings.STT_BASE_URL.rstrip('/')}"
        "/audio/transcriptions"
    )

    headers = {
        "Authorization":
            f"Bearer {settings.STT_API_KEY}",
    }

    files = {
        "file": (
            filename,
            audio,
            content_type or "audio/webm",
        ),
    }

    data = {
        "model": settings.STT_MODEL,
        "response_format": "json",
        "temperature": "0",
    }

    #
    # Leave STT_LANGUAGE empty to allow Whisper
    # to automatically detect Arabic or English.
    #
    configured_language = (
        settings.STT_LANGUAGE.strip()
    )

    if (
        configured_language
        and configured_language.lower()
        != "auto"
    ):
        data["language"] = (
            configured_language
        )

    logger.info(
        "STT request model=%s file=%s bytes=%d",
        settings.STT_MODEL,
        filename,
        len(audio),
    )

    try:

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=20.0,
                read=120.0,
                write=120.0,
                pool=20.0,
            )
        ) as client:

            response = await client.post(
                url,
                headers=headers,
                files=files,
                data=data,
            )

    except httpx.TimeoutException as exc:

        logger.exception(
            "STT request timed out"
        )

        raise SpeechServiceError(
            "Speech recognition timed out"
        ) from exc

    except httpx.RequestError as exc:

        logger.exception(
            "STT connection failed"
        )

        raise SpeechServiceError(
            f"Speech recognition connection failed: {exc}"
        ) from exc

    if not response.is_success:

        logger.error(
            "STT upstream error "
            "status=%s body=%s",
            response.status_code,
            response.text[:1000],
        )

        raise SpeechServiceError(
            "Speech recognition returned "
            f"HTTP {response.status_code}"
        )

    try:
        payload = response.json()

    except ValueError as exc:

        raise SpeechServiceError(
            "Speech recognition returned invalid JSON"
        ) from exc

    text = payload.get("text")

    if not isinstance(
        text,
        str,
    ):
        raise SpeechServiceError(
            "Speech recognition returned invalid text"
        )

    text = text.strip()

    if not text:
        raise SpeechServiceError(
            "Speech recognition returned empty text"
        )

    logger.info(
        "STT success characters=%d",
        len(text),
    )

    return text


# ============================================================
# TEXT TO SPEECH
# ElevenLabs
# ============================================================

async def synthesize_speech(
    text: str,
    requested_language: str = "auto",
) -> tuple[bytes, str]:
    """
    Convert answer text into speech.

    Provider:
        ElevenLabs

    Model:
        eleven_multilingual_v2

    Voice:
        Sarah / configured TTS_VOICE_ID

    The returned value is the actual MP3 bytes.
    No public audio URL is used.
    """

    clean_text = text.strip()

    if not clean_text:
        raise SpeechServiceError(
            "TTS text is empty"
        )

    if not settings.TTS_BASE_URL:
        raise SpeechServiceError(
            "TTS_BASE_URL is not configured"
        )

    if not settings.TTS_API_KEY:
        raise SpeechServiceError(
            "TTS_API_KEY is not configured"
        )

    if not settings.TTS_MODEL:
        raise SpeechServiceError(
            "TTS_MODEL is not configured"
        )

    if not settings.TTS_VOICE_ID:
        raise SpeechServiceError(
            "TTS_VOICE_ID is not configured"
        )

    #
    # eleven_multilingual_v2 detects the language
    # from the supplied text.
    #
    # requested_language is deliberately retained
    # for API compatibility with the BNU router.
    #
    if requested_language not in {
        "auto",
        "ar",
        "en",
    }:
        raise SpeechServiceError(
            f"Unsupported TTS language: "
            f"{requested_language}"
        )

    url = (
        f"{settings.TTS_BASE_URL.rstrip('/')}"
        f"/text-to-speech/"
        f"{settings.TTS_VOICE_ID}"
    )

    params = {
        "output_format":
            settings.TTS_OUTPUT_FORMAT,
    }

    headers = {
        "xi-api-key":
            settings.TTS_API_KEY,

        "Content-Type":
            "application/json",

        "Accept":
            "audio/mpeg",
    }

    payload = {
        "text": clean_text,

        "model_id":
            settings.TTS_MODEL,

        #
        # Optional per-request tuning.
        #
        "voice_settings": {
            "stability": 0.50,
            "similarity_boost": 0.75,
            "style": 0.0,
            "use_speaker_boost": True,
        },
    }

    logger.info(
        "TTS request "
        "model=%s voice=%s chars=%d",
        settings.TTS_MODEL,
        settings.TTS_VOICE_ID,
        len(clean_text),
    )

    try:

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=20.0,
                read=settings.TTS_TIMEOUT_SECONDS,
                write=30.0,
                pool=20.0,
            )
        ) as client:

            response = await client.post(
                url,
                params=params,
                headers=headers,
                json=payload,
            )

    except httpx.TimeoutException as exc:

        logger.exception(
            "ElevenLabs TTS timed out"
        )

        raise SpeechServiceError(
            "Text-to-speech timed out"
        ) from exc

    except httpx.RequestError as exc:

        logger.exception(
            "ElevenLabs connection failed"
        )

        raise SpeechServiceError(
            "Text-to-speech connection failed: "
            f"{exc}"
        ) from exc

    if not response.is_success:

        logger.error(
            "ElevenLabs TTS error "
            "status=%s body=%s",
            response.status_code,
            response.text[:1000],
        )

        if response.status_code == 401:
            raise SpeechServiceError(
                "ElevenLabs API key is invalid"
            )

        if response.status_code == 402:
            raise SpeechServiceError(
                "ElevenLabs account has insufficient credits"
            )

        if response.status_code == 429:
            raise SpeechServiceError(
                "ElevenLabs rate limit exceeded"
            )

        raise SpeechServiceError(
            "Text-to-speech returned "
            f"HTTP {response.status_code}"
        )

    audio = response.content

    if not audio:
        raise SpeechServiceError(
            "ElevenLabs returned empty audio"
        )

    logger.info(
        "TTS success bytes=%d",
        len(audio),
    )

    return (
        audio,
        "audio/mpeg",
    )