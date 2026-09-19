from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.dependencies import chat_service


router = APIRouter(
    prefix="/api/memory",
    tags=["memory"],
)


class MemoryCreate(BaseModel):
    key: str = Field(
        min_length=1,
        max_length=100,
    )

    value: str = Field(
        min_length=1,
        max_length=1000,
    )

    category: str = Field(
        min_length=1,
        max_length=100,
    )

    importance: int = Field(
        default=5,
        ge=1,
        le=10,
    )


class MemoryUpdate(BaseModel):
    value: str | None = Field(
        default=None,
        min_length=1,
        max_length=1000,
    )

    importance: int | None = Field(
        default=None,
        ge=1,
        le=10,
    )


class MemoryResponse(BaseModel):
    memory_id: int
    key: str
    value: str
    category: str
    importance: int
    confidence: float
    source: str
    created_at: datetime | None
    updated_at: datetime | None


def memory_to_response(memory) -> MemoryResponse:
    return MemoryResponse(
        memory_id=memory.memory_id,
        key=memory.key,
        value=memory.value,
        category=memory.category,
        importance=memory.importance,
        confidence=memory.confidence,
        source=memory.source,
        created_at=memory.created_at,
        updated_at=memory.updated_at,
    )


@router.get("")
async def get_memories(
    user_id: int = Query(
        default=1,
        ge=1,
    ),
    category: str | None = Query(
        default=None,
    ),
):
    memories = chat_service.memory.get_all_memory(
        user_id=user_id,
        category=category,
    )

    return {
        "memories": [
            memory_to_response(memory)
            for memory in memories
        ]
    }


@router.get("/categories")
async def get_memory_categories(
    user_id: int = Query(
        default=1,
        ge=1,
    ),
):
    return {
        "categories": chat_service.memory.get_memory_categories(
            user_id=user_id,
        )
    }


@router.get("/{memory_id}")
async def get_memory(
    memory_id: int,
    user_id: int = Query(
        default=1,
        ge=1,
    ),
):
    memory = chat_service.memory.get_memory_by_id(
        user_id=user_id,
        memory_id=memory_id,
    )

    if memory is None:
        raise HTTPException(
            status_code=404,
            detail="Memory not found.",
        )

    return memory_to_response(memory)


@router.post(
    "",
    response_model=MemoryResponse,
)
async def create_memory(
    request: MemoryCreate,
    user_id: int = Query(
        default=1,
        ge=1,
    ),
):
    memory = chat_service.memory.create_memory(
        user_id=user_id,
        key=request.key.strip(),
        value=request.value.strip(),
        category=request.category.strip(),
        importance=request.importance,
    )

    return memory_to_response(memory)


@router.put(
    "/{memory_id}",
    response_model=MemoryResponse,
)
async def update_memory(
    memory_id: int,
    request: MemoryUpdate,
    user_id: int = Query(
        default=1,
        ge=1,
    ),
):
    if (
        request.value is None
        and request.importance is None
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "At least one field must be provided "
                "for update."
            ),
        )

    value = (
        request.value.strip()
        if request.value is not None
        else None
    )

    if value == "":
        raise HTTPException(
            status_code=400,
            detail="Memory value cannot be empty.",
        )

    memory = chat_service.memory.update_memory(
        user_id=user_id,
        memory_id=memory_id,
        value=value,
        importance=request.importance,
    )

    if memory is None:
        raise HTTPException(
            status_code=404,
            detail="Memory not found.",
        )

    return memory_to_response(memory)


@router.delete("/{memory_id}")
async def delete_memory(
    memory_id: int,
    user_id: int = Query(
        default=1,
        ge=1,
    ),
):
    deleted = chat_service.memory.delete_memory_by_id(
        user_id=user_id,
        memory_id=memory_id,
    )

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Memory not found.",
        )

    return {
        "success": True,
        "message": "Memory deleted successfully.",
        "memory_id": memory_id,
    }