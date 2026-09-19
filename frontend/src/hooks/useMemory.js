import { useCallback, useEffect, useState } from "react";

const API_BASE_URL = "http://127.0.0.1:8000";
const USER_ID = 1;

export function useMemory(category = "") {
  const [memories, setMemories] = useState([]);
  const [categories, setCategories] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  const fetchMemories = useCallback(async () => {
    try {
      setError("");

      const categoryQuery = category
        ? `&category=${encodeURIComponent(category)}`
        : "";

      const response = await fetch(
        `${API_BASE_URL}/api/memory?user_id=${USER_ID}${categoryQuery}`
      );

      if (!response.ok) {
        throw new Error("Unable to load memories.");
      }

      const data = await response.json();

      setMemories(data.memories || []);
    } catch (error) {
      console.error("Memory loading error:", error);

      setError(
        error instanceof Error
          ? error.message
          : "Unable to load memories."
      );
    }
  }, [category]);

  const fetchCategories = useCallback(async () => {
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/memory/categories?user_id=${USER_ID}`
      );

      if (!response.ok) {
        throw new Error("Unable to load memory categories.");
      }

      const data = await response.json();

      setCategories(data.categories || []);
    } catch (error) {
      console.error(
        "Memory categories loading error:",
        error
      );
    }
  }, []);

  const refreshMemories = useCallback(async () => {
    setIsLoading(true);

    await Promise.all([
      fetchMemories(),
      fetchCategories(),
    ]);

    setIsLoading(false);
  }, [fetchMemories, fetchCategories]);

  const createMemory = async ({
    key,
    value,
    category,
    importance,
  }) => {
    const response = await fetch(
      `${API_BASE_URL}/api/memory?user_id=${USER_ID}`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          key,
          value,
          category,
          importance,
        }),
      }
    );

    if (!response.ok) {
      const data = await response.json().catch(() => null);

      throw new Error(
        data?.detail || "Unable to create memory."
      );
    }

    const memory = await response.json();

    await refreshMemories();

    return memory;
  };

  const updateMemory = async (
    memoryId,
    { value, importance }
  ) => {
    const response = await fetch(
      `${API_BASE_URL}/api/memory/${memoryId}?user_id=${USER_ID}`,
      {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          value,
          importance,
        }),
      }
    );

    if (!response.ok) {
      const data = await response.json().catch(() => null);

      throw new Error(
        data?.detail || "Unable to update memory."
      );
    }

    const memory = await response.json();

    await refreshMemories();

    return memory;
  };

  const deleteMemory = async (memoryId) => {
    const response = await fetch(
      `${API_BASE_URL}/api/memory/${memoryId}?user_id=${USER_ID}`,
      {
        method: "DELETE",
      }
    );

    if (!response.ok) {
      const data = await response.json().catch(() => null);

      throw new Error(
        data?.detail || "Unable to delete memory."
      );
    }

    await refreshMemories();
  };

  useEffect(() => {
    refreshMemories();
  }, [refreshMemories]);

  return {
    memories,
    categories,
    isLoading,
    error,
    createMemory,
    updateMemory,
    deleteMemory,
    refreshMemories,
  };
}