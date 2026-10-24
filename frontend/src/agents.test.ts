import { afterEach, expect, it, vi } from "vitest";
import { toEngineChange } from "./parser-adapter";
import { narrate, narratorBody, parseWhatIf, validateText } from "./agents";
import { historyAgreement } from "./components/AgentPanels";
import rawFork from "../../fixtures/fork_m052.json";
import narration from "../fixtures/agents/narrate.json";
import law from "../fixtures/agents/explain.json";
import history from "../fixtures/agents/precedents.json";
import type { ForkResult, MatchEvent } from "./types";
const fork = rawFork as unknown as ForkResult;
const event = fork.moment as MatchEvent;
afterEach(() => vi.unstubAllGlobals());
it.each(["free_kick", "penalty"])("translates removal of %s only", (call) =>
  expect(
    toEngineChange(
      { type: "flip_call", call: "no_foul" },
      { ...event, type: "foul", call },
    ),
  ).toEqual({ type: "flip_call" }),
);
it.each([
  ["offside", "onside"],
  ["onside", "offside"],
])("translates %s to %s", (call, wanted) =>
  expect(
    toEngineChange({ type: "flip_call", call: wanted }, { ...event, call }),
  ).toEqual({ type: "flip_call" }),
);
it("allows only a supported missed shot to become a goal", () =>
  expect(
    toEngineChange(
      { type: "shot_outcome", outcome: "goal" },
      { ...event, type: "shot", outcome: "saved" },
    ),
  ).toEqual({ type: "shot_outcome", outcome: "goal" }));
it.each([
  { type: "card", color: "red" },
  { type: "shot_outcome", outcome: "missed" },
  { type: "flip_call", call: "penalty" },
  { type: "substitution" },
  { type: "flip_call", call: "no_foul" },
])(
  "refuses unsupported or already-recorded changes without guessing: %j",
  (change) =>
    expect(() => toEngineChange(change, { ...event, call: "no_foul" })).toThrow(
      "No simulation was sent",
    ),
);
it("validates real agent response samples and rejects a stale event", () => {
  expect(validateText(law, event.id).text).toBeTruthy();
  expect(validateText(history, event.id).text).toBeTruthy();
  expect(() => validateText(law, "other")).toThrow();
});
it("adds the documented legacy envelope without altering outcome data", () => {
  const body = narratorBody(fork);
  expect(body.fork_response.request.change).toEqual(fork.change);
  expect(body.fork_response.original).toBe(fork.original);
});
it("binds narrator output to the requested comparison", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response(JSON.stringify(narration))),
  );
  expect((await narrate(fork, new AbortController().signal)).event_id).toBe(
    event.id,
  );
});
it("preserves the parser refusal verbatim", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValue(
        new Response(
          JSON.stringify({
            ok: false,
            reason: "the recorded call was already penalty",
          }),
        ),
      ),
  );
  await expect(
    parseWhatIf("penalty", fork, new AbortController().signal),
  ).rejects.toThrow("the recorded call was already penalty");
});
it("does not equate development-history goal rates with paired win shifts", () => {
  const result = {
    ...fork,
    history: { ...fork.history!, agrees_with_simulation: false },
  };
  expect(historyAgreement(validateText(history, event.id), result)).toBe(false);
});
