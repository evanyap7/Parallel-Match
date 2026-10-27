import type { ForkResult } from "./types";

const base =
  import.meta.env.VITE_AGENTS_BASE_URL?.trim().replace(/\/$/, "") || "/agents";
type Obj = Record<string, unknown>;
const obj = (v: unknown): v is Obj =>
  typeof v === "object" && v !== null && !Array.isArray(v);
export interface AgentText {
  event_id: string;
  text: string;
  facts: Obj;
  fell_back: boolean;
  /** True when the text is in the requested language; false means English was served. */
  translated?: boolean;
}
export interface Narration {
  match_id: string;
  event_id: string;
  script: { timeline: string; text: string }[];
  facts: Obj;
  fell_back: boolean;
  translated?: boolean;
}
export async function agentPost(
  path: string,
  body: unknown,
  signal: AbortSignal,
): Promise<unknown> {
  const response = await fetch(`${base}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal: AbortSignal.any([signal, AbortSignal.timeout(60000)]),
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    throw new Error(
      obj(detail) && typeof detail.detail === "string"
        ? detail.detail
        : `Agents service unavailable (${response.status}).`,
    );
  }
  return response.json();
}
export function validateText(value: unknown, eventId: string): AgentText {
  if (
    !obj(value) ||
    value.event_id !== eventId ||
    typeof value.text !== "string" ||
    !value.text.trim() ||
    !obj(value.facts) ||
    typeof value.fell_back !== "boolean"
  )
    throw new Error("Agent response does not match the selected moment.");
  return value as unknown as AgentText;
}
export async function explain(
  match_id: string,
  event_id: string,
  signal: AbortSignal,
  lang = "en",
) {
  return validateText(
    await agentPost("/explain", { match_id, event_id, lang }, signal),
    event_id,
  );
}
export async function precedents(
  match_id: string,
  event_id: string,
  signal: AbortSignal,
  lang = "en",
) {
  return validateText(
    await agentPost("/precedents", { match_id, event_id, lang }, signal),
    event_id,
  );
}
// The current agents reader expects a request envelope; preserve the engine's raw fields.
export function narratorBody(result: ForkResult, lang = "en") {
  return {
    lang,
    match_id: result.match_id,
    fork_response: {
      ...result,
      request: {
        match_id: result.match_id,
        event_id: result.event_id,
        change: result.change,
      },
    },
  };
}
export async function narrate(
  result: ForkResult,
  signal: AbortSignal,
  lang = "en",
): Promise<Narration> {
  const value = await agentPost("/narrate", narratorBody(result, lang), signal);
  if (
    !obj(value) ||
    value.match_id !== result.match_id ||
    value.event_id !== result.event_id ||
    !obj(value.facts) ||
    typeof value.fell_back !== "boolean" ||
    !Array.isArray(value.script) ||
    !["real", "alternate"].every((side) =>
      (value.script as unknown[]).some(
        (line: unknown) =>
          obj(line) &&
          line.timeline === side &&
          typeof line.text === "string" &&
          line.text.trim(),
      ),
    )
  )
    throw new Error("Narrator response does not match this comparison.");
  return value as unknown as Narration;
}
export interface DeskToolCall {
  tool: string;
  args: Obj;
  ok: boolean;
}
export interface DeskCheck {
  check: string;
  ok: boolean;
}
export interface DeskStep {
  role: string;
  status: string;
  ms: number;
  start_ms: number;
  plan?: string[];
  rejected?: string[];
  reviewer?: "agent" | "code";
  review_error?: string | null;
  tool_calls?: DeskToolCall[];
  consistency?: DeskCheck[];
  edited?: Record<string, string>;
  source?: string | null;
}
export interface DeskPiece {
  role: string;
  text: string;
  status: "approved" | "repaired" | "restored";
  issues: string[];
  translated: boolean;
}
/** The Match Desk: every agent on one moment, fact-checked, with a trace. */
export interface Desk {
  match_id: string;
  event_id: string;
  plan: string[];
  recap: { text: string; fell_back: boolean; translated: boolean };
  pieces: DeskPiece[];
  checks: {
    numbers_verified: number;
    tool_calls: number;
    consistency: DeskCheck[];
    agrees_with_simulation: boolean | null;
    precedent_source: string | null;
  };
  trace: DeskStep[];
  ms: number;
  fell_back: boolean;
  translated: boolean;
}
export async function desk(
  result: ForkResult,
  signal: AbortSignal,
  lang = "en",
): Promise<Desk> {
  const value = await agentPost("/desk", narratorBody(result, lang), signal);
  if (
    !obj(value) ||
    value.match_id !== result.match_id ||
    value.event_id !== result.event_id ||
    !obj(value.recap) ||
    typeof value.recap.text !== "string" ||
    !Array.isArray(value.pieces) ||
    !Array.isArray(value.trace) ||
    !obj(value.checks)
  )
    throw new Error("Agent desk response does not match this comparison.");
  return value as unknown as Desk;
}
export async function agentHealth(signal: AbortSignal): Promise<string> {
  const response = await fetch(`${base}/health`, {
    signal: AbortSignal.any([signal, AbortSignal.timeout(10000)]),
  });
  if (!response.ok) throw new Error("Agent status unavailable");
  const value = await response.json();
  if (!obj(value) || typeof value.provider !== "string")
    throw new Error("Agent status unavailable");
  return value.provider;
}
export async function parseWhatIf(
  text: string,
  request: { match_id: string; event_id: string },
  signal: AbortSignal,
  lang = "en",
) {
  const value = await agentPost("/parse", { ...request, text, lang }, signal);
  if (!obj(value) || typeof value.ok !== "boolean")
    throw new Error("Invalid parser response.");
  if (!value.ok)
    throw new Error(
      typeof value.reason === "string"
        ? value.reason
        : "This alternative is not supported.",
    );
  if (
    !obj(value.request) ||
    value.request.match_id !== request.match_id ||
    value.request.event_id !== request.event_id ||
    !obj(value.request.change)
  )
    throw new Error("Parser response refers to a different moment.");
  return value.request.change;
}
