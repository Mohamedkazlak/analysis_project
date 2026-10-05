import { useEffect, useRef, useState } from "react";
import {
  MessageCircle,
  Mic,
  PenLine,
  Send,
  Square,
  Volume2,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { ApiError } from "@/lib/api";
import type { Role } from "@/lib/types";
import {
  askAssistant,
  type ChatActivityStep,
  type ChatAnalyticalObject,
} from "@/lib/ai/assistant";
import { synthesizeSpeech, transcribeAudio } from "@/lib/ai/speech";
import { subscribeToChatOpen } from "@/lib/chat-bus";
import { useRole } from "./role-context";
import { speechLanguageForLocale, useLocale } from "@/lib/i18n";

type VoiceState = "idle" | "listening" | "thinking" | "speaking" | "error";

function openerFor(
  role: Role,
  name: string,
  openers: Record<string, string>,
  studentGreeting: string,
): string {
  const roleOpener = openers[role] ?? openers["student"] ?? "";
  if (role !== "student") return roleOpener;
  const given = name
    .trim()
    .split(/\s+/)
    .find((part) => part && !/^(prof\.?|dr\.?)$/i.test(part));
  const who = given && !/^u[-_]/i.test(given) ? given : "there";
  const opener = openers["student"] ?? "";
  if (!opener) return studentGreeting.replace("{name}", who);
  return `${studentGreeting.replace("{name}", who)} ${opener.charAt(0).toLowerCase()}${opener.slice(1)}`;
}

interface Msg {
  id: number;
  from: "user" | "ai";
  text: string;
  blocked?: boolean;
  activities?: ChatActivityStep[];
  objects?: ChatAnalyticalObject[];
  sources?: Array<Record<string, unknown>>;
}

function WritingText({ text }: { text: string }) {
  // Fast progressive reveal — readable immediately, slight pen feel.
  const [shown, setShown] = useState(
    text.length < 80 ? text : text.slice(0, 48),
  );
  useEffect(() => {
    if (shown.length >= text.length) return;
    const id = window.setTimeout(() => {
      setShown(text.slice(0, Math.min(text.length, shown.length + 24)));
    }, 12);
    return () => window.clearTimeout(id);
  }, [shown, text]);
  return (
    <span>
      {shown}
      {shown.length < text.length && (
        <PenLine className="ms-1 inline size-3 animate-pulse text-ai/70" />
      )}
    </span>
  );
}

function AnalyticalObjectCard({ obj }: { obj: ChatAnalyticalObject }) {
  const { messages } = useLocale();
  const chat = messages.chat;
  const data = obj.data || {};
  if (obj.type === "what_if") {
    const change = (data["estimatedChange"] || {}) as Record<string, any>;
    const college = change["collegePassRate"];
    const uni = change["universityPassRate"];
    const scope = (data["scopeAffected"] || {}) as Record<string, any>;
    const entity = String(data["entity"] || "");
    const currentValue = data["currentValue"];
    const targetValue = data["targetValue"];
    const participants = scope["courseParticipants"];
    const assumption =
      data["kind"] === "college_pass_uplift"
        ? chat.whatIfAssumptionCollege
            .replace("{from}", String(currentValue))
            .replace("{to}", String(targetValue))
        : chat.whatIfAssumptionCourse
            .replace("{course}", entity)
            .replace("{from}", String(currentValue))
            .replace("{to}", String(targetValue))
            .replace("{n}", String(participants ?? "—"));
    return (
      <div className="mt-2 rounded-xl border border-black/8 bg-white/80 p-3 text-[12px]">
        <div className="text-[10px] font-bold uppercase tracking-[0.12em] text-ai">
          {chat.whatIf}
        </div>
        <div className="mt-1 font-semibold text-ink">{obj.title}</div>
        <p className="mt-1 text-ink-soft">{assumption}</p>
        <div className="mt-2 grid grid-cols-2 gap-2">
          <div className="rounded-lg bg-black/[0.03] p-2">
            <div className="text-[10px] text-ink-soft">{chat.current}</div>
            <div className="font-semibold">{String(currentValue)}%</div>
          </div>
          <div className="rounded-lg bg-black/[0.03] p-2">
            <div className="text-[10px] text-ink-soft">{chat.target}</div>
            <div className="font-semibold">{String(targetValue)}%</div>
          </div>
        </div>
        {college && (
          <p className="mt-2 text-ink">
            {chat.whatIfDelta
              .replace("{label}", chat.college)
              .replace("{from}", String(college.from))
              .replace("{to}", String(college.to))
              .replace("{delta}", String(college.delta))}
          </p>
        )}
        {uni && (
          <p className="text-ink">
            {chat.whatIfDelta
              .replace("{label}", chat.university)
              .replace("{from}", String(uni.from))
              .replace("{to}", String(uni.to))
              .replace("{delta}", String(uni.delta))}
          </p>
        )}
      </div>
    );
  }
  if (obj.type === "policy") {
    return (
      <div className="mt-2 rounded-xl border border-black/8 bg-white/80 p-3 text-[12px]">
        <div className="text-[10px] font-bold uppercase tracking-[0.12em] text-ink-soft">
          {chat.policySource}
        </div>
        <div className="mt-1 font-semibold text-ink">{obj.title}</div>
        <p className="mt-1 text-ink-soft">{String(data["snippet"] || "")}</p>
      </div>
    );
  }
  const typeLabel =
    chat.objectTypes[obj.type as keyof typeof chat.objectTypes] ?? obj.type;
  return (
    <div className="mt-2 rounded-xl border border-black/8 bg-white/80 p-3 text-[12px]">
      <div className="text-[10px] font-bold uppercase tracking-[0.12em] text-ai">
        {typeLabel}
      </div>
      <div className="mt-1 font-semibold text-ink">{obj.title}</div>
    </div>
  );
}

function StateOrb({
  state,
  labels,
}: {
  state: VoiceState;
  labels: {
    stateReady: string;
    stateListening: string;
    stateThinking: string;
    stateSpeaking: string;
    stateError: string;
  };
}) {
  const label =
    state === "listening"
      ? labels.stateListening
      : state === "thinking"
        ? labels.stateThinking
        : state === "speaking"
          ? labels.stateSpeaking
          : state === "error"
            ? labels.stateError
            : labels.stateReady;
  return (
    <div className="flex items-center gap-2">
      <span
        className={cn(
          "inline-flex size-2.5 rounded-full",
          state === "idle" && "bg-ink-soft/40",
          state === "listening" && "animate-pulse bg-rose-500",
          state === "thinking" && "animate-pulse bg-ai",
          state === "speaking" && "animate-pulse bg-emerald-500",
          state === "error" && "bg-rose-700",
        )}
      />
      <span className="text-[11px] font-medium text-ink-soft">{label}</span>
    </div>
  );
}

export function ChatPanel() {
  const { role, user } = useRole();
  const { locale, messages: copy } = useLocale();
  const chat = copy.chat;
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [context, setContext] = useState<string | null>(null);
  const [handoff, setHandoff] = useState<{
    cardId?: string;
    slice?: Record<string, string | null | undefined>;
    itemId?: string;
  } | null>(null);
  const [pending, setPending] = useState(false);
  const [voiceState, setVoiceState] = useState<VoiceState>("idle");
  const [liveActivities, setLiveActivities] = useState<ChatActivityStep[]>([]);
  const greeting = openerFor(
    role,
    user.name,
    chat.openers,
    chat.studentGreeting,
  );
  const identity = `${role}:${user.id}:${locale}`;
  const identityRef = useRef(identity);
  const [messages, setMessages] = useState<Msg[]>(() => [
    { id: 0, from: "ai", text: greeting },
  ]);
  const threadRef = useRef<HTMLDivElement>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (identityRef.current !== identity) {
      identityRef.current = identity;
      setMessages([{ id: 0, from: "ai", text: greeting }]);
      return;
    }
    setMessages((current) => {
      if (current.length !== 1 || current[0]?.id !== 0) return current;
      if (current[0].text === greeting) return current;
      return [{ id: 0, from: "ai", text: greeting }];
    });
  }, [identity, greeting]);

  useEffect(
    () =>
      subscribeToChatOpen((req) => {
        setContext(req.context);
        setHandoff({
          ...(req.cardId ? { cardId: req.cardId } : {}),
          ...(req.slice ? { slice: req.slice } : {}),
          ...(req.itemId ? { itemId: req.itemId } : {}),
        });
        setOpen(true);
        if (req.question) setInput(req.question);
      }),
    [],
  );

  useEffect(() => {
    threadRef.current?.scrollTo({
      top: threadRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, pending, voiceState, open, liveActivities]);

  useEffect(() => {
    return () => {
      recorderRef.current?.stop();
      streamRef.current?.getTracks().forEach((track) => track.stop());
      audioRef.current?.pause();
    };
  }, []);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        if (recorderRef.current && recorderRef.current.state !== "inactive") {
          recorderRef.current.stop();
        }
        setOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    const focusTimer = window.setTimeout(() => inputRef.current?.focus(), 280);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.clearTimeout(focusTimer);
    };
  }, [open]);

  const addError = (text: string) => {
    setVoiceState("error");
    setMessages((items) => [...items, { id: Date.now(), from: "ai", text }]);
  };

  const playSpeech = async (text: string) => {
    setVoiceState("speaking");
    try {
      audioRef.current?.pause();
      const blob = await synthesizeSpeech(
        text,
        speechLanguageForLocale(locale),
      );
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audioRef.current = audio;
      await new Promise<void>((resolve, reject) => {
        audio.addEventListener(
          "ended",
          () => {
            URL.revokeObjectURL(url);
            resolve();
          },
          { once: true },
        );
        audio.addEventListener("error", () => reject(new Error("playback")), {
          once: true,
        });
        void audio.play();
      });
      setVoiceState("idle");
    } catch {
      setVoiceState("error");
      throw new Error("speech");
    }
  };

  const send = async (question: string) => {
    const text = question.trim();
    if (!text || pending) return;
    setInput("");
    setMessages((m) => [...m, { id: Date.now(), from: "user", text }]);
    setPending(true);
    setVoiceState("thinking");
    setLiveActivities([
      { id: "question", label: chat.analyzingQuestion, done: false },
    ]);
    try {
      const answer = await askAssistant(text, handoff ?? undefined, locale);
      const steps = (
        answer.activities?.length
          ? answer.activities
          : [
              {
                id: "analysis",
                label: chat.activityLabels.analysis,
                done: true,
              },
            ]
      ).map((step) => ({
        ...step,
        label:
          chat.activityLabels[step.id as keyof typeof chat.activityLabels] ??
          step.label,
      }));
      setLiveActivities(steps);
      const aiMsg: Msg = {
        id: Date.now() + 1,
        from: "ai",
        text: answer.text,
        blocked: answer.blocked,
        activities: steps,
      };
      if (answer.objects?.length) aiMsg.objects = answer.objects;
      if (answer.sources?.length) aiMsg.sources = answer.sources;
      setMessages((m) => [...m, aiMsg]);
      setLiveActivities([]);

      setVoiceState("idle");
    } catch (error) {
      const detail =
        error instanceof ApiError && error.message.trim()
          ? error.message.trim()
          : chat.notUnderstood;
      // Soft "not understood" from the API is a normal reply, not a hard fault.
      if (
        error instanceof ApiError &&
        error.status === 400 &&
        /not understand|لم أفهم/i.test(detail)
      ) {
        setMessages((m) => [
          ...m,
          { id: Date.now() + 1, from: "ai", text: chat.notUnderstood },
        ]);
        setVoiceState("idle");
      } else {
        addError(detail);
      }
    } finally {
      setPending(false);
    }
  };

  const startRecording = async () => {
    if (voiceState === "listening" || pending) return;
    if (!navigator.mediaDevices?.getUserMedia) {
      addError(chat.micUnsupported);
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      chunksRef.current = [];
      const recorder = new MediaRecorder(stream);
      recorderRef.current = recorder;
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data);
      };
      recorder.onstop = async () => {
        setVoiceState("thinking");
        try {
          const blob = new Blob(chunksRef.current, {
            type: recorder.mimeType || "audio/webm",
          });
          const result = await transcribeAudio(blob);
          await send(result.text);
        } catch {
          addError(chat.recordingFailed);
        } finally {
          stream.getTracks().forEach((track) => track.stop());
          streamRef.current = null;
          recorderRef.current = null;
          chunksRef.current = [];
        }
      };
      recorder.start();
      setVoiceState("listening");
    } catch {
      addError(chat.micDenied);
    }
  };

  const stopRecording = () => {
    if (recorderRef.current && recorderRef.current.state !== "inactive") {
      recorderRef.current.stop();
    }
  };

  const closeChat = () => {
    if (voiceState === "listening") stopRecording();
    setOpen(false);
  };

  return (
    <>
      {!open && (
        <button
          onClick={() => setOpen(true)}
          className="chat-fab fixed bottom-6 end-6 z-40 flex items-center gap-2 rounded-full bg-ai px-4 py-3 text-[13px] font-semibold text-white shadow-xl shadow-ai/30 transition-transform duration-200 hover:scale-105 active:scale-95"
        >
          <MessageCircle className="size-4" />
          {chat.askAi}
        </button>
      )}

      {open && (
        <>
          <button
            type="button"
            aria-label={chat.closeChat}
            className="chat-backdrop fixed inset-0 z-40 border-0 bg-ink/20 backdrop-blur-[2px]"
            onClick={closeChat}
          />
          <div
            className="chat-panel-enter fixed bottom-5 end-5 z-50 flex h-[min(820px,calc(100vh-4.5rem))] w-[min(680px,calc(100vw-2.5rem))] flex-col overflow-hidden rounded-3xl border border-black/10 bg-[#f7f6f2] shadow-2xl"
            style={{
              backgroundImage:
                "radial-gradient(circle at 1px 1px, rgba(0,0,0,0.06) 1px, transparent 0)",
              backgroundSize: "18px 18px",
            }}
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-black/8 bg-white/70 px-4 py-3 backdrop-blur">
              <div>
                <div className="text-[13px] font-semibold text-ink">
                  {chat.workspaceTitle}
                </div>
                <div className="text-[11px] text-ink-soft">
                  {context || chat.headers[role]}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <StateOrb state={voiceState} labels={chat} />
                <button
                  onClick={closeChat}
                  aria-label={chat.closeChat}
                  className="rounded-full p-1.5 text-ink-soft transition-colors duration-150 hover:bg-black/5 hover:text-ink active:scale-90"
                >
                  <X className="size-4" />
                </button>
              </div>
            </div>

            <div
              ref={threadRef}
              className="flex-1 space-y-3 overflow-y-auto scroll-smooth px-4 py-3"
            >
              {messages.map((m) => (
                <div
                  key={m.id}
                  className={cn(
                    "chat-bubble-enter max-w-[92%] break-words rounded-2xl px-3.5 py-2.5 text-[13px] leading-relaxed shadow-sm transition-shadow duration-200",
                    m.from === "user"
                      ? "ms-auto bg-ink text-white"
                      : m.blocked
                        ? "bg-rose/10 text-rosee"
                        : "border border-black/5 bg-white/90 text-ink hover:shadow-md",
                  )}
                >
                  {m.from === "ai" && !m.blocked ? (
                    <WritingText text={m.text} />
                  ) : (
                    <span>{m.text}</span>
                  )}
                  {m.from === "ai" &&
                    m.objects?.map((obj, idx) => (
                      <AnalyticalObjectCard key={`${m.id}-${idx}`} obj={obj} />
                    ))}
                  {m.from === "ai" && m.sources && m.sources.length > 0 && (
                    <div className="mt-2 text-[10.5px] text-ink-soft">
                      {chat.sources}:{" "}
                      {m.sources
                        .map((s) => String(s["title"] || s["id"] || s["type"]))
                        .join(" · ")}
                    </div>
                  )}
                  {m.from === "ai" && !m.blocked && (
                    <button
                      type="button"
                      title={chat.playAnswer}
                      disabled={voiceState === "speaking"}
                      onClick={() => playSpeech(m.text)}
                      className="mt-2 inline-flex items-center gap-1 rounded-full px-2 py-1 text-[11px] font-medium text-ai transition-colors duration-150 hover:bg-ai/10 active:scale-95 disabled:opacity-40"
                    >
                      <Volume2 className="size-3.5" />
                      {chat.speak}
                    </button>
                  )}
                </div>
              ))}
              {pending && (
                <div className="chat-bubble-enter rounded-2xl border border-ai/20 bg-white/80 p-3">
                  <div className="text-[11px] font-bold uppercase tracking-[0.12em] text-ai">
                    {chat.working}
                  </div>
                  <ul className="mt-2 space-y-1.5">
                    {(liveActivities.length
                      ? liveActivities
                      : [{ id: "t", label: chat.thinking, done: false }]
                    ).map((step) => (
                      <li
                        key={step.id}
                        className="flex items-center gap-2 text-[12px] text-ink"
                      >
                        <span
                          className={cn(
                            "size-1.5 rounded-full",
                            step.done
                              ? "bg-emerald-500"
                              : "animate-pulse bg-ai",
                          )}
                        />
                        {step.done ? `✓ ${step.label}` : `✦ ${step.label}`}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            <div className="flex flex-wrap gap-1.5 border-t border-black/8 bg-white/60 px-3 py-2">
              {(chat.suggestions[role] ?? []).map((suggestion) => (
                <button
                  key={suggestion}
                  disabled={pending || voiceState === "listening"}
                  onClick={() => send(suggestion)}
                  className="rounded-full border border-black/10 bg-white px-2.5 py-1 text-[11px] font-medium text-ink transition-all duration-150 hover:border-ai/40 hover:bg-ai/5 hover:text-ai active:scale-95 disabled:opacity-40"
                >
                  {suggestion}
                </button>
              ))}
            </div>

            <form
              className="flex items-center gap-2 border-t border-black/8 bg-white/80 px-3 py-3"
              onSubmit={(e) => {
                e.preventDefault();
                if (voiceState !== "listening") send(input);
              }}
            >
              <input
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={
                  voiceState === "listening" ? chat.listening : chat.placeholder
                }
                disabled={voiceState === "listening"}
                className="flex-1 rounded-full border border-black/10 bg-white px-3.5 py-2 text-[13px] outline-none transition-[border-color,box-shadow] duration-200 focus:border-ai/50 focus:shadow-[0_0_0_3px_rgba(124,58,237,0.12)] disabled:bg-rose/5 disabled:text-ink-soft"
              />

              <button
                type="submit"
                disabled={
                  pending || voiceState === "listening" || !input.trim()
                }
                title={chat.send}
                aria-label={chat.send}
                className="grid size-9 place-items-center rounded-full bg-ai text-white transition-transform duration-150 hover:scale-105 active:scale-90 disabled:opacity-40"
              >
                <Send className="size-4" />
              </button>

              {voiceState === "listening" ? (
                <button
                  type="button"
                  onClick={stopRecording}
                  title={chat.stopRecording}
                  aria-label={chat.stopRecording}
                  className="grid size-9 place-items-center rounded-full bg-rose-600 text-white shadow-lg shadow-rose-600/30 animate-pulse transition-transform duration-150 active:scale-90"
                >
                  <Square className="size-3.5" />
                </button>
              ) : (
                <button
                  type="button"
                  disabled={pending || voiceState === "speaking"}
                  onClick={startRecording}
                  title={chat.voiceMessage}
                  aria-label={chat.voiceMessage}
                  className="grid size-9 place-items-center rounded-full bg-ai text-white shadow-md shadow-ai/20 transition-transform duration-150 hover:scale-105 active:scale-90 disabled:opacity-40"
                >
                  <Mic className="size-4" />
                </button>
              )}
            </form>
          </div>
        </>
      )}
    </>
  );
}
