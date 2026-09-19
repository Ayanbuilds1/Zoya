import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from app.api.dependencies import chat_service


router = APIRouter(
    prefix="/api/chat",
    tags=["chat"],
)


MAX_MESSAGE_LENGTH = 12000
MAX_USER_NAME_LENGTH = 100


class StreamChatRequest(BaseModel):
    user_id: int = Field(
        default=1,
        ge=1,
        description="Stable development user ID.",
    )

    user_name: str = Field(
        default="Ayan",
        min_length=1,
        max_length=MAX_USER_NAME_LENGTH,
    )

    message: str = Field(
        min_length=1,
        max_length=MAX_MESSAGE_LENGTH,
    )

    conversation_id: int | None = Field(
        default=None,
        ge=1,
    )

    @field_validator("user_name", "message")
    @classmethod
    def validate_text_fields(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError(
                "This field cannot be empty."
            )

        return value


async def event_stream(request: StreamChatRequest):
    try:
        conversation_id = chat_service.get_active_conversation_id(
            request.user_id
        )

        if request.conversation_id is not None:
            conversation_id = request.conversation_id

        yield (
            "event: metadata\n"
            f"data: {json.dumps({'conversation_id': conversation_id})}\n\n"
        )

        async for chunk in chat_service.stream_chat(
            user_id=request.user_id,
            user_name=request.user_name,
            message=request.message,
            conversation_id=request.conversation_id,
        ):
            yield (
                "event: chunk\n"
                f"data: {json.dumps({'content': chunk})}\n\n"
            )

        yield (
            "event: done\n"
            f"data: {json.dumps({'active_provider': chat_service.ai.active_provider})}\n\n"
        )

    except ValueError as error:
        yield (
            "event: error\n"
            f"data: {json.dumps({'message': str(error)})}\n\n"
        )

    except Exception:
        print("\n❌ STREAM CHAT ERROR")

        import traceback

        traceback.print_exc()

        yield (
            "event: error\n"
            f"data: {json.dumps({'message': 'Zoya AI service is temporarily unavailable.'})}\n\n"
        )


@router.post("/stream")
async def stream_chat(request: StreamChatRequest):
    if not request.message.strip():
        raise HTTPException(
            status_code=400,
            detail="Message cannot be empty.",
        )

    if len(request.message.strip()) > MAX_MESSAGE_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Message is too long. "
                f"Maximum allowed length is "
                f"{MAX_MESSAGE_LENGTH} characters."
            ),
        )

    return StreamingResponse(
        event_stream(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/history")
async def get_history(
    user_id: int = 1,
    conversation_id: int | None = None,
):
    if user_id < 1:
        raise HTTPException(
            status_code=400,
            detail="Invalid user_id.",
        )

    if conversation_id is not None and conversation_id < 1:
        raise HTTPException(
            status_code=400,
            detail="Invalid conversation_id.",
        )

    try:
        return chat_service.get_conversation_history(
            user_id=user_id,
            conversation_id=conversation_id,
        )

    except Exception as error:
        print("\n❌ HISTORY ERROR")
        print(f"Error type: {type(error).__name__}")
        print(f"Error message: {error}")

        raise HTTPException(
            status_code=503,
            detail="Unable to load conversation history.",
        ) from error