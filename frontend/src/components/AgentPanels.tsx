import { useEffect, useState } from "react";
import { agentHealth, explain, narrate, precedents } from "../agents";
import type { AgentText } from "../agents";
import type { ForkResult, MatchEvent } from "../types";

function useAgent<T>(load: (signal: AbortSignal) => Promise<T>) {
  const [state, setState] = useState<{ data?: T; error?: string }>({});
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const ctrl = new AbortController();
    setState({});
    load(ctrl.signal)
      .then((data) => {
        if (!ctrl.signal.aborted) setState({ data });
      })
      .catch((e) => {
        if (!ctrl.signal.aborted)
          setState({
            error: e instanceof Error ? e.message : "Agent unavailable.",
          });
      });
    return () => ctrl.abort();
    // Components are keyed by their complete request identity in App.
  }, [retry]);
  return { ...state, retry: () => setRetry((n) => n + 1) };
}
function AgentState({ error, retry }: { error?: string; retry: () => void }) {
  return (
    <p className="small muted" role={error ? "status" : undefined}>
      {error ?? "Consulting the agent…"}{" "}
      {error && (
        <button className="text-button" onClick={retry}>
          Retry
        </button>
      )}
    </p>
  );
}
function Source({ data }: { data: { fell_back: boolean } }) {
  return (
    <span className="small-label">
      {data.fell_back ? "GUARDED TEMPLATE FALLBACK" : "AGENT SERVICE OUTPUT"}
    </span>
  );
}
export function AgentStatus() {
  const state = useAgent(agentHealth);
  return (
    <span className="agent-status">
      {state.data?.includes("template")
        ? "Agents: template mode"
        : state.data
          ? "Agents: Foundry"
          : state.error
            ? "Agents unavailable"
            : "Connecting agents…"}
    </span>
  );
}
export function AgentLaw({
  matchId,
  event,
}: {
  matchId: string;
  event: MatchEvent;
}) {
  const state = useAgent((signal) => explain(matchId, event.id, signal));
  return (
    <section className="agent-law" aria-label="Law Explainer">
      <h4>Law Explainer</h4>
      {state.data ? (
        <>
          <p>{state.data.text}</p>
          <Source data={state.data} />
        </>
      ) : (
        <AgentState {...state} />
      )}
    </section>
  );
}
export function AgentNarrative({ result }: { result: ForkResult }) {
  const state = useAgent((signal) => narrate(result, signal));
  return (
    <section className="agent-narrative card" aria-label="Narrator commentary">
      <div className="section-title">
        <h3>Narrator · full-match stories</h3>
        {state.data && <Source data={state.data} />}
      </div>
      {state.data ? (
        <div className="narrative-grid">
          {["real", "alternate"].map((side) => (
            <div key={side}>
              <span className="eyebrow muted">
                {side === "real"
                  ? "RECORDED TIMELINE"
                  : "ALTERNATE · MODEL WORLD"}
              </span>
              <p>
                {
                  state.data!.script.find((line) => line.timeline === side)
                    ?.text
                }
              </p>
            </div>
          ))}
        </div>
      ) : (
        <AgentState {...state} />
      )}
      <p className="small muted">
        Full-time summaries reveal both outcomes. Replay positions continue to
        follow the shared clock.
      </p>
    </section>
  );
}
export function historyAgreement(
  data: AgentText,
  result: ForkResult,
): boolean | null {
  const h = data.facts.history;
  if (h && typeof h === "object" && "agrees_with_simulation" in h)
    return (h as { agrees_with_simulation: boolean | null })
      .agrees_with_simulation;
  // Current dev-season Historian measures goals within 15 minutes; the engine
  // estimates final-result changes. Their directions are not interchangeable.
  return result.history?.agrees_with_simulation ?? null;
}
export function AgentHistory({ result }: { result: ForkResult }) {
  const state = useAgent((signal) =>
    precedents(result.match_id, result.event_id, signal),
  );
  const canonical = state.data?.facts.history;
  const aligned =
    canonical && typeof canonical === "object" && "when_given" in canonical;
  const agrees = state.data ? historyAgreement(state.data, result) : null;
  return (
    <section className="agent-history" aria-label="Historian agent">
      <div className="section-title">
        <h3>Historian</h3>
        {state.data && <Source data={state.data} />}
      </div>
      {state.data ? (
        <>
          <p>{state.data.text}</p>
          <p className="small muted">
            {aligned
              ? "Source: unified season precedent."
              : "Source: agents history query. The current service uses its development dataset and a different comparison method; its count may differ from the simulator above."}
          </p>
          {agrees !== null && (
            <p className={`agreement ${!agrees ? "disagrees" : ""}`}>
              {agrees
                ? "Simulation and season precedent agree in direction."
                : "These disagree: simulation and season precedent point in different directions."}{" "}
              {!aligned &&
                "This assessment uses the simulator’s season precedent, not the separate agent query."}
            </p>
          )}
        </>
      ) : (
        <AgentState {...state} />
      )}
    </section>
  );
}
