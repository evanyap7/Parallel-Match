import { describe, expect, it } from "vitest";
import rawMatch from "../../fixtures/m012.json";
import rawFork from "../../fixtures/fork_m012.json";
import { parseFork, parseMatch } from "./api";
import { alternateEvents, changesFor, eventAt, statsAt } from "./model";
import type { ForkRequest, MatchEvent } from "./types";

const match = parseMatch(rawMatch);
const request: ForkRequest = {
  match_id: rawFork.match_id,
  event_id: rawFork.event_id,
  change: { type: "flip_call" },
};
const fork = parseFork(rawFork, request);

describe("shared repository contracts", () => {
  it("loads the untouched match and binds the fork to the exact anchor", () => {
    const event = match.events.find((e) => e.id === request.event_id)!;
    expect(event.step).toBe(fork.divergence.step);
    expect(event.t).toBe(fork.divergence.t);
    expect(changesFor(event)).toContainEqual(request.change);
  });
  it("never invents an alternate when the shared fixture has no events", () => {
    expect(
      alternateEvents(match, {
        ...fork,
        alternate: { ...fork.alternate, timeline: [] },
      }),
    ).toEqual([]);
  });
  it("rejects a response for a different selected decision", () => {
    expect(() =>
      parseFork(rawFork, { ...request, event_id: "m012-other" }),
    ).toThrow();
    expect(() =>
      parseFork(rawFork, {
        ...request,
        change: { type: "not_sent_off" },
      }),
    ).toThrow();
  });
  it("rejects invalid probabilities, reversed uncertainty and malformed history", () => {
    const bad = structuredClone(rawFork);
    bad.original.win_prob[0].home = 4;
    expect(() => parseFork(bad, request)).toThrow();
    const reversed = structuredClone(rawFork);
    reversed.uncertainty.shift_ci95.home = [0.8, 0.2];
    expect(() => parseFork(reversed, request)).toThrow();
    expect(() => parseFork({ ...rawFork, history: {} }, request)).toThrow();
  });
  it("rejects unsorted or duplicated match events rather than misplaying them", () => {
    expect(() =>
      parseMatch({ ...rawMatch, events: [...rawMatch.events].reverse() }),
    ).toThrow();
    expect(() =>
      parseMatch({
        ...rawMatch,
        events: [rawMatch.events[0], rawMatch.events[0]],
      }),
    ).toThrow();
  });
});

describe("replay and statistics", () => {
  it("does not reveal future scores or statistics", () => {
    expect(eventAt(match.events, -1)).toBeUndefined();
    expect(eventAt(match.events, 0)?.score).toEqual([0, 0]);
    expect(statsAt(match, 0).shots).toEqual([0, 0]);
    const firstShot = match.events.find((e) => e.type === "shot")!;
    expect(statsAt(match, firstShot.t - 1).shots).toEqual([0, 0]);
  });
  it("uses the last event at an identical timestamp", () => {
    const a = {
      ...match.events[0],
      id: "a",
      t: 5,
      score: [0, 0],
    } as MatchEvent;
    const b = { ...a, id: "b", type: "goal", score: [1, 0] } as MatchEvent;
    expect(eventAt([a, b], 5)).toEqual(b);
  });
  it("counts attempts and completions separately, and xG from shots only", () => {
    const base = match.events[0];
    const events: MatchEvent[] = [
      { ...base, type: "pass", success: true, team: match.home },
      { ...base, type: "pass", success: false, team: match.home },
      { ...base, type: "shot", xg: 0.3, team: match.away },
      { ...base, type: "goal", xg: 0.3, team: match.away },
    ];
    expect(statsAt({ ...match, events }, 5)).toEqual({
      passes: [2, 0],
      completed: [1, 0],
      shots: [0, 1],
      xg: [0, 0.3],
    });
  });
  it("joins continuation-only fork events without duplicating the decision", () => {
    const replacement = {
      ...match.events.find((e) => e.id === request.event_id)!,
      call: "no_foul",
    };
    const result = alternateEvents(match, {
      ...fork,
      alternate: { ...fork.alternate, timeline: [replacement] },
    });
    expect(result.filter((e) => e.id === request.event_id)).toHaveLength(1);
    expect(result.at(-1)?.call).toBe("no_foul");
    expect(result.at(-2)?.id).not.toBe(request.event_id);
  });
  it("accepts a full alternate timeline without prepending the original again", () => {
    const result = alternateEvents(match, {
      ...fork,
      alternate: { ...fork.alternate, timeline: match.events },
    });
    expect(result).toHaveLength(match.events.length);
  });
});

// Run against all engine-owned cached interventions, including null precedent.
const cached = import.meta.glob("../../parallel_match/data/forks/**/*.json", {
  eager: true,
  import: "default",
});
describe("completed engine cache", () => {
  for (const [path, raw] of Object.entries(cached)) {
    it(`accepts ${path}`, () => {
      const r = raw as ForkRequest;
      const result = parseFork(raw, {
        match_id: r.match_id,
        event_id: r.event_id,
        change: r.change,
      });
      expect(result.alternate.timeline.length).toBeGreaterThan(0);
      expect(result.original.win_prob.length).toBeGreaterThan(0);
    });
  }
  it("replaces the entire shot/goal step, keeping no original event at the split", () => {
    const joined = alternateEvents(match, fork);
    expect(joined.filter((e) => e.step >= fork.divergence.step)).toEqual(
      fork.alternate.timeline,
    );
    expect(joined.at(-1)?.score).toEqual(fork.alternate.final_score);
  });
  it("accepts absent precedent for a non-officiating intervention", () => {
    expect(
      parseFork({ ...rawFork, history: null }, request).history,
    ).toBeNull();
  });
});
