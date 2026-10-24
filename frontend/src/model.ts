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
  `${n > 0 ? "+" : ""}${(n * 100).toFixed(1)} pp`;
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
  if (event.changes) return event.changes;
  const changes: Change[] = [];
  if (event.contestable) changes.push({ type: "flip_call" });
  if (event.type === "card" && event.color === "red")
    changes.push({ type: "not_sent_off" });
  if (event.type === "goal")
    changes.push({ type: "shot_outcome", outcome: "saved" });
  if (
    event.type === "shot" &&
    ["saved", "off_target"].includes(event.outcome ?? "") &&
    (event.xg ?? 0) >= 0.15
  )
    changes.push({ type: "shot_outcome", outcome: "goal" });
  if (event.type === "substitution") changes.push({ type: "substitution" });
  return changes;
}
export function changeLabel(change: Change, event?: MatchEvent) {
  switch (change.type) {
    case "flip_call":
      return event?.call === "offside"
        ? "Play on: onside"
        : event?.call === "onside"
          ? "Flag offside"
          : event?.call === "no_foul"
            ? "Award the foul"
            : "Play on: no foul";
    case "not_sent_off":
      return "Keep the player on";
    case "shot_outcome":
      return change.outcome === "goal"
        ? "The shot goes in"
        : "The goal is saved";
    case "card":
      return change.card ? `Show a ${change.card} card` : "No card";
    case "substitution":
      return "Change a player";
    case "tactics":
      return "Change the pressing intensity";
  }
}
export function comparisonSummary(
  result: ForkResult,
  club: string,
  side: "home" | "away",
) {
  if (result.verdict) return result.verdict;
  const shift = result.outcome_shift[side];
  const interval = result.uncertainty.shift_ci95[side];
  return `${result.description}. Across ${result.rollouts} paired simulations, ${club}’s win chance ${shift < 0 ? "falls" : "rises"} by ${Math.abs(shift * 100).toFixed(1)} percentage points. ${interval[0] <= 0 && interval[1] >= 0 ? "The interval includes zero, so the direction remains uncertain." : "This is an estimate within the synthetic model world."}`;
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
  // The engine replaces an entire simulator step (e.g. shot + goal + red card),
  // not just the selected event. Keeping earlier events at that step duplicates outcomes.
  const prefix = match.events.filter((e) => e.step < result.divergence.step);
  return [...prefix, ...result.alternate.timeline];
}

// ---- view helpers ---------------------------------------------------------

/** How much a fan is likely to care about a moment (higher first). */
export function momentPriority(e: MatchEvent): number {
  if (e.type === "goal") return 10;
  if (e.type === "card" && e.color === "red") return 9;
  if (e.call === "penalty") return 9;
  if (e.type === "offside" || e.call === "onside")
    return 6 - 5 * Math.abs(e.margin ?? e.offside_margin ?? 1);
  if (e.contestable) return 4 - 10 * Math.abs(e.margin ?? 0.3);
  if (e.type === "shot") return 3;
  return 1;
}

/** The handful of moments the fan view shows, in match order. */
export function keyMoments(
  moments: MatchEvent[],
  limit = 8,
  keep?: string,
): MatchEvent[] {
  const ranked = [...moments]
    .sort((a, b) => momentPriority(b) - momentPriority(a))
    .slice(0, limit);
  const chosen =
    !keep || ranked.some((e) => e.id === keep)
      ? ranked
      : [
          ...ranked.slice(0, limit - 1),
          ...moments.filter((e) => e.id === keep),
        ];
  return chosen.sort((a, b) => a.t - b.t);
}

/** A short plain-language name for a moment, for fans. */
export function momentHeadline(e: MatchEvent): string {
  const who = e.player ? `${e.player} (${e.team})` : (e.team ?? "");
  if (e.type === "goal") return `Goal for ${clubName(e.team ?? "")}`;
  if (e.type === "card")
    return `${e.color === "red" ? "Red" : "Yellow"} card for ${who}`;
  if (e.call === "penalty")
    return `Penalty given against ${clubName(e.team ?? "")}`;
  if (e.type === "foul") return `Foul given against ${who}`;
  if (e.call === "no_foul") return `Play on after a challenge by ${who}`;
  if (e.type === "offside") return `Offside flag against ${who}`;
  if (e.call === "onside") return `${who} judged onside`;
  if (e.type === "shot") return `Big chance for ${who}`;
  if (e.type === "substitution") return `${e.player} comes on for ${e.team}`;
  return readable(e.type);
}

/** Short tag for a moment marker. */
export function momentTag(e: MatchEvent): string {
  if (e.type === "goal") return "Goal";
  if (e.type === "card") return e.color === "red" ? "Red" : "Card";
  if (e.call === "penalty") return "Pen";
  if (e.type === "offside" || e.call === "onside") return "Offside";
  if (e.type === "shot") return "Chance";
  if (e.type === "substitution") return "Sub";
  return "Foul";
}

/** The fan's question for a change, in their words. */
export function whatIfQuestion(change: Change, event?: MatchEvent): string {
  switch (change.type) {
    case "flip_call":
      if (event?.call === "penalty") return "What if it wasn’t a penalty?";
      if (event?.call === "offside") return "What if it was onside?";
      if (event?.call === "onside") return "What if offside was flagged?";
      if (event?.call === "no_foul") return "What if the foul was given?";
      return "What if there was no foul?";
    case "not_sent_off":
      return "What if the player stayed on?";
    case "shot_outcome":
      return change.outcome === "goal"
        ? "What if it went in?"
        : "What if it was saved?";
    case "card":
      return change.card
        ? `What if it was a ${change.card} card?`
        : "What if there was no card?";
    case "substitution":
      return "What if you made the change?";
    case "tactics":
      return "What if they pressed harder?";
  }
}

/** Win chance for one side before and after the change, from the paired rollouts. */
export function winChance(result: ForkResult, side: "home" | "away") {
  const before = result.original.outcome?.[side];
  const after = result.alternate.outcome?.[side];
  return {
    before: before ?? null,
    after:
      after ??
      (before !== undefined ? before + result.outcome_shift[side] : null),
  };
}

/** Events of a timeline from a step onwards, for the divergence log. */
export function eventsFrom(events: MatchEvent[], step: number, limit: number) {
  return events
    .filter((e) => e.step >= step && e.type !== "pass" && e.type !== "dribble")
    .slice(0, limit);
}
