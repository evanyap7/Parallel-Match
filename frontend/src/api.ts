import type {
  Club,
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
export const fixtureEvents: Record<string, string> = {
  m012: "m012-0302",
  m052: "m052-0715",
};
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
      !finite(p.minute) ||
      p.minute < prev ||
      !probability(p.home) ||
      !probability(p.draw) ||
      !probability(p.away)
    )
      return false;
    prev = p.minute;
    return Math.abs(p.home + p.draw + p.away - 1) < 0.02;
  });
}
// Structural comparison tolerates JSON key order, but never a different intervention.
function sameChange(a: unknown, b: unknown): boolean {
  if (object(a) && object(b)) {
    const keys = Object.keys(a);
    return (
      keys.length === Object.keys(b).length &&
      keys.every((k) => k in b && sameChange(a[k], b[k]))
    );
  }
  return a === b;
}
export function parseFork(value: unknown, request: ForkRequest): ForkResult {
  const fail = () => {
    throw new Error(
      "The fork response is incomplete or does not match this decision. No alternate result has been displayed.",
    );
  };
  if (!object(value)) return fail();
  const d = value.divergence,
    o = value.original,
    a = value.alternate;
  const u = value.uncertainty,
    h = value.history,
    shift = value.outcome_shift;
  const interval = (v: unknown) => pair(v) && v[0] <= v[1];
  const rates = (v: unknown) =>
    object(v) &&
    finite(v.n) &&
    v.n >= 0 &&
    (v.win === null || probability(v.win));
  if (
    value.match_id !== request.match_id ||
    value.event_id !== request.event_id ||
    !sameChange(value.change, request.change) ||
    value.model_world !== true ||
    typeof value.description !== "string" ||
    typeof value.diverged !== "boolean" ||
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
    !object(u.shift_ci95) ||
    !["home", "draw", "away"].every((k) =>
      interval((u.shift_ci95 as Obj)[k]),
    ) ||
    (h !== null &&
      (!object(h) ||
        !finite(h.n) ||
        h.n < 0 ||
        typeof h.description !== "string" ||
        typeof h.attacking_team !== "string" ||
        !rates(h.when_given) ||
        !rates(h.when_not_given) ||
        ![true, false, null].includes(
          h.agrees_with_simulation as boolean | null,
        ))) ||
    !object(shift) ||
    ![shift.home, shift.draw, shift.away].every(
      (x) => finite(x) && Math.abs(x) <= 1,
    ) ||
    Math.abs(
      (shift.home as number) + (shift.draw as number) + (shift.away as number),
    ) > 0.02 ||
    !finite(value.rollouts) ||
    value.rollouts < 10 ||
    (value.verdict != null && typeof value.verdict !== "string") ||
    !Array.isArray(value.score_spread) ||
    !value.score_spread.every(
      (s) => object(s) && score(s.score) && probability(s.share),
    )
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
  if (!response.ok) {
    const problem = await response.json().catch(() => null);
    const detail =
      object(problem) && typeof problem.detail === "string"
        ? problem.detail
        : "Check the API connection and try again.";
    throw new Error(`Request failed (${response.status}). ${detail}`);
  }
  return response.json();
}
export async function getMatches(signal: AbortSignal): Promise<MatchSummary[]> {
  if (sourceMode === "fixtures")
    return [
      { match_id: "m052", home: "WES", away: "COP", story: "penalty_drama" },
      { match_id: "m012", home: "IRO", away: "LAR" },
    ];
  const result = await requestJSON(`${base}/matches`, signal);
  const list = Array.isArray(result)
    ? result
    : object(result) && Array.isArray(result.matches)
      ? result.matches
      : null;
  if (!list || !list.every((m) => object(m) && typeof m.match_id === "string"))
    throw new Error("GET /matches must return matches with a match_id.");
  return (list as MatchSummary[]).sort(
    (a, b) => Number(Boolean(b.story)) - Number(Boolean(a.story)),
  );
}
export async function getMatch(id: string, signal: AbortSignal) {
  return parseMatch(
    await requestJSON(
      sourceMode === "api"
        ? `${base}/match/${encodeURIComponent(id)}`
        : `/fixtures/${encodeURIComponent(id)}.json`,
      signal,
    ),
  );
}
export async function getFork(request: ForkRequest, signal: AbortSignal) {
  if (
    sourceMode === "fixtures" &&
    (request.event_id !== fixtureEvents[request.match_id] ||
      request.change.type !== "flip_call")
  ) {
    throw new Error(
      "This fixture only covers the featured decision. Connect the live API to explore another alternative.",
    );
  }
  const result = await requestJSON(
    sourceMode === "api"
      ? `${base}/fork`
      : `/fixtures/fork_${encodeURIComponent(request.match_id)}.json`,
    signal,
    sourceMode === "api" ? request : undefined,
  );
  return parseFork(result, request);
}

export async function getMoments(
  id: string,
  signal: AbortSignal,
): Promise<MatchEvent[]> {
  const result = await requestJSON(
    `${base}/moments/${encodeURIComponent(id)}`,
    signal,
  );
  if (
    !eventsValid(result) ||
    !result.every(
      (e) =>
        Array.isArray(e.changes) &&
        e.changes.every(
          (c) =>
            c &&
            [
              "flip_call",
              "not_sent_off",
              "shot_outcome",
              "substitution",
            ].includes(c.type),
        ),
    )
  )
    throw new Error("The moments response does not match docs/api.md.");
  return result;
}
export async function getClubs(signal: AbortSignal): Promise<Club[]> {
  const result = await requestJSON(`${base}/clubs`, signal);
  if (
    !Array.isArray(result) ||
    !result.every(
      (c) =>
        object(c) &&
        typeof c.code === "string" &&
        typeof c.name === "string" &&
        Array.isArray(c.squad) &&
        c.squad.every(
          (p) =>
            object(p) && typeof p.id === "string" && typeof p.name === "string",
        ),
    )
  )
    throw new Error("The clubs response is incomplete.");
  return result as Club[];
}
