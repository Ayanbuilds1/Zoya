from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.api.dependencies import chat_service
from app.api.routes.chat import router as chat_router
from app.api.routes.memory import router as memory_router


app = FastAPI(
    title="Zoya API",
    description="Backend API for Zoya Personal AI Assistant.",
    version="0.1.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(chat_router)
app.include_router(memory_router)


class ChatRequest(BaseModel):
    user_id: int = Field(
        default=1,
        description="Stable development user ID.",
    )

    user_name: str = Field(
        default="Ayan",
        min_length=1,
        max_length=100,
    )

    message: str = Field(
        min_length=1,
        max_length=12000,
    )

    conversation_id: int | None = None


class ChatResponse(BaseModel):
    response: str
    conversation_id: int
    active_provider: str


@app.get("/")
async def root() -> dict:
    return {
        "name": "Zoya API",
        "status": "online",
        "version": "0.1.0",
    }


@app.get("/api/health")
async def health() -> dict:
    return {
        "status": "healthy",
        "active_provider": chat_service.ai.active_provider,
        "configured_providers": [
            name
            for name, _ in chat_service.ai.providers
        ],
    }


@app.post(
    "/api/chat",
    response_model=ChatResponse,
)
async def chat(request: ChatRequest) -> ChatResponse:
    try:
        result = await chat_service.chat(
            user_id=request.user_id,
            user_name=request.user_name,
            message=request.message,
            conversation_id=request.conversation_id,
        )

        return ChatResponse(**result)

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except Exception as error:
        print("\n❌ API CHAT ERROR")
        print(f"Error type: {type(error).__name__}")
        print(f"Error message: {error}")

        raise HTTPException(
            status_code=503,
            detail="Zoya AI service is temporarily unavailable.",
        ) from error