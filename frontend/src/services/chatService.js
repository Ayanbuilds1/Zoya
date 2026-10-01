import { API_BASE_URL } from "./api";

const DEFAULT_USER_ID = 1;
const DEFAULT_USER_NAME = "Ayan";

const getErrorMessage = (data, fallback) => {
  if (Array.isArray(data?.detail)) {
    return data.detail[0]?.msg || fallback;
  }

  return data?.detail || fallback;
};

const readErrorResponse = async (response, fallback) => {
  const data = await response.json().catch(() => null);
  return getErrorMessage(data, fallback);
};

export const streamChat = async ({
  userId = DEFAULT_USER_ID,
  userName = DEFAULT_USER_NAME,
  message,
  conversationId = null,
  newConversation = false,
  signal,
  onEvent,
}) => {
  const response = await fetch(`${API_BASE_URL}/api/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    signal,
    body: JSON.stringify({
      user_id: userId,
      user_name: userName,
      message,
      conversation_id: conversationId,
      new_conversation: newConversation,
    }),
  });

  if (!response.ok) {
    throw new Error(
      await readErrorResponse(
        response,
        "Zoya AI service is temporarily unavailable."
      )
    );
  }

  if (!response.body) {
    throw new Error(
      "Streaming response is not supported by this browser."
    );
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  let streamCompleted = false;

  while (!streamCompleted) {
    const { value, done } = await reader.read();

    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split("\n\n");
    buffer = events.pop() || "";

    for (const event of events) {
      const result = onEvent ? await onEvent(event) : undefined;
      if (result === "done") {
        streamCompleted = true;
        break;
      }
    }
  }

  buffer += decoder.decode();

  if (buffer.trim() && !streamCompleted) {
    await onEvent?.(buffer);
  }

  if (streamCompleted) {
    try {
      await reader.cancel();
    } catch {
      // Ignore reader cancellation failures after completion.
    }
  }
};
