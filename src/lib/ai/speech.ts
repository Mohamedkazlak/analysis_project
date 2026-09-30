import {
  ApiError,
  BACKEND_URL,
} from "../api";

import {
  clearAuthToken,
  getAuthToken,
} from "../auth/token";


function authHeaders(): Record<string, string> {
  const token = getAuthToken();

  if (!token) return {};

  return {
    Authorization: `Bearer ${token}`,
  };
}


function handleUnauthorized(
  response: Response,
): void {
  if (response.status !== 401) return;

  clearAuthToken();

  if (
    typeof window !== "undefined" &&
    window.location.pathname !== "/login"
  ) {
    window.location.href = "/login";
  }
}


export interface TranscriptionResult {
  text: string;
}


export async function transcribeAudio(
  audio: Blob,
): Promise<TranscriptionResult> {
  const form = new FormData();

  form.append(
    "file",
    audio,
    "recording.webm",
  );

  const response = await fetch(
    `${BACKEND_URL}/api/speech/transcribe`,
    {
      method: "POST",
      headers: authHeaders(),
      body: form,
    },
  );

  handleUnauthorized(response);

  if (!response.ok) {
    throw new ApiError(
      `Speech recognition failed: ${response.status}`,
      response.status,
    );
  }

  return (
    await response.json()
  ) as TranscriptionResult;
}


export type SpeechLanguage =
  | "auto"
  | "ar"
  | "en";


export async function synthesizeSpeech(
  text: string,
  language: SpeechLanguage = "auto",
): Promise<Blob> {
  const response = await fetch(
    `${BACKEND_URL}/api/speech/synthesize`,
    {
      method: "POST",
      headers: {
        ...authHeaders(),
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        text,
        language,
      }),
    },
  );

  handleUnauthorized(response);

  if (!response.ok) {
    throw new ApiError(
      `Speech synthesis failed: ${response.status}`,
      response.status,
    );
  }

  return await response.blob();
}