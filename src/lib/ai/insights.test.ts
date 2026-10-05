import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api";
import { getAiDecision } from "@/lib/ai/insights";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    fetchFromBackend: vi.fn(),
  };
});

import { fetchFromBackend } from "@/lib/api";

const fetchMock = vi.mocked(fetchFromBackend);

describe("ai-insights combined decision", () => {
  beforeEach(() => {
    fetchMock.mockReset();
  });

  it("posts filters to the combined AI endpoint", async () => {
    fetchMock.mockResolvedValue({
      insight: { headline: "x", body: "y", action: null },
      prediction: {
        title: "Current standing",
        direction: "stable",
        summary: "not a forecast",
        rows: [],
        action: null,
        kind: "current_standing",
      },
      recommendations: { insightId: "insight", items: [] },
      status: "ok",
      message: null,
    });
    const result = await getAiDecision({
      sectorId: "sec-a",
      collegeId: "col-a",
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/ai/decision");
    expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({
      method: "POST",
      body: {
        sectorId: "sec-a",
        collegeId: "col-a",
        curriculumId: null,
        studentId: null,
        professorId: null,
        language: "en",
        page: "overview",
      },
    });
    expect(result.status).toBe("ok");
    expect(result.prediction?.kind).toBe("current_standing");
  });

  it("posts the page surface to the combined AI endpoint", async () => {
    fetchMock.mockResolvedValue({
      insight: { headline: "x", body: "y", action: null },
      prediction: null,
      recommendations: null,
      status: "ok",
      page: "courses",
      pageLabel: "Course performance analysis",
    });
    await getAiDecision({ collegeId: "col-a" }, "en", "courses");
    expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({
      body: {
        page: "courses",
        collegeId: "col-a",
      },
    });
  });

  it("returns a controlled timeout state instead of throwing", async () => {
    fetchMock.mockRejectedValue(new ApiError("Request timed out", 408));
    const result = await getAiDecision({
      sectorId: "sec-a",
      collegeId: "col-a",
    });
    expect(result.status).toBe("timeout");
    expect(result.insight).toBeNull();
    expect(result.message).toMatch(/longer than expected/i);
  });
});
