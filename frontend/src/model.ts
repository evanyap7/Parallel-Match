import type { Change, ForkResult, MatchEvent, Match, Score } from "./types";

export const CLUBS: Record<string, string> = {
  HAR: "Harbourside Rovers",
  NOR: "Northgate Athletic",
  STO: "Stonebridge City",
  KES: "Kestrel Wanderers",
  BRW: "Brightwater Albion",
  RED: "Redmere Town",
  IRO: "Ironvale United",
  WES: "Westfield Rangers",
  LAR: "Larkhill Borough",
  COP: "Copperfield FC",
};
export const clubName = (code: string) => CLUBS[code] ?? code;
export const percent = (n: number) => `${(n * 100).toFixed(0)}%`;
export const points = (n: number) =>
  `${n > 0 ? "+" : ""}${(n * 100).toFixed(0)} pp`;
export const scoreText = (score: Score) => `${score[0]} – ${score[1]}`;
export const readable = (s: string) => s.replaceAll("_", " ");
export function clockLabel(t: number) {
  const seconds = Math.max(0, Math.floor(t));
  return `${Math.floor(seconds / 60)
    .toString()
    .padStart(2, "0")}:${(seconds % 60).toString().padStart(2, "0")}`;
}
// Upper-bound search preserves event order when a shot and goal share a timestamp.
export function eventAt(
  events: MatchEvent[],
  t: number,
): MatchEvent | undefined {
  let lo = 0,
    hi = events.length;
  while (lo < hi) {
    const mid = (lo + hi) >>> 1;
    if (events[mid].t <= t) lo = mid + 1;
    else hi = mid;
  }
  return events[lo - 1];
}
export function changesFor(event: MatchEvent): Change[] {
  if (event.call === "free_kick" || event.call === "penalty")
    return [{ type: "flip_call", call: "no_foul" }];
  if (event.type === "offside" || event.call === "offside")
    return [{ type: "flip_call", call: "onside" }];
  if (event.call === "onside") return [{ type: "flip_call", call: "offside" }];
  if (event.call === "no_foul")
    return [{ type: "flip_call", call: "free_kick" }];
  return [];
}
export function describe(event?: MatchEvent) {
  if (!event) return "Waiting for kick-off";
  const subject = event.player
    ? `${event.team ?? ""} · ${event.player}`
    : (event.team ?? "Match");
  if (event.type === "goal") return `${subject} scores`;
  if (event.type === "pass")
    return `${subject} · ${readable(event.kind ?? "pass")}${event.success === false ? " intercepted" : " pass"}`;
  if (event.type === "shot")
    return `${subject} · shot ${readable(event.outcome ?? "")}`;
  if (event.type === "substitution")
    return `${event.team} · ${event.player} replaces ${event.off}`;
  return `${subject} · ${readable(event.type)}${event.call ? ` · ${readable(event.call)}` : ""}`;
}
export function statsAt(match: Match, t: number) {
  const stats = {
    shots: [0, 0],
    xg: [0, 0],
    passes: [0, 0],
    completed: [0, 0],
  };
  for (const e of match.events) {
    if (e.t > t) break;
    if (e.team !== match.home && e.team !== match.away) continue;
    const i = e.team === match.home ? 0 : 1;
    if (e.type === "shot") {
      stats.shots[i]++;
      stats.xg[i] += e.xg ?? 0;
    }
    if (e.type === "pass") {
      stats.passes[i]++;
      if (e.success) stats.completed[i]++;
    }
  }
  return stats;
}
// An empty alternate is missing evidence, never an invitation to replay the original as a fork.
export function alternateEvents(
  match: Match,
  result: ForkResult,
): MatchEvent[] {
  if (!result.alternate.timeline.length) return [];
  const first = result.alternate.timeline[0];
  if (first.t < result.divergence.t) return result.alternate.timeline;
  const anchor = match.events.findIndex(
    (e) => e.id === result.divergence.event_id,
  );
  const prefix =
    anchor >= 0
      ? match.events.slice(0, anchor)
      : match.events.filter((e) => e.t < result.divergence.t);
  return [...prefix, ...result.alternate.timeline];
}
