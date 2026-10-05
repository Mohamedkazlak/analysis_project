import { fetchFromBackend } from "../api";

/**
 * Chat is `POST /api/chat`. The server loads the live account from the JWT
 * user id, then the RAG engine validates any generated SQL before it runs.
 * Handoff fields are ids only — never send fact content from the client.
 */

export interface ChatActivityStep {
  id: string;
  label: string;
  done: boolean;
}

export interface ChatAnalyticalObject {
  type:
    | "metric"
    | "comparison"
    | "warning"
    | "pattern"
    | "what_if"
    | "recommendation"
    | "evidence"
    | "policy"
    | "prediction";
  title: string;
  data: Record<string, unknown>;
}

export interface AssistantAnswer {
  text: string;
  blocked: boolean;
  openIssues?: string[] | null;
  activities?: ChatActivityStep[] | null;
  objects?: ChatAnalyticalObject[] | null;
  evidenceQuality?: Record<string, unknown> | null;
  sources?: Array<Record<string, unknown>> | null;
}

export interface ChatHandoff {
  cardId?: string;
  slice?: Record<string, string | null | undefined>;
  itemId?: string;
}

export function askAssistant(
  question: string,
  handoff?: ChatHandoff,
  language: "en" | "ar" = "en",
): Promise<AssistantAnswer> {
  return fetchFromBackend<AssistantAnswer>("/api/chat", {
    method: "POST",
    body: {
      question,
      cardId: handoff?.cardId ?? null,
      slice: handoff?.slice ?? null,
      itemId: handoff?.itemId ?? null,
      language,
    },
  });
}
