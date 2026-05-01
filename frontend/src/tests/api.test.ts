/**
 * Tests for src/lib/api.ts
 *
 * Strategy: mock global fetch, call each exported function, assert that the
 * correct URL is built and the response is returned/thrown as expected.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  fetchAccuracyStats,
  fetchMe,
  fetchReport,
  fetchReportPredictions,
  fetchReports,
  fetchRun,
  fetchRuns,
  fetchSignalCard,
  fetchSignalPredictions,
  fetchSignals,
  fetchLatestSignal,
  sseStreamUrl,
  triggerRun,
  updateMe,
} from "@/lib/api";

// ── Setup ─────────────────────────────────────────────────────────────────────

const BASE = "http://localhost:8000/api/v1";

// Capture every fetch call
let fetchMock: ReturnType<typeof vi.fn>;

function mockOk(body: unknown) {
  fetchMock.mockResolvedValueOnce({
    ok: true,
    json: () => Promise.resolve(body),
  } as unknown as Response);
}

function mockFail(status: number, text = "Bad Request") {
  fetchMock.mockResolvedValueOnce({
    ok: false,
    status,
    statusText: text,
    text: () => Promise.resolve(text),
  } as unknown as Response);
}

beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

// ── Helpers ───────────────────────────────────────────────────────────────────

function lastUrl(): string {
  return (fetchMock.mock.calls[0][0] as string);
}

// ── Signals ───────────────────────────────────────────────────────────────────

describe("fetchSignals", () => {
  it("calls the correct base URL with no params", async () => {
    mockOk({ items: [], total: 0, page: 1, page_size: 12 });
    await fetchSignals();
    expect(lastUrl()).toBe(`${BASE}/signals/`);
  });

  it("appends ticker and signal query params", async () => {
    mockOk({ items: [], total: 0, page: 1, page_size: 12 });
    await fetchSignals({ ticker: "AAPL", signal: "BULLISH", page: 2 });
    const url = lastUrl();
    expect(url).toContain("ticker=AAPL");
    expect(url).toContain("signal=BULLISH");
    expect(url).toContain("page=2");
  });

  it("does not append empty optional params", async () => {
    mockOk({ items: [], total: 0, page: 1, page_size: 12 });
    await fetchSignals({ ticker: "" });
    expect(lastUrl()).not.toContain("ticker=");
  });
});

describe("fetchSignalCard", () => {
  it("calls /signals/{id}", async () => {
    mockOk({ id: 7 });
    await fetchSignalCard(7);
    expect(lastUrl()).toBe(`${BASE}/signals/7`);
  });
});

describe("fetchLatestSignal", () => {
  it("calls /signals/latest/{ticker}", async () => {
    mockOk({ id: 1, ticker: "AAPL" });
    await fetchLatestSignal("AAPL");
    expect(lastUrl()).toBe(`${BASE}/signals/latest/AAPL`);
  });
});

describe("fetchAccuracyStats", () => {
  it("calls /signals/accuracy", async () => {
    mockOk({ total: 0 });
    await fetchAccuracyStats();
    expect(lastUrl()).toBe(`${BASE}/signals/accuracy`);
  });
});

describe("fetchSignalPredictions", () => {
  it("calls /signals/{id}/predictions", async () => {
    mockOk([]);
    await fetchSignalPredictions(3);
    expect(lastUrl()).toBe(`${BASE}/signals/3/predictions`);
  });
});

// ── Reports ───────────────────────────────────────────────────────────────────

describe("fetchReports", () => {
  it("calls the correct base URL with no params", async () => {
    mockOk({ items: [], total: 0, page: 1, page_size: 20 });
    await fetchReports();
    expect(lastUrl()).toBe(`${BASE}/reports/`);
  });

  it("appends sector_id", async () => {
    mockOk({ items: [], total: 0, page: 1, page_size: 20 });
    await fetchReports({ sector_id: "technology" });
    expect(lastUrl()).toContain("sector_id=technology");
  });
});

describe("fetchReport", () => {
  it("calls /reports/{id}", async () => {
    mockOk({ id: 5 });
    await fetchReport(5);
    expect(lastUrl()).toBe(`${BASE}/reports/5`);
  });
});

describe("fetchReportPredictions", () => {
  it("calls /reports/{id}/predictions", async () => {
    mockOk([]);
    await fetchReportPredictions(5);
    expect(lastUrl()).toBe(`${BASE}/reports/5/predictions`);
  });
});

// ── Pipeline ─────────────────────────────────────────────────────────────────

describe("triggerRun", () => {
  it("sends POST to /pipeline/runs", async () => {
    mockOk({ run_id: "abc-123" });
    const result = await triggerRun({ ticker: "NVDA", sector_id: "semiconductors" });
    expect(fetchMock.mock.calls[0][0]).toBe(`${BASE}/pipeline/runs`);
    expect(fetchMock.mock.calls[0][1].method).toBe("POST");
    expect(result.run_id).toBe("abc-123");
  });

  it("sends the body as JSON", async () => {
    mockOk({ run_id: "xyz" });
    await triggerRun({ ticker: "TSLA", sector_id: "auto" });
    const body = JSON.parse(fetchMock.mock.calls[0][1].body as string);
    expect(body.ticker).toBe("TSLA");
    expect(body.sector_id).toBe("auto");
  });
});

describe("fetchRuns", () => {
  it("calls /pipeline/runs with no params", async () => {
    mockOk({ items: [], total: 0, page: 1, page_size: 20 });
    await fetchRuns();
    expect(lastUrl()).toBe(`${BASE}/pipeline/runs`);
  });

  it("appends ticker and status filters", async () => {
    mockOk({ items: [], total: 0, page: 1, page_size: 20 });
    await fetchRuns({ ticker: "AAPL", status: "completed" });
    expect(lastUrl()).toContain("ticker=AAPL");
    expect(lastUrl()).toContain("status=completed");
  });
});

describe("fetchRun", () => {
  it("calls /pipeline/runs/{run_id}", async () => {
    mockOk({ run_id: "abc" });
    await fetchRun("abc-123");
    expect(lastUrl()).toBe(`${BASE}/pipeline/runs/abc-123`);
  });
});

describe("sseStreamUrl", () => {
  it("returns the correct SSE URL without using fetch", () => {
    const url = sseStreamUrl("my-run-id");
    expect(url).toBe(`${BASE}/pipeline/runs/my-run-id/stream`);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

// ── Error handling ─────────────────────────────────────────────────────────────

describe("apiFetch error handling", () => {
  it("throws on non-ok response", async () => {
    mockFail(404, "Not Found");
    await expect(fetchSignalCard(999)).rejects.toThrow("404");
  });

  it("throws on 500 with server error text", async () => {
    mockFail(500, "Internal Server Error");
    await expect(fetchReport(1)).rejects.toThrow("500");
  });
});

// ── Users ──────────────────────────────────────────────────────────────────────

describe("fetchMe", () => {
  it("calls GET /users/me", async () => {
    const profile = {
      id: 1,
      email: "alice@example.com",
      username: "Alice",
      saved_sectors: [],
      preferences: {},
      created_at: "2026-01-01T00:00:00Z",
      updated_at: null,
    };
    mockOk(profile);
    const result = await fetchMe();
    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE}/users/me`,
      expect.any(Object)
    );
    expect(result.email).toBe("alice@example.com");
  });
});

describe("updateMe", () => {
  it("calls PATCH /users/me with body", async () => {
    const updated = {
      id: 1,
      email: "alice@example.com",
      username: "Alice",
      saved_sectors: ["semiconductors"],
      preferences: {},
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-04-30T00:00:00Z",
    };
    mockOk(updated);
    const result = await updateMe({ saved_sectors: ["semiconductors"] });
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`${BASE}/users/me`);
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(init.body as string)).toEqual({
      saved_sectors: ["semiconductors"],
    });
    expect(result.saved_sectors).toEqual(["semiconductors"]);
  });
});
