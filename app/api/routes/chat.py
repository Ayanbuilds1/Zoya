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
            raise ValueError("This field cannot be empty.")
    
        return value


class ConversationUpdateRequest(BaseModel):
    user_id: int = Field(default=1, ge=1)
    title: str = Field(min_length=1, max_length=80)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        value = " ".join(value.strip().split())
        if not value:
            raise ValueError("Conversation title cannot be empty.")
        return value


async def event_stream(
    request: StreamChatRequest,
):
    try:
        conversation_id = chat_service.get_active_conversation_id(
            request.user_id
        )

        if request.conversation_id is not None:
            conversation_id = request.conversation_id

        yield (
            "event: metadata\n"
            f"data: {json.dumps({'conversation_id': conversation_id}, ensure_ascii=False)}\n\n"
        )

        async for event in chat_service.stream_chat_events(
            user_id=request.user_id,
            user_name=request.user_name,
            message=request.message,
            conversation_id=request.conversation_id,
        ):
            event_name = event.get("event", "message")
            payload = event.get("data", {})

            yield (
                f"event: {event_name}\n"
                f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            )

    except ValueError as error:
        yield (
            "event: error\n"
            f"data: {json.dumps({'message': str(error)}, ensure_ascii=False)}\n\n"
        )

    except Exception:
        print("\n❌ STREAM CHAT ERROR")

        import traceback

        traceback.print_exc()

        yield (
            "event: error\n"
            f"data: {json.dumps({'message': 'Zoya AI service is temporarily unavailable.'}, ensure_ascii=False)}\n\n"
        )


@router.post("/stream")
async def stream_chat(
    request: StreamChatRequest,
):
    if not request.message.strip():
        raise HTTPException(
            status_code=400,
            detail="Message cannot be empty.",
        )

    if len(request.message.strip()) > MAX_MESSAGE_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Message is too long. Maximum allowed length is "
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


@router.get("/conversations")
async def list_conversations(
    user_id: int = 1,
    limit: int = 50,
):
    if user_id < 1:
        raise HTTPException(status_code=400, detail="Invalid user_id.")

    limit = max(1, min(limit, 200))

    try:
        return {
            "conversations": chat_service.list_conversations(
                user_id=user_id,
                limit=limit,
            )
        }
    except Exception as error:
        print("\n❌ CONVERSATIONS LIST ERROR")
        print(f"Error type: {type(error).__name__}")
        print(f"Error message: {error}")
        raise HTTPException(
            status_code=503,
            detail="Unable to load conversations.",
        ) from error


@router.post("/conversations")
async def create_conversation(
    user_id: int = 1,
):
    if user_id < 1:
        raise HTTPException(status_code=400, detail="Invalid user_id.")

    try:
        chat_service.memory.get_or_create_user(user_id)
        return chat_service.create_conversation(user_id=user_id)
    except Exception as error:
        print("\n❌ CONVERSATION CREATE ERROR")
        print(f"Error type: {type(error).__name__}")
        print(f"Error message: {error}")
        raise HTTPException(
            status_code=503,
            detail="Unable to create conversation.",
        ) from error


@router.patch("/conversations/{conversation_id}")
async def rename_conversation(
    conversation_id: int,
    request: ConversationUpdateRequest,
):
    try:
        result = chat_service.rename_conversation(
            user_id=request.user_id,
            conversation_id=conversation_id,
            title=request.title,
        )

        if result is None:
            raise HTTPException(
                status_code=404,
                detail="Conversation not found.",
            )

        return result
    except HTTPException:
        raise
    except Exception as error:
        print("\n❌ CONVERSATION RENAME ERROR")
        print(f"Error type: {type(error).__name__}")
        print(f"Error message: {error}")
        raise HTTPException(
            status_code=503,
            detail="Unable to rename conversation.",
        ) from error


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: int,
    user_id: int = 1,
):
    if user_id < 1:
        raise HTTPException(status_code=400, detail="Invalid user_id.")

    try:
        deleted = chat_service.delete_conversation(
            user_id=user_id,
            conversation_id=conversation_id,
        )

        if not deleted:
            raise HTTPException(
                status_code=404,
                detail="Conversation not found.",
            )

        return {
            "ok": True,
            "conversation_id": conversation_id,
        }
    except HTTPException:
        raise
    except Exception as error:
        print("\n❌ CONVERSATION DELETE ERROR")
        print(f"Error type: {type(error).__name__}")
        print(f"Error message: {error}")
        raise HTTPException(
            status_code=503,
            detail="Unable to delete conversation.",
        ) from error


@router.get("/history")
async def get_history(
    user_id: int = 1,
    conversation_id: int | None = None,
):
    if user_id < 1:
        raise HTTPException(status_code=400, detail="Invalid user_id.")

    if conversation_id is not None and conversation_id < 1:
        raise HTTPException(status_code=400, detail="Invalid conversation_id.")

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
