from typing import Literal

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
)

from fastapi.responses import Response
from pydantic import BaseModel

from core.dependencies import get_live_user
from schemas.auth import UserContext

from services.speech import (
    SpeechServiceError,
    synthesize_speech,
    transcribe_audio,
)


router = APIRouter(
    prefix="/api/speech",
    tags=["speech"],
)


# ============================================================
# Limits
# ============================================================

MAX_AUDIO_BYTES = (
    15 * 1024 * 1024
)

MAX_TTS_CHARACTERS = 4000


ALLOWED_AUDIO_TYPES = {
    "audio/webm",
    "audio/wav",
    "audio/x-wav",
    "audio/mpeg",
    "audio/mp3",
    "audio/mp4",
    "audio/m4a",
    "audio/x-m4a",
    "audio/ogg",
}


# ============================================================
# Schemas
# ============================================================

class TranscriptionResponse(
    BaseModel
):
    text: str


class SpeechRequest(
    BaseModel
):
    text: str

    language: Literal[
        "auto",
        "ar",
        "en",
    ] = "auto"


# ============================================================
# VOICE -> TEXT
# ============================================================

@router.post(
    "/transcribe",
    response_model=TranscriptionResponse,
)
async def transcribe(
    file: UploadFile = File(...),

    ctx: UserContext = Depends(
        get_live_user
    ),
):
    """
    Browser audio
        ↓
    BNU Backend
        ↓
    Groq Whisper
        ↓
    Text
    """

    #
    # Authentication and role verification
    # have already been performed.
    #
    del ctx

    content_type = (
        file.content_type
        or "application/octet-stream"
    )

    normalized_type = (
        content_type
        .split(";", 1)[0]
        .strip()
        .lower()
    )

    if (
        normalized_type
        not in ALLOWED_AUDIO_TYPES
    ):
        raise HTTPException(
            status_code=415,
            detail=(
                "Unsupported audio format: "
                f"{content_type}"
            ),
        )

    try:
        audio = await file.read()

    finally:
        await file.close()

    if not audio:
        raise HTTPException(
            status_code=400,
            detail="Empty audio file",
        )

    if (
        len(audio)
        > MAX_AUDIO_BYTES
    ):
        raise HTTPException(
            status_code=413,
            detail=(
                "Audio file is too large. "
                "Maximum size is 15 MB."
            ),
        )

    try:

        text = await transcribe_audio(
            audio=audio,

            filename=(
                file.filename
                or "recording.webm"
            ),

            content_type=(
                content_type
            ),
        )

    except SpeechServiceError as exc:

        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    return TranscriptionResponse(
        text=text,
    )


# ============================================================
# TEXT -> VOICE
# ============================================================

@router.post(
    "/synthesize",
)
async def synthesize(
    body: SpeechRequest,

    ctx: UserContext = Depends(
        get_live_user
    ),
):
    """
    RAG answer text
        ↓
    BNU Backend
        ↓
    ElevenLabs
        ↓
    MP3 bytes
        ↓
    Browser
    """

    del ctx

    text = body.text.strip()

    if not text:
        raise HTTPException(
            status_code=400,
            detail="Text is required",
        )

    if (
        len(text)
        > MAX_TTS_CHARACTERS
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Text is too long for "
                "speech synthesis. "
                f"Maximum is "
                f"{MAX_TTS_CHARACTERS} "
                "characters."
            ),
        )

    try:

        (
            audio,
            media_type,
        ) = await synthesize_speech(
            text=text,

            requested_language=(
                body.language
            ),
        )

    except SpeechServiceError as exc:

        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    #
    # We return the actual MP3 data.
    # No external URL is returned.
    #
    return Response(
        content=audio,

        media_type=media_type,

        headers={
            "Content-Disposition":
                'inline; filename="answer.mp3"',

            "Cache-Control":
                "private, no-store",
        },
    )