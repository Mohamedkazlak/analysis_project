/**
 * Tiny event bus so reference pages can open the existing ChatPanel
 * pre-scoped to a context (a student, the directory, …) without new routes.
 * Card handoff sends ids only — never fact content.
 */
export interface ChatOpenRequest {
  /** Short context label shown under the panel header. */
  context: string;
  /** Optional question pre-filled in the composer. */
  question?: string;
  cardId?: string;
  slice?: Record<string, string | null | undefined>;
  itemId?: string;
}

type Listener = (req: ChatOpenRequest) => void;

const listeners = new Set<Listener>();

export function openChat(req: ChatOpenRequest) {
  listeners.forEach((l) => l(req));
}

export function subscribeToChatOpen(listener: Listener) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}
