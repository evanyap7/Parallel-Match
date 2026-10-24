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
  readable,
  scoreText,
  statsAt,
} from "../model";
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
          <h2 id="report-title">Comparison</h2>
          <p>
            Run a comparison to fill this report: the outcome shift with its 95%
            interval, the alternate score distribution, season precedent and the
            divergence log.
          </p>
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
  const s = useMemo(() => statsAt(match, time), [match, time]);
  const score = eventAt(match.events, time)?.score ?? [0, 0];
  const comp = (i: number) =>
    s.passes[i] ? percent(s.completed[i] / s.passes[i]) : "–";
  const cells: [string, string, string][] = [
    [
      "Score",
      scoreText(score as [number, number]),
      `${match.home} / ${match.away}`,
    ],
    ["Shots", `${s.shots[0]} / ${s.shots[1]}`, "Recorded shot events"],
    [
      "Expected goals",
      `${s.xg[0].toFixed(2)} / ${s.xg[1].toFixed(2)}`,
      "Sum of simulator xG",
    ],
    ["Pass completion", `${comp(0)} / ${comp(1)}`, "Completed of attempted"],
  ];
  return (
    <section
      className="stat-strip"
      aria-label={`Match statistics at ${clockLabel(time)}`}
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
  const e = p.selected;
  if (!e)
    return (
      <aside className="dossier panel">
        <h2>Decision</h2>
        <p>No supported moments in this match.</p>
      </aside>
    );
  const margin =
    e.margin !== undefined
      ? `${e.margin > 0 ? "+" : ""}${e.margin.toFixed(3)}${e.type === "offside" ? " m" : ""}`
      : null;
  const rows: [string, string][] = [
    ["Minute", `${e.min}′`],
    ["Event", readable(e.type)],
    ["Team", e.team ? clubName(e.team) : "–"],
    ["Player", e.player ?? "–"],
    ["Recorded call", e.call ? readable(e.call) : "–"],
  ];
  if (e.contact !== undefined)
    rows.push(["Contact severity", e.contact.toFixed(3)]);
  if (margin)
    rows.push([
      e.type === "offside" ? "Beyond the line" : "Against threshold",
      margin,
    ]);
  if (e.offside_margin !== undefined)
    rows.push(["Offside margin", `${e.offside_margin.toFixed(2)} m`]);
  rows.push(
    ["Contestable", e.contestable ? "Yes" : "No"],
    ["Simulator step", String(e.step)],
    ["Ball position", e.xy ? `${e.xy[0]}, ${e.xy[1]}` : "–"],
  );
  return (
    <aside className="dossier panel" aria-labelledby="dossier-title">
      <header className="panel-head">
        <h2 id="dossier-title">Decision</h2>
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
        {e.law ?? "No law reference supplied for this event."}
      </p>
      <h3 className="panel-sub">Change</h3>
      {p.liveEngine ? (
        <DecisionControls
          event={e}
          match={p.match}
          clubs={p.clubs}
          change={p.change}
          onChange={p.updateChange}
        />
      ) : (
        p.change && <p className="change-name">{changeLabel(p.change, e)}</p>
      )}
      <button
        className="primary explore"
        disabled={!p.changeReady || !p.canMock || p.forkLoading}
        onClick={() => p.explore()}
      >
        {p.forkLoading ? (
          <>
            <LoaderCircle size={17} className="spin" /> Running rollouts…
          </>
        ) : (
          <>
            Run comparison <ArrowRight size={17} />
          </>
        )}
      </button>
      {p.forkLoading && (
        <button className="text-button" onClick={p.cancel}>
          Cancel
        </button>
      )}
      {!p.canMock && (
        <p className="small muted">
          Offline mode has one featured moment.{" "}
          <button className="text-button" onClick={p.loadExample}>
            Load it
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
            Free text, parsed by the Intervention agent
          </label>
          <div className="ask-row">
            <input
              id="an-what-if"
              maxLength={300}
              value={p.whatIf}
              onChange={(ev) => p.setWhatIf(ev.target.value)}
              placeholder="e.g. no penalty, or he was onside"
            />
            <button
              className="secondary"
              disabled={!p.whatIf.trim() || p.forkLoading}
            >
              Parse
            </button>
          </div>
          {p.result && (
            <p className="small muted">
              Sent to the fork: {p.result.description}.
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
  const { result, match } = p;
  const sides = [
    ["home", `${clubName(match.home)} win`],
    ["draw", "Draw"],
    ["away", `${clubName(match.away)} win`],
  ] as const;
  return (
    <section className="report" aria-labelledby="report-title">
      <header className="report-head">
        <h2 id="report-title">Comparison</h2>
        <p>
          {result.description} · fork at {result.divergence.min}′ ·{" "}
          {result.rollouts.toLocaleString()} paired rollouts
          {result.cached ? " · precomputed" : ""}
          {result.timing ? ` · ${result.timing.total_s.toFixed(1)} s` : ""}
          {result.placeholder ? " · fixture placeholder" : ""}
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
                95% CI {points(ci[0])} to {points(ci[1])}
              </small>
            </div>
          );
        })}
        <div>
          <span>Typical final score</span>
          <strong>{scoreText(result.alternate.final_score)}</strong>
          <small>Real {scoreText(result.original.final_score)}</small>
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
              <h3>Historian</h3>
              <p className="small muted">
                Season precedent covers officiating calls only.
              </p>
            </>
          )}
        </section>
      </div>
    </section>
  );
}

function OutcomeTable({ result, match }: { result: ForkResult; match: Match }) {
  const o = result.original.outcome;
  const a = result.alternate.outcome;
  const rows = [
    ["home", clubName(match.home)],
    ["draw", "Draw"],
    ["away", clubName(match.away)],
  ] as const;
  return (
    <section className="panel">
      <h3>Outcome shares</h3>
      <table className="data">
        <thead>
          <tr>
            <th>Result</th>
            <th className="num">Real</th>
            <th className="num">What if</th>
            <th className="num">Shift</th>
            <th className="num">95% CI</th>
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
        From {result.rollouts.toLocaleString()} paired rollouts after the fork;
        each pair shares its random numbers, so the shift is the change, not
        luck.
      </p>
    </section>
  );
}

function ScoreSpread({ result }: { result: ForkResult }) {
  const max = Math.max(...result.score_spread.map((s) => s.share), 0.01);
  const typical = scoreText(result.alternate.final_score);
  return (
    <section className="panel">
      <h3>Alternate final scores</h3>
      <table className="data">
        <thead>
          <tr>
            <th>Score</th>
            <th>Share of rollouts</th>
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
                  {label === typical && <span className="tag">typical</span>}
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
        The real match finished {scoreText(result.original.final_score)}.
      </p>
    </section>
  );
}

function PrecedentPanel({ result }: { result: ForkResult }) {
  const h = result.history;
  if (!h)
    return (
      <section className="panel">
        <h3>Season precedent</h3>
        <p className="small muted">
          Precedent is computed for flipped officiating calls only.
        </p>
      </section>
    );
  const g = h.when_given;
  const n = h.when_not_given;
  return (
    <section className="panel">
      <h3>Season precedent</h3>
      <p className="panel-note">{h.description}</p>
      <table className="data">
        <thead>
          <tr>
            <th>Call</th>
            <th className="num">n</th>
            <th className="num">Attack won</th>
            <th className="num">Goal in 10′</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <th scope="row">Given</th>
            <td className="num">{g.n}</td>
            <td className="num">{pc(g.win)}</td>
            <td className="num">{pc(g.goal_10)}</td>
          </tr>
          <tr>
            <th scope="row">Not given</th>
            <td className="num">{n.n}</td>
            <td className="num">{pc(n.win)}</td>
            <td className="num">{pc(n.goal_10)}</td>
          </tr>
        </tbody>
      </table>
      <dl className="facts compact">
        <div>
          <dt>History shift, {h.attacking_team}</dt>
          <dd>
            {h.history_shift_att_win == null
              ? "Not enough precedent"
              : points(h.history_shift_att_win)}
          </dd>
        </div>
        <div>
          <dt>Simulated shift, {h.attacking_team}</dt>
          <dd className="alt">
            {h.sim_shift_att_win == null ? "–" : points(h.sim_shift_att_win)}
          </dd>
        </div>
      </dl>
      <p
        className={`agreement${h.agrees_with_simulation === false ? " disagrees" : ""}`}
      >
        {h.agrees_with_simulation == null
          ? "Not enough precedent to compare."
          : h.agrees_with_simulation
            ? "Precedent and simulation agree in direction."
            : "Precedent and simulation disagree. Treat the estimate as uncertain."}
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
  const step = result.divergence.step;
  const column = (title: string, list: MatchEvent[], alt: boolean) => (
    <div className={`log-col${alt ? " alt" : ""}`}>
      <h4>{title}</h4>
      <ol>
        {list.map((e) => (
          <li key={e.id}>
            <span className="log-min">{e.min}′</span>
            <span className="log-what">{describe(e)}</span>
            <span className="log-score">{scoreText(e.score)}</span>
          </li>
        ))}
      </ol>
    </div>
  );
  return (
    <section className="panel log">
      <h3>Divergence log</h3>
      <p className="panel-note">
        Events from the fork at {result.divergence.min}′, passes and dribbles
        left out.
      </p>
      <div className="log-grid">
        {column("Real", eventsFrom(match.events, step, 8), false)}
        {column("What if", eventsFrom(forkEvents, step, 8), true)}
      </div>
    </section>
  );
}

const FILTERS = [
  ["all", "All"],
  ["foul", "Contact"],
  ["offside", "Offside"],
  ["other", "Goals, cards, subs"],
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
        <h2 id="moments-title">All moments</h2>
        <span className="count">
          {rows.length} of {moments.length}
        </span>
        <div className="filter-row" role="group" aria-label="Filter moments">
          {FILTERS.map(([v, l]) => (
            <button
              key={v}
              aria-pressed={filter === v}
              className={filter === v ? "active" : ""}
              onClick={() => setFilter(v)}
            >
              {l}
            </button>
          ))}
        </div>
      </header>
      <div className="table-scroll">
        <table className="data moments-table">
          <thead>
            <tr>
              <th className="num">Min</th>
              <th>Moment</th>
              <th>Team</th>
              <th>Call</th>
              <th className="num">Margin</th>
              <th>Contestable</th>
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
                    {readable(e.type)}
                    {e.player ? ` · ${e.player}` : ""}
                  </button>
                </td>
                <td>{e.team ?? "–"}</td>
                <td>{e.call ? readable(e.call) : "–"}</td>
                <td className="num">
                  {e.margin !== undefined
                    ? e.margin.toFixed(3)
                    : e.offside_margin !== undefined
                      ? `${e.offside_margin.toFixed(2)} m`
                      : "–"}
                </td>
                <td>{e.contestable ? "Yes" : "–"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
