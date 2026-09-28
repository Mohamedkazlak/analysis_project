import { fetchFromBackend, ApiError } from "../api";
import type { AnalyticsFilters } from "../filter-types";
import type { RecommendationSet } from "./recommendations";

export interface InsightEvidence {
  label: string;
  detail: string;
  weight: number;
}

export interface RiskCase {
  id: string;
  subject: string;
  exam: string;
  level: "Low" | "Medium" | "High";
  score: number;
  evidence: InsightEvidence[];
}

export interface Insight {
  headline: string;
  body: string;
  action: { label: string; to: string } | null;
  cases?: RiskCase[];
  warnings?: { id: string; text: string; tone: "amber" | "rose" }[];
}

export interface Prediction {
  title: string;
  direction: "rising" | "stable" | "falling";
  summary: string;
  rows: {
    label: string;
    value: string;
    tone: "mint" | "amber" | "rose" | "iris";
  }[];
  action: { label: string; to: string } | null;
  kind?: "current_standing" | "forecast";
}

export interface AiDecision {
  insight: Insight | null;
  prediction: Prediction | null;
  recommendations: RecommendationSet | null;
  status: "ok" | "timeout" | "unavailable";
  message?: string | null;
  /** "pending" while the LLM is still rewording the SQL sentences above. */
  narrationStatus?: "pending" | "done" | "skipped";
}

export const AI_REQUEST_TIMEOUT_MS = 12000;

export async function getAiDecision(
  filters: AnalyticsFilters,
): Promise<AiDecision> {
  try {
    return await fetchFromBackend<AiDecision>("/api/ai/decision", {
      method: "POST",
      body: {
        sectorId: filters.sectorId ?? null,
        collegeId: filters.collegeId ?? null,
        curriculumId: filters.curriculumId ?? null,
        studentId: filters.studentId ?? null,
        professorId: filters.professorId ?? null,
      },
      timeoutMs: AI_REQUEST_TIMEOUT_MS,
    });
  } catch (error) {
    const timedOut = error instanceof ApiError && error.status === 408;
    return {
      insight: null,
      prediction: null,
      recommendations: null,
      status: timedOut ? "timeout" : "unavailable",
      message: timedOut
        ? "AI analysis is taking longer than expected."
        : "AI analysis is temporarily unavailable.",
      narrationStatus: "skipped",
    };
  }
}
