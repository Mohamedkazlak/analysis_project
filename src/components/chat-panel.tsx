import { useEffect, useRef, useState } from "react";
import { MessageCircle, Mic, Send, Square, Volume2, X } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Role } from "@/lib/types";
import { askAssistant } from "@/lib/ai/assistant";
import { synthesizeSpeech, transcribeAudio } from "@/lib/ai/speech";
import { subscribeToChatOpen } from "@/lib/chat-bus";
import { useRole } from "./role-context";
import { speechLanguageForLocale, useLocale } from "@/lib/i18n";

type ChatMode = "text-text" | "voice-text" | "text-voice" | "voice-voice";

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

function usesVoiceInput(mode: ChatMode): boolean {
  return mode === "voice-text" || mode === "voice-voice";
}

function usesVoiceOutput(mode: ChatMode): boolean {
  return mode === "text-voice" || mode === "voice-voice";
}

interface Msg {
  id: number;
  from: "user" | "ai";
  text: string;
  blocked?: boolean;
}

export function ChatPanel() {
  const { role, user } = useRole();
  const { locale, messages: copy } = useLocale();
  const chat = copy.chat;
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [context, setContext] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [speechPending, setSpeechPending] = useState(false);
  const [recording, setRecording] = useState(false);
  const [mode, setMode] = useState<ChatMode>("text-text");
  const greeting = openerFor(
    role,
    user.name,
    chat.openers,
    chat.studentGreeting,
  );
  const identity = `${role}:${user.id}:${locale}`;
  const identityRef = useRef(identity);
  const [messages, setMessages] = useState<Msg[]>(() => [
    {
      id: 0,
      from: "ai",
      text: openerFor(role, user.name, chat.openers, chat.studentGreeting),
    },
  ]);
  const threadRef = useRef<HTMLDivElement>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const audioRef = useRef<HTMLAudioElement | null>(null);

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
  }, [messages, pending, speechPending, open]);

  useEffect(() => {
    return () => {
      recorderRef.current?.stop();
      streamRef.current?.getTracks().forEach((track) => track.stop());
      audioRef.current?.pause();
    };
  }, []);

  const addError = (text: string) => {
    setMessages((items) => [
      ...items,
      {
        id: Date.now(),
        from: "ai",
        text,
      },
    ]);
  };

  const playSpeech = async (text: string) => {
    setSpeechPending(true);
    try {
      audioRef.current?.pause();
      const blob = await synthesizeSpeech(
        text,
        speechLanguageForLocale(locale),
      );
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audioRef.current = audio;
      audio.addEventListener(
        "ended",
        () => {
          URL.revokeObjectURL(url);
        },
        { once: true },
      );
      await audio.play();
    } finally {
      setSpeechPending(false);
    }
  };

  const send = async (question: string) => {
    const text = question.trim();
    if (!text || pending) return;
    setInput("");
    setMessages((m) => [...m, { id: Date.now(), from: "user", text }]);
    setPending(true);
    try {
      const answer = await askAssistant(text);
      setMessages((m) => [
        ...m,
        {
          id: Date.now() + 1,
          from: "ai",
          text: answer.text,
          blocked: answer.blocked,
        },
      ]);

      if (!answer.blocked && usesVoiceOutput(mode)) {
        try {
          await playSpeech(answer.text);
        } catch {
          addError(chat.voicePlaybackUnavailable);
        }
      }
    } catch {
      addError(chat.notUnderstood);
    } finally {
      setPending(false);
    }
  };

  const startRecording = async () => {
    if (recording || pending || speechPending) return;

    if (!navigator.mediaDevices?.getUserMedia) {
      addError(chat.micUnsupported);
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: true,
      });
      streamRef.current = stream;
      chunksRef.current = [];

      const recorder = new MediaRecorder(stream);
      recorderRef.current = recorder;

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };

      recorder.onstop = async () => {
        setRecording(false);
        setSpeechPending(true);
        try {
          const blob = new Blob(chunksRef.current, {
            type: recorder.mimeType || "audio/webm",
          });
          const result = await transcribeAudio(blob);
          await send(result.text);
        } catch {
          addError(chat.recordingFailed);
        } finally {
          setSpeechPending(false);
          stream.getTracks().forEach((track) => track.stop());
          streamRef.current = null;
          recorderRef.current = null;
          chunksRef.current = [];
        }
      };

      recorder.start();
      setRecording(true);
    } catch {
      addError(chat.micDenied);
    }
  };

  const stopRecording = () => {
    if (recorderRef.current && recorderRef.current.state !== "inactive") {
      recorderRef.current.stop();
    }
  };

  return (
    <>
      {!open && (
        <button
          onClick={() => setOpen(true)}
          className="rise-in fixed bottom-6 end-6 z-40 flex items-center gap-2 rounded-full bg-ai px-4 py-3 text-[13px] font-semibold text-white shadow-xl shadow-ai/30 transition-transform hover:scale-[1.02]"
        >
          <MessageCircle className="size-4" />
          {chat.askAi}
        </button>
      )}

      {open && (
        <div className="rise-in fixed bottom-6 end-6 z-50 flex h-[min(620px,85vh)] w-[min(420px,calc(100vw-2rem))] flex-col overflow-hidden rounded-3xl border border-white/80 bg-white/95 shadow-2xl backdrop-blur-xl">
          <div className="flex items-center justify-between border-b border-black/5 px-4 py-3">
            <div>
              <div className="text-[13px] font-semibold text-ink">
                {chat.headers[role]}
              </div>
              {context && (
                <div className="text-[11px] text-ink-soft">{context}</div>
              )}
            </div>
            <button
              onClick={() => setOpen(false)}
              className="rounded-full p-1.5 text-ink-soft hover:bg-black/5"
            >
              <X className="size-4" />
            </button>
          </div>

          <div className="border-b border-black/5 px-3 py-2">
            <select
              value={mode}
              disabled={recording || pending}
              onChange={(event) => setMode(event.target.value as ChatMode)}
              className="w-full rounded-xl border border-black/10 bg-white px-3 py-2 text-[12px] font-medium text-ink outline-none focus:border-ai/50"
            >
              {(Object.keys(chat.modes) as ChatMode[]).map((item) => (
                <option key={item} value={item}>
                  {chat.modes[item]}
                </option>
              ))}
            </select>
          </div>

          <div
            ref={threadRef}
            className="flex-1 space-y-3 overflow-y-auto scroll-smooth px-4 py-3"
          >
            {messages.map((m) => (
              <div
                key={m.id}
                className={cn(
                  "flex max-w-[90%] items-start gap-2 break-words rounded-2xl px-3.5 py-2.5 text-[13px] leading-relaxed",
                  m.from === "user"
                    ? "ml-auto bg-iris text-white"
                    : m.blocked
                      ? "bg-rose/10 text-rosee"
                      : "bg-iris/8 text-ink",
                )}
              >
                <span className="flex-1">{m.text}</span>
                {m.from === "ai" && !m.blocked && (
                  <button
                    type="button"
                    title={chat.playAnswer}
                    disabled={speechPending}
                    onClick={() => playSpeech(m.text)}
                    className="mt-0.5 shrink-0 rounded-full p-1 text-ai hover:bg-ai/10 disabled:opacity-40"
                  >
                    <Volume2 className="size-3.5" />
                  </button>
                )}
              </div>
            ))}
            {pending && (
              <div className="text-[12px] text-ink-soft">{chat.thinking}</div>
            )}
            {speechPending && !pending && (
              <div className="text-[12px] text-ink-soft">
                {chat.processingVoice}
              </div>
            )}
          </div>

          <div className="flex flex-wrap gap-1.5 border-t border-black/5 px-3 py-2">
            {(chat.suggestions[role] ?? []).map((suggestion) => (
              <button
                key={suggestion}
                disabled={pending || recording}
                onClick={() => send(suggestion)}
                className="rounded-full border border-ai/30 bg-ai/5 px-2.5 py-1 text-[11px] font-medium text-ai disabled:opacity-40"
              >
                {suggestion}
              </button>
            ))}
          </div>

          <form
            className="flex items-center gap-2 border-t border-black/5 px-3 py-3"
            onSubmit={(e) => {
              e.preventDefault();
              if (!usesVoiceInput(mode)) send(input);
            }}
          >
            {!usesVoiceInput(mode) && (
              <>
                <input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder={chat.placeholder}
                  className="flex-1 rounded-full border border-black/10 bg-white px-3.5 py-2 text-[13px] outline-none focus:border-ai/50"
                />
                <button
                  type="submit"
                  disabled={pending || !input.trim()}
                  className="grid size-9 place-items-center rounded-full bg-ai text-white disabled:opacity-40"
                >
                  <Send className="size-4" />
                </button>
              </>
            )}

            {usesVoiceInput(mode) && (
              <>
                <div className="flex-1 rounded-full border border-black/10 bg-white px-3.5 py-2 text-[13px] text-ink-soft">
                  {recording ? chat.listening : chat.voiceHint}
                </div>
                {!recording ? (
                  <button
                    type="button"
                    disabled={pending || speechPending}
                    onClick={startRecording}
                    className="grid size-9 place-items-center rounded-full bg-ai text-white disabled:opacity-40"
                  >
                    <Mic className="size-4" />
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={stopRecording}
                    className="grid size-9 place-items-center rounded-full bg-rose-600 text-white"
                  >
                    <Square className="size-4" />
                  </button>
                )}
              </>
            )}
          </form>
        </div>
      )}
    </>
  );
}
