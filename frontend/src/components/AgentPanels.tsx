import { useEffect, useState } from "react";
import { agentHealth, explain, narrate, precedents } from "../agents";
import type { AgentText } from "../agents";
import { useI18n } from "../i18n";
import type { ForkResult, MatchEvent } from "../types";

function useAgent<T>(load: (signal: AbortSignal) => Promise<T>) {
  const { t } = useI18n();
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
            error: e instanceof Error ? e.message : t("agent.failed"),
          });
      });
    return () => ctrl.abort();
    // Components are keyed by their complete request identity in App.
  }, [retry]);
  return { ...state, retry: () => setRetry((n) => n + 1) };
}
function EnglishNote() {
  const { lang, t } = useI18n();
  return lang === "en" ? null : (
    <p className="small muted">{t("agent.englishNote")}</p>
  );
}
function AgentState({ error, retry }: { error?: string; retry: () => void }) {
  const { t } = useI18n();
  return (
    <p className="small muted" role="status">
      {error ?? t("agent.consulting")}{" "}
      {error && (
        <button className="text-button" onClick={retry}>
          {t("agent.retry")}
        </button>
      )}
    </p>
  );
}
function Source({ data }: { data: { fell_back: boolean } }) {
  const { t } = useI18n();
  return (
    <span className="small-label">
      {data.fell_back ? t("agent.fallback") : t("agent.output")}
    </span>
  );
}
export function AgentStatus() {
  const { t } = useI18n();
  const state = useAgent(agentHealth);
  return (
    <span className="agent-status">
      {state.data?.includes("template")
        ? t("agent.template")
        : state.data
          ? t("agent.foundry")
          : state.error
            ? t("agent.unavailable")
            : t("agent.connecting")}
    </span>
  );
}
export function AgentLaw({
  matchId,
  event,
  open = false,
}: {
  matchId: string;
  event: MatchEvent;
  open?: boolean;
}) {
  const { t } = useI18n();
  const state = useAgent((signal) => explain(matchId, event.id, signal));
  return (
    <section className="agent-law" aria-label={t("agent.law")}>
      <h4>{t("agent.law")}</h4>
      {state.data ? (
        <>
          <details className="law-details" open={open}>
            <summary>{t("agent.fullExplanation")}</summary>
            <p>{state.data.text}</p>
          </details>
          <Source data={state.data} />
          <EnglishNote />
        </>
      ) : (
        <AgentState {...state} />
      )}
    </section>
  );
}
export function AgentNarrative({
  result,
  variant = "analyst",
}: {
  result: ForkResult;
  variant?: "fan" | "analyst";
}) {
  const { t } = useI18n();
  const state = useAgent((signal) => narrate(result, signal));
  return (
    <section
      className={`agent-narrative ${variant}`}
      aria-label={t("agent.narratorAria")}
    >
      <div className="section-title">
        <h3>{variant === "fan" ? t("agent.commentary") : t("agent.narrator")}</h3>
        {state.data && <Source data={state.data} />}
      </div>
      {state.data ? (
        <div className="narrative-grid">
          {["real", "alternate"].map((side) => (
            <div key={side}>
              <span className="timeline-name">
                {side === "real" ? t("agent.happened") : t("agent.couldHappen")}
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
      {state.data && <EnglishNote />}
      {variant === "analyst" && (
        <p className="small muted">{t("agent.fullTimeNote")}</p>
      )}
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
  const { t } = useI18n();
  const state = useAgent((signal) =>
    precedents(result.match_id, result.event_id, signal),
  );
  const canonical = state.data?.facts.history;
  const aligned =
    canonical && typeof canonical === "object" && "when_given" in canonical;
  const agrees = state.data ? historyAgreement(state.data, result) : null;
  return (
    <section className="agent-history" aria-label={t("agent.histAria")}>
      <div className="section-title">
        <h4>{t("agent.historian")}</h4>
        {state.data && <Source data={state.data} />}
      </div>
      {state.data ? (
        <>
          <p>{state.data.text}</p>
          <p className="small muted">
            {aligned ? t("agent.srcUnified") : t("agent.srcDev")}
          </p>
          {agrees !== null && (
            <p className={`agreement ${!agrees ? "disagrees" : ""}`}>
              {agrees ? t("agent.agree") : t("agent.disagree")}{" "}
              {!aligned && t("agent.usesSim")}
            </p>
          )}
          <EnglishNote />
        </>
      ) : (
        <AgentState {...state} />
      )}
    </section>
  );
}
