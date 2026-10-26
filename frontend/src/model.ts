import type { Change, ForkResult, MatchEvent, Match, Score } from "./types";
import { en } from "./i18n/en";
import { tEn, type T } from "./i18n";

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
/** An event field value (type, call, kind, outcome) in the reader's language. */
export const word = (s: string, t: T = tEn) =>
  `v.${s}` in en ? t(`v.${s}` as keyof typeof en) : readable(s);
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
export function changeLabel(change: Change, event?: MatchEvent, t: T = tEn) {
  switch (change.type) {
    case "flip_call":
      return event?.call === "offside"
        ? t("chg.onside")
        : event?.call === "onside"
          ? t("chg.flagOffside")
          : event?.call === "no_foul"
            ? t("chg.awardFoul")
            : t("chg.noFoul");
    case "not_sent_off":
      return t("chg.keepOn");
    case "shot_outcome":
      return change.outcome === "goal" ? t("chg.shotIn") : t("chg.goalSaved");
    case "card":
      return change.card
        ? t("chg.showCard", { card: word(change.card, t) })
        : t("chg.noCard");
    case "substitution":
      return t("chg.sub");
    case "tactics":
      return t("chg.tactics");
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
export function describe(event?: MatchEvent, t: T = tEn) {
  if (!event) return t("desc.wait");
  const subject = event.player
    ? `${event.team ?? ""} · ${event.player}`
    : (event.team ?? t("desc.match"));
  if (event.type === "goal") return t("desc.scores", { subject });
  if (event.type === "pass") {
    const kind = word(event.kind ?? "pass", t);
    return t(event.success === false ? "desc.intercepted" : "desc.pass", {
      subject,
      kind,
    });
  }
  if (event.type === "shot")
    return t("desc.shot", { subject, outcome: word(event.outcome ?? "", t) });
  if (event.type === "substitution")
    return t("desc.sub", {
      team: event.team ?? "",
      on: event.player ?? "",
      off: event.off ?? "",
    });
  return (
    t("desc.other", { subject, type: word(event.type, t) }) +
    (event.call ? t("desc.call", { call: word(event.call, t) }) : "")
  );
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
export function momentHeadline(e: MatchEvent, t: T = tEn): string {
  const who = e.player ? `${e.player} (${e.team})` : (e.team ?? "");
  const team = clubName(e.team ?? "");
  if (e.type === "goal") return t("mom.goal", { team });
  if (e.type === "card") return t(e.color === "red" ? "mom.red" : "mom.yellow", { who });
  if (e.call === "penalty") return t("mom.penalty", { team });
  if (e.type === "foul") return t("mom.foul", { who });
  if (e.call === "no_foul") return t("mom.noFoul", { who });
  if (e.type === "offside") return t("mom.offside", { who });
  if (e.call === "onside") return t("mom.onside", { who });
  if (e.type === "shot") return t("mom.chance", { who });
  if (e.type === "substitution")
    return t("mom.sub", { player: e.player ?? "", team: e.team ?? "" });
  return word(e.type, t);
}

/** Short tag for a moment marker. */
export function momentTag(e: MatchEvent, t: T = tEn): string {
  if (e.type === "goal") return t("tag.goal");
  if (e.type === "card") return e.color === "red" ? t("tag.red") : t("tag.card");
  if (e.call === "penalty") return t("tag.pen");
  if (e.type === "offside" || e.call === "onside") return t("tag.offside");
  if (e.type === "shot") return t("tag.chance");
  if (e.type === "substitution") return t("tag.sub");
  return t("tag.foul");
}

/** The fan's question for a change, in their words. */
export function whatIfQuestion(
  change: Change,
  event?: MatchEvent,
  t: T = tEn,
): string {
  switch (change.type) {
    case "flip_call":
      if (event?.call === "penalty") return t("q.noPenalty");
      if (event?.call === "offside") return t("q.onside");
      if (event?.call === "onside") return t("q.offside");
      if (event?.call === "no_foul") return t("q.foul");
      return t("q.noFoul");
    case "not_sent_off":
      return t("q.stayed");
    case "shot_outcome":
      return change.outcome === "goal" ? t("q.wentIn") : t("q.saved");
    case "card":
      return change.card
        ? t("q.card", { card: word(change.card, t) })
        : t("q.noCard");
    case "substitution":
      return t("q.sub");
    case "tactics":
      return t("q.press");
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
