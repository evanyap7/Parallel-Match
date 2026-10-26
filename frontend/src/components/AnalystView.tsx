import { useMemo, useState } from "react";
import { ArrowRight, LoaderCircle } from "lucide-react";
import {
  changeLabel,
  clockLabel,
  clubName,
  describe,
  eventAt,
  eventsFrom,
  percent,
  points,
  scoreText,
  statsAt,
  word,
} from "../model";
import { useI18n } from "../i18n";
import { Pitch } from "./Pitch";
import { Transport } from "./Transport";
import { ProbabilityChart } from "./ProbabilityChart";
import { AgentHistory, AgentLaw, AgentNarrative } from "./AgentPanels";
import { DecisionControls } from "./DecisionControls";
import type { ForkResult, Match, MatchEvent } from "../types";
import type { ViewProps } from "./viewProps";

const pc = (v?: number | null) =>
  v === null || v === undefined ? "–" : percent(v);

/** Analyst view: every figure the engine produces, set as tables and type. */
export function AnalystView(p: ViewProps) {
  const { t } = useI18n();
  const { match, result, transport } = p;
  return (
    <div className="analyst">
      <div className="an-top">
        <div className="an-broadcast">
          <div className="broadcast-grid">
            <Pitch
              events={match.events}
              time={transport.time}
              home={match.home}
              away={match.away}
            />
            <Pitch
              events={p.forkEvents}
              time={transport.time}
              home={match.home}
              away={match.away}
              alternate
              pending={!p.forkEvents.length}
              divergence={result?.divergence.t}
            />
          </div>
          <Transport
            detailed
            state={transport}
            markers={p.moments}
            selectedId={p.selectedId}
            onSelect={p.chooseMoment}
            result={result}
          />
          <MatchStats match={match} time={transport.time} />
        </div>
        <Dossier {...p} />
      </div>
      {result ? (
        <Report {...p} result={result} />
      ) : (
        <section className="report-empty" aria-labelledby="report-title">
          <h2 id="report-title">{t("an.report")}</h2>
          <p>{t("an.reportEmpty")}</p>
        </section>
      )}
      <MomentTable
        moments={p.moments}
        selectedId={p.selectedId}
        onSelect={p.chooseMoment}
      />
    </div>
  );
}

function MatchStats({ match, time }: { match: Match; time: number }) {
  const { t } = useI18n();
  const s = useMemo(() => statsAt(match, time), [match, time]);
  const score = eventAt(match.events, time)?.score ?? [0, 0];
  const comp = (i: number) =>
    s.passes[i] ? percent(s.completed[i] / s.passes[i]) : "–";
  const cells: [string, string, string][] = [
    [
      t("an.score"),
      scoreText(score as [number, number]),
      `${match.home} / ${match.away}`,
    ],
    [t("an.shots"), `${s.shots[0]} / ${s.shots[1]}`, t("an.shotsNote")],
    [
      t("an.xg"),
      `${s.xg[0].toFixed(2)} / ${s.xg[1].toFixed(2)}`,
      t("an.xgNote"),
    ],
    [t("an.pass"), `${comp(0)} / ${comp(1)}`, t("an.passNote")],
  ];
  return (
    <section
      className="stat-strip"
      aria-label={t("an.statsAria", { clock: clockLabel(time) })}
    >
      {cells.map(([label, value, note]) => (
        <div key={label}>
          <span>{label}</span>
          <strong>{value}</strong>
          <small>{note}</small>
        </div>
      ))}
    </section>
  );
}

function Dossier(p: ViewProps) {
  const { t } = useI18n();
  const e = p.selected;
  if (!e)
    return (
      <aside className="dossier panel">
        <h2>{t("an.decision")}</h2>
        <p>{t("an.noMoments")}</p>
      </aside>
    );
  const margin =
    e.margin !== undefined
      ? `${e.margin > 0 ? "+" : ""}${e.margin.toFixed(3)}${e.type === "offside" ? " m" : ""}`
      : null;
  const rows: [string, string][] = [
    [t("an.minute"), `${e.min}′`],
    [t("an.event"), word(e.type, t)],
    [t("an.team"), e.team ? clubName(e.team) : "–"],
    [t("an.player"), e.player ?? "–"],
    [t("an.recorded"), e.call ? word(e.call, t) : "–"],
  ];
  if (e.contact !== undefined)
    rows.push([t("an.contact"), e.contact.toFixed(3)]);
  if (margin)
    rows.push([
      e.type === "offside" ? t("an.beyond") : t("an.threshold"),
      margin,
    ]);
  if (e.offside_margin !== undefined)
    rows.push([t("an.offMargin"), `${e.offside_margin.toFixed(2)} m`]);
  rows.push(
    [t("an.contestable"), e.contestable ? t("an.yes") : t("an.no")],
    [t("an.step"), String(e.step)],
    [t("an.ball"), e.xy ? `${e.xy[0]}, ${e.xy[1]}` : "–"],
  );
  return (
    <aside className="dossier panel" aria-labelledby="dossier-title">
      <header className="panel-head">
        <h2 id="dossier-title">{t("an.decision")}</h2>
        <code>{e.id}</code>
      </header>
      <dl className="facts">
        {rows.map(([k, v]) => (
          <div key={k}>
            <dt>{k}</dt>
            <dd>{v}</dd>
          </div>
        ))}
      </dl>
      <p className="law-ref">
        {e.law ?? t("an.noLaw")}
      </p>
      <h3 className="panel-sub">{t("an.change")}</h3>
      {p.liveEngine ? (
        <DecisionControls
          event={e}
          match={p.match}
          clubs={p.clubs}
          change={p.change}
          onChange={p.updateChange}
        />
      ) : (
        p.change && (
          <p className="change-name">{changeLabel(p.change, e, t)}</p>
        )
      )}
      <button
        className="primary explore"
        disabled={!p.changeReady || !p.canMock || p.forkLoading}
        onClick={() => p.explore()}
      >
        {p.forkLoading ? (
          <>
            <LoaderCircle size={17} className="spin" /> {t("an.running")}
          </>
        ) : (
          <>
            {t("an.run")} <ArrowRight size={17} />
          </>
        )}
      </button>
      {p.forkLoading && (
        <button className="text-button" onClick={p.cancel}>
          {t("fan.cancel")}
        </button>
      )}
      {!p.canMock && (
        <p className="small muted">
          {t("an.offlineOne")}{" "}
          <button className="text-button" onClick={p.loadExample}>
            {t("an.load")}
          </button>
        </p>
      )}
      {p.forkError && (
        <p role="alert" className="inline-error">
          {p.forkError}
        </p>
      )}
      {p.liveEngine && (
        <form
          className="ask-own"
          onSubmit={(ev) => {
            ev.preventDefault();
            p.explore(true);
          }}
        >
          <label htmlFor="an-what-if">
            {t("an.freeText")}
          </label>
          <div className="ask-row">
            <input
              id="an-what-if"
              maxLength={300}
              value={p.whatIf}
              onChange={(ev) => p.setWhatIf(ev.target.value)}
              placeholder={t("an.freePlaceholder")}
            />
            <button
              className="secondary"
              disabled={!p.whatIf.trim() || p.forkLoading}
            >
              {t("an.parse")}
            </button>
          </div>
          {p.result && (
            <p className="small muted">
              {t("an.sent", { description: p.result.description })}
            </p>
          )}
        </form>
      )}
      <AgentLaw
        key={`${p.match.match_id}:${p.selectedId}`}
        matchId={p.match.match_id}
        event={e}
      />
    </aside>
  );
}

function Report(p: ViewProps & { result: ForkResult }) {
  const { t } = useI18n();
  const { result, match } = p;
  const sides = [
    ["home", t("an.win", { club: clubName(match.home) })],
    ["draw", t("an.draw")],
    ["away", t("an.win", { club: clubName(match.away) })],
  ] as const;
  return (
    <section className="report" aria-labelledby="report-title">
      <header className="report-head">
        <h2 id="report-title">{t("an.report")}</h2>
        <p>
          {result.description} ·{" "}
          {t("an.rolloutsLine", {
            min: result.divergence.min,
            n: result.rollouts.toLocaleString(),
          })}
          {result.cached ? ` · ${t("an.precomputed")}` : ""}
          {result.timing ? ` · ${result.timing.total_s.toFixed(1)} s` : ""}
          {result.placeholder ? ` · ${t("an.placeholder")}` : ""}
        </p>
      </header>
      <div className="shift-strip">
        {sides.map(([k, label]) => {
          const ci = result.uncertainty.shift_ci95[k];
          return (
            <div key={k} className={k === p.side ? "focus" : ""}>
              <span>{label}</span>
              <strong>{points(result.outcome_shift[k])}</strong>
              <small>
                {t("an.ci", { a: points(ci[0]), b: points(ci[1]) })}
              </small>
            </div>
          );
        })}
        <div>
          <span>{t("an.typical")}</span>
          <strong>{scoreText(result.alternate.final_score)}</strong>
          <small>
            {t("an.realScore", { score: scoreText(result.original.final_score) })}
          </small>
        </div>
      </div>
      <div className="report-row two">
        <ProbabilityChart result={result} home={match.home} />
        <OutcomeTable result={result} match={match} />
      </div>
      <div className="report-row three">
        <ScoreSpread result={result} />
        <PrecedentPanel result={result} />
        <DivergenceLog
          match={match}
          result={result}
          forkEvents={p.forkEvents}
        />
      </div>
      <div className="report-row two">
        <AgentNarrative
          key={`${match.match_id}:${p.selectedId}:${p.attempt}`}
          result={result}
          variant="analyst"
        />
        <section className="panel">
          {result.change.type === "flip_call" ? (
            <AgentHistory
              key={`${match.match_id}:${p.selectedId}:${p.attempt}`}
              result={result}
            />
          ) : (
            <>
              <h3>{t("agent.historian")}</h3>
              <p className="small muted">{t("an.noHistorian")}</p>
            </>
          )}
        </section>
      </div>
    </section>
  );
}

function OutcomeTable({ result, match }: { result: ForkResult; match: Match }) {
  const { t } = useI18n();
  const o = result.original.outcome;
  const a = result.alternate.outcome;
  const rows = [
    ["home", clubName(match.home)],
    ["draw", t("an.draw")],
    ["away", clubName(match.away)],
  ] as const;
  return (
    <section className="panel">
      <h3>{t("an.outcomeTitle")}</h3>
      <table className="data">
        <thead>
          <tr>
            <th>{t("an.result")}</th>
            <th className="num">{t("an.real")}</th>
            <th className="num">{t("an.whatIf")}</th>
            <th className="num">{t("an.shift")}</th>
            <th className="num">{t("an.ci95")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([k, label]) => (
            <tr key={k}>
              <th scope="row">{label}</th>
              <td className="num">{o ? percent(o[k]) : "–"}</td>
              <td className="num alt">{a ? percent(a[k]) : "–"}</td>
              <td className="num">{points(result.outcome_shift[k])}</td>
              <td className="num muted">
                {result.uncertainty.shift_ci95[k].map(points).join(" to ")}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="small muted">
        {t("an.outcomeNote", { n: result.rollouts.toLocaleString() })}
      </p>
    </section>
  );
}

function ScoreSpread({ result }: { result: ForkResult }) {
  const { t } = useI18n();
  const max = Math.max(...result.score_spread.map((s) => s.share), 0.01);
  const typical = scoreText(result.alternate.final_score);
  return (
    <section className="panel">
      <h3>{t("an.altScores")}</h3>
      <table className="data">
        <thead>
          <tr>
            <th>{t("an.score")}</th>
            <th>{t("an.shareRollouts")}</th>
            <th className="num">%</th>
          </tr>
        </thead>
        <tbody>
          {result.score_spread.map((s) => {
            const label = scoreText(s.score);
            return (
              <tr key={label}>
                <th scope="row">
                  {label}
                  {label === typical && <span className="tag">{t("an.typicalTag")}</span>}
                </th>
                <td>
                  <span
                    className="bar"
                    style={{ width: `${(s.share / max) * 100}%` }}
                  />
                </td>
                <td className="num">{percent(s.share)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="small muted">
        {t("an.realFinished", { score: scoreText(result.original.final_score) })}
      </p>
    </section>
  );
}

function PrecedentPanel({ result }: { result: ForkResult }) {
  const { t } = useI18n();
  const h = result.history;
  if (!h)
    return (
      <section className="panel">
        <h3>{t("an.precedent")}</h3>
        <p className="small muted">{t("an.precedentNone")}</p>
      </section>
    );
  const g = h.when_given;
  const n = h.when_not_given;
  return (
    <section className="panel">
      <h3>{t("an.precedent")}</h3>
      <p className="panel-note">{h.description}</p>
      <table className="data">
        <thead>
          <tr>
            <th>{t("an.call")}</th>
            <th className="num">n</th>
            <th className="num">{t("an.attackWon")}</th>
            <th className="num">{t("an.goal10")}</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <th scope="row">{t("an.given")}</th>
            <td className="num">{g.n}</td>
            <td className="num">{pc(g.win)}</td>
            <td className="num">{pc(g.goal_10)}</td>
          </tr>
          <tr>
            <th scope="row">{t("an.notGiven")}</th>
            <td className="num">{n.n}</td>
            <td className="num">{pc(n.win)}</td>
            <td className="num">{pc(n.goal_10)}</td>
          </tr>
        </tbody>
      </table>
      <dl className="facts compact">
        <div>
          <dt>{t("an.histShift", { team: h.attacking_team })}</dt>
          <dd>
            {h.history_shift_att_win == null
              ? t("an.notEnough")
              : points(h.history_shift_att_win)}
          </dd>
        </div>
        <div>
          <dt>{t("an.simShift", { team: h.attacking_team })}</dt>
          <dd className="alt">
            {h.sim_shift_att_win == null ? "–" : points(h.sim_shift_att_win)}
          </dd>
        </div>
      </dl>
      <p
        className={`agreement${h.agrees_with_simulation === false ? " disagrees" : ""}`}
      >
        {h.agrees_with_simulation == null
          ? t("an.cmpNone")
          : h.agrees_with_simulation
            ? t("an.cmpAgree")
            : t("an.cmpDisagree")}
      </p>
    </section>
  );
}

function DivergenceLog({
  match,
  result,
  forkEvents,
}: {
  match: Match;
  result: ForkResult;
  forkEvents: MatchEvent[];
}) {
  const { t } = useI18n();
  const step = result.divergence.step;
  const column = (title: string, list: MatchEvent[], alt: boolean) => (
    <div className={`log-col${alt ? " alt" : ""}`}>
      <h4>{title}</h4>
      <ol>
        {list.map((e) => (
          <li key={e.id}>
            <span className="log-min">{e.min}′</span>
            <span className="log-what">{describe(e, t)}</span>
            <span className="log-score">{scoreText(e.score)}</span>
          </li>
        ))}
      </ol>
    </div>
  );
  return (
    <section className="panel log">
      <h3>{t("an.divergence")}</h3>
      <p className="panel-note">{t("an.divNote", { min: result.divergence.min })}</p>
      <div className="log-grid">
        {column(t("an.real"), eventsFrom(match.events, step, 8), false)}
        {column(t("an.whatIf"), eventsFrom(forkEvents, step, 8), true)}
      </div>
    </section>
  );
}

const FILTERS = [
  ["all", "an.fAll"],
  ["foul", "an.fContact"],
  ["offside", "an.fOffside"],
  ["other", "an.fOther"],
] as const;

function MomentTable({
  moments,
  selectedId,
  onSelect,
}: {
  moments: MatchEvent[];
  selectedId: string;
  onSelect: (e: MatchEvent) => void;
}) {
  const { t } = useI18n();
  const [filter, setFilter] = useState<string>("all");
  const rows = moments.filter(
    (e) =>
      filter === "all" ||
      (filter === "offside"
        ? e.type === "offside" || e.call === "onside"
        : filter === "foul"
          ? e.law?.startsWith("Law 12")
          : ["goal", "shot", "card", "substitution"].includes(e.type)),
  );
  return (
    <section className="panel moments" aria-labelledby="moments-title">
      <header className="panel-head">
        <h2 id="moments-title">{t("an.moments")}</h2>
        <span className="count">
          {t("an.countOf", { n: rows.length, total: moments.length })}
        </span>
        <div className="filter-row" role="group" aria-label={t("an.filter")}>
          {FILTERS.map(([v, l]) => (
            <button
              key={v}
              aria-pressed={filter === v}
              className={filter === v ? "active" : ""}
              onClick={() => setFilter(v)}
            >
              {t(l)}
            </button>
          ))}
        </div>
      </header>
      <div className="table-scroll">
        <table className="data moments-table">
          <thead>
            <tr>
              <th className="num">{t("an.colMin")}</th>
              <th>{t("an.colMoment")}</th>
              <th>{t("an.colTeam")}</th>
              <th>{t("an.colCall")}</th>
              <th className="num">{t("an.colMargin")}</th>
              <th>{t("an.colContestable")}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((e) => (
              <tr key={e.id} className={e.id === selectedId ? "selected" : ""}>
                <td className="num">{e.min}′</td>
                <td>
                  <button
                    className="row-button"
                    aria-current={e.id === selectedId ? "true" : undefined}
                    onClick={() => onSelect(e)}
                  >
                    {word(e.type, t)}
                    {e.player ? ` · ${e.player}` : ""}
                  </button>
                </td>
                <td>{e.team ?? "–"}</td>
                <td>{e.call ? word(e.call, t) : "–"}</td>
                <td className="num">
                  {e.margin !== undefined
                    ? e.margin.toFixed(3)
                    : e.offside_margin !== undefined
                      ? `${e.offside_margin.toFixed(2)} m`
                      : "–"}
                </td>
                <td>{e.contestable ? t("an.yes") : "–"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
