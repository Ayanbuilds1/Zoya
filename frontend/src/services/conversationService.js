import { API_BASE_URL } from "./api";

const DEFAULT_USER_ID = 1;

const getErrorMessage = (data, fallback) => {
  if (Array.isArray(data?.detail)) {
    return data.detail[0]?.msg || fallback;
  }

  return data?.detail || fallback;
};

const requestJson = async (url, options, fallbackMessage) => {
  const response = await fetch(url, options);
  const data = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(getErrorMessage(data, fallbackMessage));
  }

  return data;
};

export const listConversations = async (userId = DEFAULT_USER_ID) =>
  requestJson(
    `${API_BASE_URL}/api/chat/conversations?user_id=${encodeURIComponent(userId)}`,
    undefined,
    "Conversation list load failed."
  );

export const createConversation = async (userId = DEFAULT_USER_ID) =>
  requestJson(
    `${API_BASE_URL}/api/chat/conversations?user_id=${encodeURIComponent(userId)}`,
    { method: "POST" },
    "Unable to create a new chat."
  );

export const renameConversation = async (conversationId, title, userId = DEFAULT_USER_ID) =>
  requestJson(
    `${API_BASE_URL}/api/chat/conversations/${conversationId}`,
    {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        user_id: userId,
        title,
      }),
    },
    "Unable to rename conversation."
  );

export const deleteConversation = async (conversationId, userId = DEFAULT_USER_ID) =>
  requestJson(
    `${API_BASE_URL}/api/chat/conversations/${conversationId}?user_id=${encodeURIComponent(userId)}`,
    { method: "DELETE" },
    "Unable to delete conversation."
  );

export const getConversationHistory = async (conversationId = null, userId = DEFAULT_USER_ID) => {
  const query = new URLSearchParams({ user_id: String(userId) });

  if (conversationId !== null && conversationId !== undefined) {
    query.set("conversation_id", String(conversationId));
  }

  return requestJson(
    `${API_BASE_URL}/api/chat/history?${query.toString()}`,
    undefined,
    "History load failed."
  );
};
