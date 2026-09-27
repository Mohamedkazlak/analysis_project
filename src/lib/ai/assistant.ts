import { fetchFromBackend } from "../api";

/**
 * Chat is `POST /api/chat`. The server loads the live account from the JWT
 * user id, then the RAG engine validates any generated SQL before it runs.
 */

export interface AssistantAnswer {
  text: string;
  blocked: boolean;
}

export function askAssistant(question: string): Promise<AssistantAnswer> {
  return fetchFromBackend<AssistantAnswer>("/api/chat", {
    method: "POST",
    body: { question },
  });
}
