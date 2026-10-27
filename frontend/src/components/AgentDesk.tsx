import {
  Check,
  ClipboardList,
  History,
  Mic,
  Newspaper,
  PenLine,
  Scale,
  ShieldCheck,
  X,
} from "lucide-react";
import type { CSSProperties, ComponentType } from "react";
import { desk } from "../agents";
import type { Desk, DeskStep } from "../agents";
import { useI18n } from "../i18n";
import type { Key } from "../i18n";
import type { ForkResult } from "../types";
import { AgentState, EnglishNote, useAgent } from "./AgentPanels";

const ICONS: Record<string, ComponentType<{ size?: number; "aria-hidden"?: boolean }>> = {
  producer: ClipboardList,
  narrator: Mic,
  law: Scale,
  historian: History,
  fact_checker: ShieldCheck,
  editor: PenLine,
  recap: Newspaper,
};

const ROLE_KEYS: Record<string, Key> = {
  producer: "desk.role.producer",
  narrator: "agent.narrator",
  law: "agent.law",
  historian: "agent.historian",
  fact_checker: "desk.role.fact_checker",
  editor: "desk.role.editor",
  recap: "desk.role.recap",
};

const STATUS_KEYS: Record<string, Key> = {
  ok: "desk.status.ok",
  fallback: "desk.status.fallback",
  skipped: "desk.status.skipped",
  rejected: "desk.status.rejected",
  idle: "desk.status.idle",
  repaired: "desk.status.repaired",
  restored: "desk.status.restored",
  approved: "desk.status.approved",
  working: "desk.status.working",
};

const CHECK_KEYS: Record<string, Key> = {
  same_moment: "desk.check.same_moment",
  same_call: "desk.check.same_call",
  precedent_count: "desk.check.precedent_count",
};

function Node({
  role,
  step,
  order,
  doing,
  detail,
}: {
  role: string;
  step?: DeskStep;
  order: number;
  doing?: string;
  detail?: string;
}) {
  const { t } = useI18n();
  const Icon = ICONS[role] ?? ClipboardList;
  const status = step?.status ?? "working";
  return (
    <div
      className={`desk-node status-${status}`}
      style={{ "--i": order } as CSSProperties}
    >
      <span className="desk-icon">
        <Icon size={18} aria-hidden />
      </span>
      <span className="desk-node-text">
        <strong>{t(ROLE_KEYS[role] ?? "desk.role.producer")}</strong>
        {doing && <span className="desk-doing">{doing}</span>}
        <span className="desk-status">
          {t(STATUS_KEYS[status] ?? "desk.status.ok")}
          {step && <span className="desk-ms"> · {step.ms} ms</span>}
        </span>
        {detail && <span className="desk-detail">{detail}</span>}
      </span>
    </div>
  );
}

function callLabel(call: { tool: string; args: Record<string, unknown> }) {
  const args = Object.entries(call.args)
    .map(([k, v]) => `${k}=${JSON.stringify(v)}`)
    .join(", ");
  return `${call.tool}(${args.length > 60 ? `${args.slice(0, 57)}…` : args})`;
}

function Evidence({ data }: { data: Desk }) {
  const { t } = useI18n();
  const checker = data.trace.find((s) => s.role === "fact_checker");
  return (
    <details className="desk-evidence">
      <summary>{t("desk.evidence")}</summary>
      <div className="desk-evidence-grid">
        <div>
          <h4>{t("desk.checks")}</h4>
          <ul className="desk-list">
            {data.checks.consistency.map((c) => (
              <li key={c.check} className={c.ok ? "ok" : "bad"}>
                {c.ok ? <Check size={14} aria-hidden /> : <X size={14} aria-hidden />}
                {CHECK_KEYS[c.check] ? t(CHECK_KEYS[c.check]) : c.check}
              </li>
            ))}
          </ul>
          <h4>{t("desk.toolCalls")}</h4>
          <ul className="desk-list mono">
            {(checker?.tool_calls ?? []).map((c, i) => (
              <li key={i} className={c.ok ? "ok" : "bad"}>
                {c.ok ? <Check size={14} aria-hidden /> : <X size={14} aria-hidden />}
                <code>{callLabel(c)}</code>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <h4>{t("desk.pieces")}</h4>
          <ul className="desk-pieces">
            {data.pieces.map((p) => (
              <li key={p.role}>
                <span className="desk-piece-head">
                  <strong>{t(ROLE_KEYS[p.role] ?? "desk.role.producer")}</strong>
                  <span className={`desk-chip status-${p.status}`}>
                    {t(STATUS_KEYS[p.status])}
                  </span>
                </span>
                <p>{p.text}</p>
                {p.issues.length > 0 && (
                  <p className="small muted">{p.issues.join(" · ")}</p>
                )}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </details>
  );
}

/** The Match Desk: how the agents produced the answer, step by step. */
export function AgentDesk({ result }: { result: ForkResult }) {
  const { t, lang } = useI18n();
  const state = useAgent((signal) => desk(result, signal, lang));
  const data = state.data;
  const step = (role: string) => data?.trace.find((s) => s.role === role);
  const specialists =
    data?.plan ??
    (result.change.type === "flip_call"
      ? ["narrator", "law", "historian"]
      : ["narrator", "law"]);
  const checker = step("fact_checker");
  return (
    <section
      className={`panel agent-desk ${data ? "ready" : "loading"}`}
      aria-label={t("desk.aria")}
      aria-busy={!data && !state.error}
    >
      <div className="section-title">
        <h3>{t("desk.title")}</h3>
        {checker && (
          <span className="small-label">
            {t(checker.reviewer === "agent" ? "desk.reviewer.agent" : "desk.reviewer.code")}
          </span>
        )}
      </div>
      <p className="small muted">{t("desk.intro")}</p>
      <ol className="desk-flow">
        <li>
          <Node role="producer" step={step("producer")} order={0} doing={t("desk.do.producer")} />
        </li>
        <li className="desk-parallel">
          <span className="desk-doing">{t("desk.do.specialists")}</span>
          {specialists.map((role, i) => (
            <Node key={role} role={role} step={step(role)} order={1 + i * 0.4} />
          ))}
        </li>
        <li>
          <Node
            role="fact_checker"
            step={checker}
            order={2.4}
            doing={t("desk.do.fact_checker")}
            detail={
              data
                ? `${data.checks.tool_calls} × ${t("desk.toolCalls").toLowerCase()}`
                : undefined
            }
          />
        </li>
        <li>
          <Node role="editor" step={step("editor")} order={3.2} doing={t("desk.do.editor")} />
        </li>
        <li>
          <Node role="recap" step={step("recap")} order={4} doing={t("desk.do.recap")} />
        </li>
      </ol>
      {data ? (
        <>
          <div className="desk-recap" style={{ "--i": 4.6 } as CSSProperties}>
            <span className="timeline-name">{t("desk.recap")}</span>
            <p>{data.recap.text}</p>
            <span className="small-label">
              {t("desk.verified", {
                numbers: data.checks.numbers_verified,
                tools: data.checks.tool_calls,
                ms: data.ms,
              })}
            </span>
            <EnglishNote translated={data.recap.translated} />
          </div>
          <Evidence data={data} />
        </>
      ) : (
        state.error && <AgentState {...state} />
      )}
    </section>
  );
}
