import { expect, it } from "vitest";
import { availablePlayers } from "./DecisionControls";
import { parseMatch } from "../api";
import rawMatch from "../../../fixtures/m052.json";
import type { Club, MatchEvent } from "../types";

it("offers only active players and unused substitutes before the fork step", () => {
  const club: Club = {
    code: "WES",
    name: "Westfield Rangers",
    squad: Array.from({ length: 13 }, (_, i) => ({
      id: `W${i + 1}`,
      name: `Player ${i + 1}`,
      pos: "MID",
      number: i + 1,
    })),
  };
  const match = parseMatch(rawMatch);
  const base = match.events[0];
  const events: MatchEvent[] = [
    {
      ...base,
      step: 2,
      team: "WES",
      type: "substitution",
      off: "W2",
      player: "W12",
    },
    { ...base, step: 3, team: "WES", type: "card", color: "red", player: "W3" },
    {
      ...base,
      step: 4,
      team: "WES",
      type: "substitution",
      off: "W4",
      player: "W13",
    },
  ];
  const result = availablePlayers(club, { ...match, events }, 4);
  expect(result.on.map((p) => p.id)).toContain("W12");
  expect(result.on.map((p) => p.id)).toContain("W4");
  expect(result.on.map((p) => p.id)).not.toContain("W2");
  expect(result.on.map((p) => p.id)).not.toContain("W3");
  expect(result.bench.map((p) => p.id)).toEqual(["W13"]);
});
