import io
import logging
import edge_tts
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from app.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tts", tags=["tts"])


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000, description="Texto a convertir en voz")


@router.post("")
async def text_to_speech(req: TTSRequest):
    settings = get_settings()
    voice = settings.TTS_VOICE

    clean_text = req.text.replace("*", "").replace("#", "").replace('"', "").replace("`", "").strip()

    try:
        communicate = edge_tts.Communicate(clean_text, voice)
        audio_buffer = io.BytesIO()

        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_buffer.write(chunk["data"])

        audio_bytes = audio_buffer.getvalue()

        if not audio_bytes:
            raise Exception("No se generó audio")

        return Response(
            content=audio_bytes,
            media_type="audio/mpeg",
            headers={"Cache-Control": "no-store"},
        )

    except Exception as e:
        logger.error("Edge TTS error: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generando audio: {str(e)}",
        )
