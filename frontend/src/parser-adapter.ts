import type { Change, MatchEvent } from "./types";
// Deliberately small compatibility table: remove a foul, invert offside, or score a missed shot.
export function toEngineChange(
  parsed: Record<string, unknown>,
  event: MatchEvent,
): Change {
  if (parsed.type === "flip_call") {
    const wanted = parsed.call;
    if (
      (event.type === "foul" &&
        ["free_kick", "penalty"].includes(event.call ?? "") &&
        wanted === "no_foul") ||
      (event.call === "offside" && wanted === "onside") ||
      (event.call === "onside" && wanted === "offside")
    )
      return { type: "flip_call" };
  }
  if (
    parsed.type === "shot_outcome" &&
    parsed.outcome === "goal" &&
    event.type === "shot" &&
    ["saved", "off_target", "blocked"].includes(event.outcome ?? "")
  )
    return { type: "shot_outcome", outcome: "goal" };
  throw new Error(
    `Parser returned an unsupported change: ${JSON.stringify(parsed)}. Use the typed alternatives instead. No simulation was sent.`,
  );
}
