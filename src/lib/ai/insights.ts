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

export interface EvidenceMetric {
  id: string;
  name: string;
  entity?: string | null;
  value: number;
  unit: string;
  source: "deterministic_sql";
  dataset: string;
  comparison?: { name: string; scopeAverage?: number | null } | null;
}

export interface AiWarning {
  id: string;
  rule: string;
  severity: "low" | "medium" | "high";
  tone: "amber" | "rose";
  metric: string;
  entity?: string | null;
  value: number;
  threshold: number;
  text: string;
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
  method?: string | null;
  observations?: number | null;
  forecastValue?: number | null;
  intervalLow?: number | null;
  intervalHigh?: number | null;
}

export interface AiDecision {
  insight: Insight | null;
  prediction: Prediction | null;
  recommendations: RecommendationSet | null;
  warnings?: AiWarning[] | null;
  evidence?: EvidenceMetric[] | null;
  dataStatus?: "ready" | "insufficient";
  status: "ok" | "timeout" | "unavailable";
  message?: string | null;
  /** "pending" while the LLM is still rewording the SQL sentences above. */
  narrationStatus?: "pending" | "done" | "skipped";
  factPacket?: Record<string, unknown> | null;
  narrative?: {
    headline?: string;
    story?: string;
    captions?: Record<string, string>;
    source?: string;
  } | null;
  ruleAlerts?: Array<Record<string, unknown>> | null;
  anomalies?: Array<Record<string, unknown>> | null;
  impactItems?: Array<{
    id: string;
    issue: string;
    students_affected: number;
    gap_to_threshold: number;
    uplift_program: number;
    uplift_university: number;
    source: string;
    rank: number;
  }> | null;
  provenance?: {
    tables: string[];
    row_counts: Record<string, number>;
    updated_at: string;
  } | null;
  forecastStatus?: {
    kind: string;
    message: string;
    value?: number | null;
    low?: number | null;
    high?: number | null;
    observations?: number;
    needs_years?: number;
  } | null;
  evidenceQuality?: {
    quality: "strong" | "moderate" | "limited";
    label: string;
    score: number;
    reasons: string[];
  } | null;
  page?: string | null;
  pageLabel?: string | null;
}

export const AI_REQUEST_TIMEOUT_MS = 12000;

export async function getAiDecision(
  filters: AnalyticsFilters,
  language: "en" | "ar" = "en",
  page: string = "overview",
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
        academicYearId:
          (filters as { academicYearId?: string }).academicYearId ?? null,
        termId: (filters as { termId?: string }).termId ?? null,
        language,
        page,
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
      dataStatus: "insufficient",
      narrationStatus: "skipped",
      page,
    };
  }
}
