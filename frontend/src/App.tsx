import { useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  ArrowRight,
  Check,
  ChevronRight,
  CircleHelp,
  Flag,
  GitBranch,
  LoaderCircle,
  Pause,
  Play,
  RotateCcw,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";
import {
  fixtureEvents,
  getMoments,
  getClubs,
  getFork,
  getMatch,
  getMatches,
  sourceMode,
} from "./api";
import {
  alternateEvents,
  changesFor,
  changeLabel,
  comparisonSummary,
  clockLabel,
  clubName,
  describe,
  eventAt,
  percent,
  points,
  readable,
  scoreText,
  statsAt,
} from "./model";
import { Pitch } from "./components/Pitch";
import { ProbabilityChart } from "./components/ProbabilityChart";
import { parseWhatIf } from "./agents";
import { toEngineChange } from "./parser-adapter";
import {
  AgentStatus,
  AgentLaw,
  AgentNarrative,
  AgentHistory,
} from "./components/AgentPanels";
import { DecisionControls } from "./components/DecisionControls";
import type {
  Change,
  Club,
  ForkResult,
  Match,
  MatchEvent,
  MatchSummary,
} from "./types";
const errorText = (error: unknown) =>
  error instanceof Error
    ? error.message
    : "Something went wrong. Please try again.";
export default function App() {
  const [clubs, setClubs] = useState<Club[]>([]);
  const [apiMoments, setApiMoments] = useState<MatchEvent[]>([]);
  const [customChange, setCustomChange] = useState<Change>();
  const [matches, setMatches] = useState<MatchSummary[]>([]);
  const [matchId, setMatchId] = useState("");
  const [match, setMatch] = useState<Match>();
  const [loadError, setLoadError] = useState("");
  const [retry, setRetry] = useState(0);
  const [time, setTime] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(12);
  const [selectedId, setSelectedId] = useState("");
  const [filter, setFilter] = useState("all");
  const [view, setView] = useState<"fan" | "analyst">("fan");
  const [focus, setFocus] = useState("");
  const [result, setResult] = useState<ForkResult>();
  const [whatIf, setWhatIf] = useState("");
  const [forkError, setForkError] = useState("");
  const [forkLoading, setForkLoading] = useState(false);
  const [showHelp, setShowHelp] = useState(false);
  const forkController = useRef<AbortController | null>(null);
  const [attempt, setAttempt] = useState(0);
  const helpRef = useRef<HTMLElement>(null);
  useEffect(() => {
    if (!showHelp) return;
    const returnFocus = document.activeElement as HTMLElement | null;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setShowHelp(false);
        return;
      }
      if (event.key !== "Tab") return;
      const items = helpRef.current?.querySelectorAll<HTMLElement>(
        'button, a[href], select, input, [tabindex="0"]',
      );
      if (!items?.length) return;
      const first = items[0],
        last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      returnFocus?.focus();
    };
  }, [showHelp]);
  useEffect(() => {
    const ctrl = new AbortController();
    setLoadError("");
    Promise.all([
      getMatches(ctrl.signal),
      sourceMode === "api" ? getClubs(ctrl.signal) : Promise.resolve([]),
    ])
      .then(([list, league]) => {
        if (ctrl.signal.aborted) return;
        if (!list.length) throw new Error("The API returned no matches.");
        setMatches(list);
        setClubs(league);
        setMatchId(
          (id) =>
            id ||
            list.find((m) => m.match_id === "m052")?.match_id ||
            list[0].match_id,
        );
      })
      .catch((e) => {
        if (!ctrl.signal.aborted) setLoadError(errorText(e));
      });
    return () => ctrl.abort();
  }, [retry]);
  useEffect(() => {
    if (!matchId) return;
    const ctrl = new AbortController();
    forkController.current?.abort();
    setMatch(undefined);
    setResult(undefined);
    setForkError("");
    setLoadError("");
    setForkLoading(false);
    setPlaying(false);
    setCustomChange(undefined);
    setApiMoments([]);
    Promise.all([
      getMatch(matchId, ctrl.signal),
      sourceMode === "api"
        ? getMoments(matchId, ctrl.signal)
        : Promise.resolve([]),
    ])
      .then(([data, suppliedMoments]) => {
        if (ctrl.signal.aborted) return;
        const available =
          sourceMode === "api"
            ? suppliedMoments
            : data.events.filter((e) => changesFor(e).length);
        setMatch(data);
        setApiMoments(available);
        setFocus(data.home);
        const initial =
          available.find((e) => e.id === fixtureEvents[matchId]) ??
          available[0];
        setSelectedId(initial?.id ?? "");
        setTime(initial?.t ?? 0);
        setFilter("all");
      })
      .catch((e) => {
        if (!ctrl.signal.aborted) setLoadError(errorText(e));
      });
    return () => ctrl.abort();
  }, [matchId, retry]);
  useEffect(() => () => forkController.current?.abort(), []);
  const selected = apiMoments.find((e) => e.id === selectedId);
  const forkEvents = useMemo(
    () => (match && result ? alternateEvents(match, result) : []),
    [match, result],
  );
  const end = Math.max(match?.events.at(-1)?.t ?? 0, forkEvents.at(-1)?.t ?? 0);
  useEffect(() => {
    if (!playing) return;
    let previous = performance.now();
    const timer = window.setInterval(() => {
      const now = performance.now(),
        delta = (now - previous) / 1000;
      previous = now;
      setTime((t) => Math.min(end, t + Math.min(delta, 1) * speed));
    }, 100);
    return () => clearInterval(timer);
  }, [playing, speed, end]);
  useEffect(() => {
    if (playing && time >= end) setPlaying(false);
  }, [time, end, playing]);
  const moments = apiMoments;
  const filtered = moments.filter(
    (e) =>
      filter === "all" ||
      (filter === "offside"
        ? e.type === "offside" || e.call === "onside"
        : filter === "foul"
          ? e.law?.startsWith("Law 12")
          : ["goal", "shot", "card", "substitution"].includes(e.type)),
  );
  const stats = useMemo(
    () => (match ? statsAt(match, time) : undefined),
    [match, time],
  );
  const current = match ? eventAt(match.events, time) : undefined;
  const canMock =
    sourceMode !== "fixtures" || selectedId === fixtureEvents[matchId];
  const change =
    customChange ?? (selected ? changesFor(selected)[0] : undefined);
  const changeReady =
    change &&
    (change.type !== "substitution" ||
      (change.team && change.off && change.on));
  const side = focus === match?.away ? "away" : "home";
  function updateChange(value: Change) {
    forkController.current?.abort();
    setForkLoading(false);
    setResult(undefined);
    setForkError("");
    setCustomChange(value);
  }
  function chooseMoment(event: MatchEvent) {
    forkController.current?.abort();
    setForkLoading(false);
    setResult(undefined);
    setForkError("");
    setSelectedId(event.id);
    setCustomChange(undefined);
    setWhatIf("");
    setTime(event.t);
    setPlaying(false);
  }
  async function explore(fromText = false) {
    if (!match || !selected || (!fromText && (!change || !changeReady))) return;
    forkController.current?.abort();
    const ctrl = new AbortController();
    forkController.current = ctrl;
    setForkLoading(true);
    setForkError("");
    setResult(undefined);
    setPlaying(false);
    try {
      const resolved = fromText
        ? toEngineChange(
            await parseWhatIf(
              whatIf,
              { match_id: match.match_id, event_id: selected.id },
              ctrl.signal,
            ),
            selected,
          )
        : change!;
      if (ctrl.signal.aborted) return;
      const response = await getFork(
        { match_id: match.match_id, event_id: selected.id, change: resolved },
        ctrl.signal,
      );
      if (ctrl.signal.aborted) return;
      // The matching event ID is insufficient if a backend anchors the replay at the wrong time.
      if (
        response.divergence.t !== selected.t ||
        response.divergence.step !== selected.step
      )
        throw new Error(
          "The fork anchor does not match the selected event. Check the API response.",
        );
      setResult(response);
      setTime(response.divergence.t);
      setAttempt((a) => a + 1);
    } catch (e) {
      if (!ctrl.signal.aborted) setForkError(errorText(e));
    } finally {
      if (!ctrl.signal.aborted) setForkLoading(false);
    }
  }
  return (
    <div className="app-shell">
      <header className="topbar">
        <a href="#main" className="brand">
          <span className="brand-mark">
            <GitBranch size={23} />
          </span>
          parallel<span className="brand-light">match</span>
          <span className="beta">LAB</span>
        </a>
        <div className="topbar-right">
          <AgentStatus />
          <span className="source-pill">
            <span className="status-dot" />
            {sourceMode === "fixtures" ? "Offline simulation" : "Live engine"}
          </span>
          <button
            className="icon-button"
            onClick={() => setShowHelp(true)}
            aria-label="About this model world"
          >
            <CircleHelp size={19} />
          </button>
        </div>
      </header>
      <main id="main">
        <div className="page-intro">
          <div>
            <div className="eyebrow lime">
              <span className="tiny-line" />
              THE MATCH, RECONSIDERED
            </div>
            <h1>
              One decision.
              <br />
              <span>A different match.</span>
            </h1>
            <p>
              Explore a turning point. Follow the evidence. See what could
              change.
            </p>
          </div>
          <div className="intro-side">
            <span className="model-stamp">
              <ShieldCheck size={16} /> MODEL WORLD
            </span>
            <p>
              Fictional clubs. Synthetic events.
              <br />
              Possibilities, with their uncertainty.
            </p>
          </div>
        </div>
        {loadError ? (
          <div className="error-panel" role="alert">
            <h2>We couldn’t load the match.</h2>
            <p>{loadError}</p>
            <button className="primary" onClick={() => setRetry((x) => x + 1)}>
              Try again
            </button>
            <p className="small">
              API errors never silently fall back to fixture data.
            </p>
          </div>
        ) : !match ? (
          <div className="loading-panel" role="status">
            <LoaderCircle className="spin" /> Loading the match…
          </div>
        ) : (
          <>
            <div className="match-toolbar">
              <div className="fixture-title">
                <span className="league-label">THE SYNTHETIC LEAGUE</span>
                <h2>
                  {clubName(match.home)} <span>vs</span> {clubName(match.away)}
                </h2>
              </div>
              <div className="toolbar-controls">
                {matches.length > 1 && (
                  <label>
                    Match
                    <select
                      value={matchId}
                      onChange={(e) => setMatchId(e.target.value)}
                    >
                      {matches.map((m) => (
                        <option key={m.match_id} value={m.match_id}>
                          {m.home && m.away
                            ? `${m.home} vs ${m.away}${m.story ? ` · ${readable(m.story)}` : ""} · ${m.match_id}`
                            : m.match_id}
                        </option>
                      ))}
                    </select>
                  </label>
                )}
                <div className="segmented" aria-label="Explanation detail">
                  <button
                    aria-pressed={view === "fan"}
                    className={view === "fan" ? "active" : ""}
                    onClick={() => setView("fan")}
                  >
                    Fan view
                  </button>
                  <button
                    aria-pressed={view === "analyst"}
                    className={view === "analyst" ? "active" : ""}
                    onClick={() => setView("analyst")}
                  >
                    Analyst
                  </button>
                </div>
              </div>
            </div>
            {sourceMode === "fixtures" && (
              <div className="fixture-notice">
                <CircleHelp size={15} />
                <span>
                  Both replays and statistics come from the{" "}
                  <strong>completed simulator</strong>. Offline mode includes
                  one featured alternative per match; connect the engine to
                  explore every decision.
                </span>
              </div>
            )}
            <div className="workspace-grid">
              <div className="broadcast-column">
                <div className="broadcast-grid">
                  <Pitch
                    events={match.events}
                    time={time}
                    home={match.home}
                    away={match.away}
                  />
                  <Pitch
                    events={forkEvents}
                    time={time}
                    home={match.home}
                    away={match.away}
                    alternate
                    pending={!forkEvents.length}
                    divergence={result?.divergence.t}
                  />
                </div>
                {result && (
                  <AgentNarrative
                    key={`${match.match_id}:${selectedId}:${attempt}`}
                    result={result}
                  />
                )}
                <section
                  className="transport card"
                  aria-label="Replay controls"
                >
                  <div className="transport-top">
                    <div className="playback-buttons">
                      <button
                        className="play-button"
                        aria-label={playing ? "Pause replay" : "Play replay"}
                        onClick={() => {
                          if (time >= end) setTime(0);
                          setPlaying((p) => !p);
                        }}
                      >
                        {playing ? <Pause size={18} /> : <Play size={18} />}
                      </button>
                      <button
                        className="icon-button"
                        aria-label="Restart replay"
                        onClick={() => {
                          setTime(0);
                          setPlaying(false);
                        }}
                      >
                        <RotateCcw size={16} />
                      </button>
                      <strong className="transport-clock">
                        {clockLabel(time)}
                      </strong>
                      <span className="muted">/ {clockLabel(end)}</span>
                    </div>
                    <label className="speed-label">
                      Speed
                      <select
                        aria-label="Replay speed"
                        value={speed}
                        onChange={(e) => setSpeed(Number(e.target.value))}
                      >
                        <option value={1}>1×</option>
                        <option value={6}>6×</option>
                        <option value={12}>12×</option>
                        <option value={30}>30×</option>
                      </select>
                    </label>
                  </div>
                  <div className="scrubber">
                    <input
                      type="range"
                      aria-label="Match replay position"
                      aria-valuetext={clockLabel(time)}
                      min="0"
                      max={end}
                      step="1"
                      value={time}
                      onChange={(e) => {
                        setTime(Number(e.target.value));
                        setPlaying(false);
                      }}
                    />
                    <div className="moment-markers">
                      {moments.map((e) => (
                        <button
                          key={e.id}
                          aria-label={`Select ${readable(e.type)} at ${e.min} minutes`}
                          title={`${e.min}′ · ${readable(e.type)}`}
                          className={e.id === selectedId ? "selected" : ""}
                          style={{ left: `${(e.t / end) * 100}%` }}
                          onClick={() => chooseMoment(e)}
                        />
                      ))}
                      {result && (
                        <span
                          className="divergence-pin"
                          style={{
                            left: `${(result.divergence.t / end) * 100}%`,
                          }}
                        >
                          <GitBranch size={12} /> FORK {result.divergence.min}′
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="timeline-labels">
                    <span>Kick-off</span>
                    <span>30′</span>
                    <span>60′</span>
                    <span>Full-time</span>
                  </div>
                  <div className="timeline-key">
                    <span>
                      <i /> Supported moment
                    </span>
                    <span>{moments.length} moments to explore</span>
                  </div>
                </section>
                <section className="live-stats card">
                  <div className="section-title">
                    <h3>
                      <Activity size={15} /> Match pulse
                    </h3>
                    <span className="small-label">AT {clockLabel(time)}</span>
                  </div>
                  <div className="stats-row">
                    <div>
                      <span>Score</span>
                      <strong>{scoreText(current?.score ?? [0, 0])}</strong>
                      <small>
                        {match.home} / {match.away}
                      </small>
                    </div>
                    <div>
                      <span>Shots</span>
                      <strong>{stats?.shots.join(" / ")}</strong>
                      <small>Recorded shot events</small>
                    </div>
                    <div>
                      <span>Expected goals</span>
                      <strong>
                        {stats?.xg.map((n) => n.toFixed(2)).join(" / ")}
                      </strong>
                      <small>Sum of simulator xG</small>
                    </div>
                    <div>
                      <span>Pass completion</span>
                      <strong>
                        {stats?.passes
                          .map((n, i) =>
                            n
                              ? `${Math.round((stats.completed[i] / n) * 100)}%`
                              : "—",
                          )
                          .join(" / ")}
                      </strong>
                      <small>Completed / attempted</small>
                    </div>
                  </div>
                </section>
                {result ? (
                  <div className="results-stack" key={attempt}>
                    <div className="result-banner">
                      <GitBranch size={17} />
                      <span>
                        {result.placeholder
                          ? "Fixture comparison"
                          : "Model comparison"}{" "}
                        · {result.divergence.min}′ · {result.description}
                      </span>
                      <span className="small-label">
                        {result.placeholder
                          ? "NOT MEASURED RESULTS"
                          : "NOT A PREDICTION"}
                      </span>
                    </div>
                    <div className="insights-grid">
                      <ProbabilityChart result={result} home={match.home} />
                      <section className="verdict card">
                        <div className="section-title">
                          <h3>
                            <Sparkles size={15} /> The turning point
                          </h3>
                        </div>
                        <p className="verdict-text">
                          {comparisonSummary(result, focus, side)}
                        </p>
                        <p className="small muted">
                          {result.verdict
                            ? "Agent narrative"
                            : "Data summary from paired rollouts"}
                          {result.cached ? " · Precomputed simulation" : ""}
                          {!result.diverged
                            ? " · No immediate change at the selected step"
                            : ""}
                        </p>
                        <div className="final-comparison">
                          <span>Recorded original / typical alternate</span>
                          <div>
                            <span>
                              Original{" "}
                              <strong>
                                {scoreText(result.original.final_score)}
                              </strong>
                            </span>
                            <ArrowRight size={14} />
                            <span>
                              Alternate{" "}
                              <strong>
                                {scoreText(result.alternate.final_score)}
                              </strong>
                            </span>
                          </div>
                        </div>
                        <p className="small muted">
                          {result.placeholder
                            ? "Canned verdict and scores from the shared fixture. "
                            : ""}
                          A single path does not determine the outcome across
                          all rollouts.
                        </p>
                      </section>
                    </div>
                    <section className="evidence card">
                      <div className="section-title">
                        <h3>Behind the comparison</h3>
                        <span className="small-label">
                          {result.placeholder
                            ? "SAMPLE EVIDENCE ONLY"
                            : "SIMULATION & PRECEDENT"}
                        </span>
                      </div>
                      <div className="evidence-grid">
                        <div>
                          <span className="eyebrow muted">
                            01 / RE-SIMULATION
                          </span>
                          <strong className="impact-number">
                            {points(
                              result.outcome_shift[
                                focus === match.away ? "away" : "home"
                              ],
                            )}
                          </strong>
                          <p>{focus} win-probability shift</p>
                          <small>
                            {result.rollouts.toLocaleString()} paired rollouts ·{" "}
                            {focus} shift 95% interval:{" "}
                            {result.uncertainty.shift_ci95[side]
                              .map(points)
                              .join(" to ")}
                          </small>
                        </div>
                        <div>
                          <span className="eyebrow muted">
                            02 / SEASON PRECEDENT
                          </span>
                          <strong className="impact-number">
                            {result.history?.n ?? "—"}
                            <span className="impact-unit">moments</span>
                          </strong>
                          <p>
                            {result.history?.description ??
                              "No comparable season history for this intervention."}
                          </p>
                          <small>
                            {result.history ? (
                              <>
                                {result.history.attacking_team} attacking-team
                                win share: call given{" "}
                                {result.history.when_given.win === null
                                  ? "unavailable"
                                  : percent(result.history.when_given.win)}{" "}
                                (n={result.history.when_given.n}); not given{" "}
                                {result.history.when_not_given.win === null
                                  ? "unavailable"
                                  : percent(
                                      result.history.when_not_given.win,
                                    )}{" "}
                                (n={result.history.when_not_given.n}).{" "}
                              </>
                            ) : (
                              "Precedent is currently available for officiating flips only. "
                            )}
                            Observational precedent is not a causal estimate.
                          </small>
                        </div>
                      </div>
                      {result.change.type === "flip_call" && (
                        <AgentHistory
                          key={`${match.match_id}:${selectedId}:${attempt}`}
                          result={result}
                        />
                      )}
                      <div
                        className={`agreement ${result.history?.agrees_with_simulation === false ? "disagrees" : ""}`}
                      >
                        {result.history?.agrees_with_simulation === true ? (
                          <Check size={15} />
                        ) : (
                          <CircleHelp size={15} />
                        )}
                        <span>
                          {result.history?.agrees_with_simulation == null
                            ? "No agreement assessment supplied."
                            : result.history?.agrees_with_simulation
                              ? "The supplied estimates agree directionally."
                              : "The supplied estimates disagree. This comparison is inconclusive."}
                          {result.placeholder
                            ? " This assessment is also a placeholder."
                            : ""}
                        </span>
                      </div>
                    </section>
                  </div>
                ) : (
                  <div className="comparison-invitation">
                    <GitBranch size={24} />
                    <div>
                      <h3>The match has another side.</h3>
                      <p>
                        Select a decision and explore its alternative. The
                        evidence will appear here.
                      </p>
                    </div>
                  </div>
                )}
              </div>
              <aside className="decision-column">
                <section className="decision-card card">
                  <div className="section-title">
                    <h3>
                      <GitBranch size={16} /> Your turning point
                    </h3>
                    <span className="step-tag">01</span>
                  </div>
                  {selected ? (
                    <>
                      <div className="decision-time">
                        {selected.min}
                        <span>′</span>
                        <span className="decision-kind">
                          {readable(selected.type)}
                        </span>
                      </div>
                      <h3 className="decision-question">
                        What if the decision changed?
                      </h3>
                      <p className="decision-description">
                        {view === "fan"
                          ? `At ${selected.min}′, ${selected.team} player ${selected.player} was involved in a ${readable(selected.type)} decision. Explore how a different call could affect what follows.`
                          : describe(selected)}
                      </p>
                      <div className="decision-facts">
                        <div>
                          <span>Recorded call</span>
                          <strong>
                            {readable(selected.call ?? selected.type)}
                          </strong>
                        </div>
                        <div>
                          <span>Alternative</span>
                          <strong className="lavender">
                            {change
                              ? changeLabel(change, selected)
                              : "Not yet supported"}
                          </strong>
                        </div>
                        {view === "analyst" && (
                          <>
                            <div>
                              <span>Event</span>
                              <code>{selected.id}</code>
                            </div>
                            {selected.margin !== undefined && (
                              <div>
                                <span>
                                  {selected.type === "offside"
                                    ? "Offside margin"
                                    : "Decision margin"}
                                </span>
                                <strong>
                                  {selected.margin.toFixed(3)}
                                  {selected.type === "offside" ? " m" : ""}
                                </strong>
                              </div>
                            )}
                            <div>
                              <span>Simulator step</span>
                              <strong>{selected.step}</strong>
                            </div>
                          </>
                        )}
                      </div>
                      {sourceMode === "api" && (
                        <DecisionControls
                          event={selected}
                          match={match}
                          clubs={clubs}
                          change={change}
                          onChange={updateChange}
                        />
                      )}
                      <button
                        className="primary explore"
                        disabled={!changeReady || !canMock || forkLoading}
                        onClick={() => explore()}
                      >
                        {forkLoading ? (
                          <>
                            <LoaderCircle size={17} className="spin" />{" "}
                            Comparing timelines…
                          </>
                        ) : (
                          <>
                            Explore this alternative <ArrowRight size={17} />
                          </>
                        )}
                      </button>
                      {forkLoading && (
                        <button
                          className="text-button"
                          onClick={() => {
                            forkController.current?.abort();
                            setForkLoading(false);
                          }}
                        >
                          Cancel comparison
                        </button>
                      )}
                      {!canMock && (
                        <p className="small muted">
                          Offline mode includes only the featured alternative.
                          Connect the live engine to explore other moments.{" "}
                          <button
                            className="text-button"
                            onClick={() => {
                              const e = match.events.find(
                                (e) => e.id === fixtureEvents[matchId],
                              );
                              if (e) chooseMoment(e);
                            }}
                          >
                            Load the example moment
                          </button>
                        </p>
                      )}
                      {forkError && (
                        <p role="alert" className="inline-error">
                          {forkError}
                        </p>
                      )}
                      <p className="model-disclaimer">
                        {sourceMode === "fixtures"
                          ? "Loads a precomputed simulator comparison."
                          : "Runs a model comparison using the API."}{" "}
                        A possibility, not a prediction.
                      </p>
                      {sourceMode === "api" && (
                        <form
                          className="what-if"
                          onSubmit={(e) => {
                            e.preventDefault();
                            void explore(true);
                          }}
                        >
                          <label htmlFor="what-if">Your what if…</label>
                          <textarea
                            id="what-if"
                            maxLength={500}
                            value={whatIf}
                            onChange={(e) => setWhatIf(e.target.value)}
                            placeholder="What if that was no foul?"
                          />
                          <button
                            className="primary"
                            disabled={!whatIf.trim() || forkLoading}
                          >
                            Parse and explore
                          </button>
                          <p className="small muted">
                            Supports removing a foul, reversing offside, or
                            scoring a missed shot. Other requests show the
                            parser’s response or an unsupported-case reason.
                          </p>
                          {result && (
                            <p className="small">
                              Sent to the fork: {result.description}.
                            </p>
                          )}
                        </form>
                      )}
                      <AgentLaw
                        key={`${match.match_id}:${selectedId}`}
                        matchId={match.match_id}
                        event={selected}
                      />
                      <div className="law-box">
                        <ShieldCheck size={16} />
                        <div>
                          <strong>The law, neutrally</strong>
                          <p>
                            {selected.law ??
                              "No law reference supplied for this event."}
                          </p>
                          <span>
                            Exploring an alternative does not establish that the
                            original decision was incorrect.
                          </span>
                        </div>
                      </div>
                    </>
                  ) : (
                    <p>No supported moments in this match.</p>
                  )}
                </section>
                <section className="moments-card card">
                  <div className="section-title">
                    <h3>
                      <Flag size={15} /> Decision timeline
                    </h3>
                    <span className="count">{filtered.length}</span>
                  </div>
                  <div className="filter-row">
                    {[
                      ["all", "All"],
                      ["foul", "Contact"],
                      ["offside", "Offside"],
                      ["other", "Other"],
                    ].map(([value, label]) => (
                      <button
                        key={value}
                        className={filter === value ? "active" : ""}
                        aria-pressed={filter === value}
                        onClick={() => setFilter(value)}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                  <div className="moment-list">
                    {filtered.map((e) => (
                      <button
                        className={`moment-item ${e.id === selectedId ? "active" : ""}`}
                        key={e.id}
                        onClick={() => chooseMoment(e)}
                      >
                        <span className="moment-minute">{e.min}′</span>
                        <span>
                          <strong>{readable(e.type)}</strong>
                          <small>
                            {e.team} · {e.player} · {readable(e.call ?? "")}
                          </small>
                        </span>
                        <ChevronRight size={15} />
                      </button>
                    ))}
                    {!filtered.length && (
                      <p className="small muted">
                        No moments in this category.
                      </p>
                    )}
                  </div>
                </section>
                <div className="focus-card">
                  <span className="eyebrow muted">YOUR PERSPECTIVE</span>
                  <label htmlFor="club-focus">Follow a club</label>
                  <select
                    id="club-focus"
                    value={focus}
                    onChange={(e) => setFocus(e.target.value)}
                  >
                    <option value={match.home}>{clubName(match.home)}</option>
                    <option value={match.away}>{clubName(match.away)}</option>
                  </select>
                  <p>
                    The impact card follows your club. Match evidence stays the
                    same.
                  </p>
                </div>
              </aside>
            </div>
          </>
        )}
        <footer>
          <span>
            <GitBranch size={15} /> PARALLEL MATCH
          </span>
          <span>Synthetic by design. Transparent by default.</span>
          <button className="text-button" onClick={() => setShowHelp(true)}>
            About the model world <ArrowRight size={13} />
          </button>
        </footer>
      </main>
      {showHelp && (
        <div className="modal-backdrop" onClick={() => setShowHelp(false)}>
          <section
            ref={helpRef}
            className="help-modal card"
            role="dialog"
            aria-modal="true"
            aria-label="About the model world"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              autoFocus
              className="icon-button close-modal"
              aria-label="Close about panel"
              onClick={() => setShowHelp(false)}
            >
              <X size={20} />
            </button>
            <span className="eyebrow lime">MODEL WORLD</span>
            <h2>
              Explore possibilities.
              <br />
              Keep the evidence in view.
            </h2>
            <p>
              Every club, player and event in this viewer is fictional. Original
              means the recorded synthetic match. Alternate means a simulated
              continuation after a single changed decision.
            </p>
            <p>
              Each comparison pairs original and alternate simulations using
              shared random seeds. The typical alternate replay is one possible
              path; the confidence interval describes the change across
              rollouts. Season precedent compares different situations and may
              disagree.
            </p>
            <p>
              The pitch shows ball-event positions only. It does not invent
              player tracking. The alternate simulation may disagree with
              historical precedent; neither is proof of what would happen in a
              real match.
            </p>
            <button className="primary" onClick={() => setShowHelp(false)}>
              Back to the match
            </button>
          </section>
        </div>
      )}
    </div>
  );
}
