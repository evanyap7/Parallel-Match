import type {
  ForkRequest,
  ForkResult,
  Match,
  MatchEvent,
  MatchSummary,
} from "./types";

const configuredBase = import.meta.env.VITE_API_BASE_URL?.trim().replace(
  /\/$/,
  "",
);
export const sourceMode = configuredBase ? "api" : "fixtures";
export const fixtureEventId = "m012-0148";
const base = configuredBase ?? "";
type Obj = Record<string, unknown>;
function object(value: unknown): value is Obj {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function finite(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}
function pair(value: unknown): value is [number, number] {
  return Array.isArray(value) && value.length === 2 && value.every(finite);
}
function score(value: unknown) {
  return pair(value) && value.every((x) => Number.isInteger(x) && x >= 0);
}
function probability(value: unknown): value is number {
  return finite(value) && value >= 0 && value <= 1;
}
function eventsValid(value: unknown): value is MatchEvent[] {
  if (!Array.isArray(value)) return false;
  const ids = new Set<string>();
  let previous = -1;
  return value.every((e) => {
    if (
      !object(e) ||
      typeof e.id !== "string" ||
      ids.has(e.id) ||
      typeof e.type !== "string" ||
      !finite(e.t) ||
      e.t < previous ||
      !finite(e.step) ||
      typeof e.min !== "string" ||
      !finite(e.period) ||
      !score(e.score)
    )
      return false;
    if (
      e.xy !== undefined &&
      (!pair(e.xy) ||
        e.xy[0] < 0 ||
        e.xy[0] > 105 ||
        e.xy[1] < 0 ||
        e.xy[1] > 68)
    )
      return false;
    if (e.xg !== undefined && !probability(e.xg)) return false;
    ids.add(e.id);
    previous = e.t;
    return true;
  });
}
export function parseMatch(value: unknown): Match {
  if (
    !object(value) ||
    typeof value.match_id !== "string" ||
    typeof value.home !== "string" ||
    typeof value.away !== "string" ||
    !score(value.score) ||
    !eventsValid(value.events) ||
    !value.events.length
  ) {
    throw new Error(
      "The match response does not match docs/event-schema.md. Check the API contract.",
    );
  }
  return value as unknown as Match;
}
function curveValid(value: unknown) {
  if (!Array.isArray(value)) return false;
  let prev = -1;
  return value.every((p) => {
    if (
      !object(p) ||
      !finite(p.min) ||
      p.min < prev ||
      !probability(p.home) ||
      !probability(p.draw) ||
      !probability(p.away)
    )
      return false;
    prev = p.min;
    return Math.abs(p.home + p.draw + p.away - 1) < 0.02;
  });
}
export function parseFork(value: unknown, request: ForkRequest): ForkResult {
  const fail = () => {
    throw new Error(
      "The fork response is incomplete or does not match this decision. No alternate result has been displayed.",
    );
  };
  if (!object(value)) return fail();
  const r = value.request,
    d = value.divergence,
    o = value.original,
    a = value.alternate;
  const u = value.uncertainty,
    h = value.history,
    shift = value.outcome_shift;
  if (
    !object(r) ||
    !object(r.change) ||
    r.match_id !== request.match_id ||
    r.event_id !== request.event_id ||
    r.change.type !== request.change.type ||
    r.change.call !== request.change.call ||
    !object(d) ||
    d.event_id !== request.event_id ||
    !finite(d.t) ||
    d.t < 0 ||
    !finite(d.step) ||
    typeof d.min !== "string" ||
    !object(o) ||
    !score(o.final_score) ||
    !curveValid(o.win_prob) ||
    !object(a) ||
    !score(a.final_score) ||
    !curveValid(a.win_prob) ||
    !eventsValid(a.timeline) ||
    !object(u) ||
    !pair(u.home_win_ci95) ||
    !u.home_win_ci95.every(probability) ||
    u.home_win_ci95[0] > u.home_win_ci95[1] ||
    !object(h) ||
    !finite(h.n) ||
    h.n < 0 ||
    !probability(h.home_win_share) ||
    typeof h.description !== "string" ||
    ![true, false, null].includes(h.agrees_with_simulation as boolean | null) ||
    !object(shift) ||
    ![shift.home, shift.draw, shift.away].every(
      (x) => finite(x) && Math.abs(x) <= 1,
    ) ||
    Math.abs(
      (shift.home as number) + (shift.draw as number) + (shift.away as number),
    ) > 0.02 ||
    !finite(value.rollouts) ||
    value.rollouts < 0 ||
    typeof value.verdict !== "string" ||
    (value.placeholder !== undefined && typeof value.placeholder !== "boolean")
  )
    return fail();
  return value as unknown as ForkResult;
}
async function requestJSON(
  path: string,
  signal: AbortSignal,
  body?: ForkRequest,
): Promise<unknown> {
  const response = await fetch(path, {
    signal: AbortSignal.any([signal, AbortSignal.timeout(60_000)]),
    ...(body
      ? {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }
      : {}),
  });
  if (!response.ok)
    throw new Error(
      `Request failed (${response.status}). Check the API connection and try again.`,
    );
  return response.json();
}
export async function getMatches(signal: AbortSignal): Promise<MatchSummary[]> {
  if (sourceMode === "fixtures")
    return [{ match_id: "m012", home: "HAR", away: "NOR" }];
  const result = await requestJSON(`${base}/matches`, signal);
  const list = Array.isArray(result)
    ? result
    : object(result) && Array.isArray(result.matches)
      ? result.matches
      : null;
  if (!list || !list.every((m) => object(m) && typeof m.match_id === "string"))
    throw new Error("GET /matches must return matches with a match_id.");
  return list as MatchSummary[];
}
export async function getMatch(id: string, signal: AbortSignal) {
  return parseMatch(
    await requestJSON(
      sourceMode === "api"
        ? `${base}/match/${encodeURIComponent(id)}`
        : "/fixtures/m012.json",
      signal,
    ),
  );
}
export async function getFork(request: ForkRequest, signal: AbortSignal) {
  if (
    sourceMode === "fixtures" &&
    (request.match_id !== "m012" ||
      request.event_id !== fixtureEventId ||
      request.change.call !== "no_foul")
  ) {
    throw new Error(
      "This fixture only covers the foul at 10′. Connect the live API to explore another decision.",
    );
  }
  const result = await requestJSON(
    sourceMode === "api" ? `${base}/fork` : "/fixtures/fork_m012.json",
    signal,
    sourceMode === "api" ? request : undefined,
  );
  return parseFork(result, request);
}
