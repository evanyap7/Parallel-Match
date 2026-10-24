import { afterEach, describe, expect, it, vi } from "vitest";
import match from "../../fixtures/m012.json";
import fork from "../../fixtures/fork_m012.json";
import type { ForkRequest } from "./types";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  vi.resetModules();
});

describe("live API adapter", () => {
  it("uses the planned GET and POST endpoints with the exact shared request", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "https://example.invalid/api/");
    vi.resetModules();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ matches: [{ match_id: "m012" }] })),
      )
      .mockResolvedValueOnce(new Response(JSON.stringify(match)))
      .mockResolvedValueOnce(new Response(JSON.stringify(fork)));
    vi.stubGlobal("fetch", fetchMock);
    const api = await import("./api");
    const signal = new AbortController().signal;
    expect(api.sourceMode).toBe("api");
    await api.getMatches(signal);
    await api.getMatch("m012", signal);
    await api.getFork(fork.request as ForkRequest, signal);
    expect(fetchMock.mock.calls.map((c) => c[0])).toEqual([
      "https://example.invalid/api/matches",
      "https://example.invalid/api/match/m012",
      "https://example.invalid/api/fork",
    ]);
    expect(fetchMock.mock.calls[2][1]).toMatchObject({
      method: "POST",
      body: JSON.stringify(fork.request),
      headers: { "Content-Type": "application/json" },
    });
  });
  it("reports service failures without silently serving fixture results", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "https://example.invalid");
    vi.resetModules();
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response("Unavailable", { status: 503 }));
    vi.stubGlobal("fetch", fetchMock);
    const api = await import("./api");
    await expect(
      api.getFork(fork.request as ForkRequest, new AbortController().signal),
    ).rejects.toThrow("503");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
  it("rejects unsupported fixture decisions before issuing a request", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "");
    vi.resetModules();
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const api = await import("./api");
    await expect(
      api.getFork(
        { ...fork.request, event_id: "different" } as ForkRequest,
        new AbortController().signal,
      ),
    ).rejects.toThrow("only covers");
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
