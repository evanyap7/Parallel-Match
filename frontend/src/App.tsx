import { useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowRight,
  CircleHelp,
  GitBranch,
  LoaderCircle,
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
import { alternateEvents, changesFor } from "./model";
import { parseWhatIf } from "./agents";
import { toEngineChange } from "./parser-adapter";
import { AgentStatus } from "./components/AgentPanels";
import { FanView } from "./components/FanView";
import { AnalystView } from "./components/AnalystView";
import { MatchHeader } from "./components/MatchHeader";
import type { ViewProps } from "./components/viewProps";
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
    helpRef.current?.querySelector<HTMLElement>("button")?.focus();
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
  const viewProps: ViewProps | undefined = match && {
    match,
    clubs,
    moments: apiMoments,
    selected,
    selectedId,
    chooseMoment,
    change,
    changeReady: Boolean(changeReady),
    canMock,
    updateChange,
    explore: (fromText?: boolean) => void explore(fromText),
    cancel: () => {
      forkController.current?.abort();
      setForkLoading(false);
    },
    loadExample: () => {
      const e = match.events.find((ev) => ev.id === fixtureEvents[matchId]);
      if (e) chooseMoment(e);
    },
    forkLoading,
    forkError,
    result,
    forkEvents,
    attempt,
    whatIf,
    setWhatIf,
    focus,
    setFocus,
    side,
    transport: { time, end, playing, speed, setTime, setPlaying, setSpeed },
    liveEngine: sourceMode === "api",
  };
  return (
    <div className={`app-shell view-${view}`}>
      <header className="topbar">
        <a href="#main" className="brand">
          <GitBranch size={20} aria-hidden="true" />
          Parallel Match
        </a>
        <nav className="view-switch" aria-label="View">
          <button
            aria-pressed={view === "fan"}
            className={view === "fan" ? "active" : ""}
            onClick={() => setView("fan")}
          >
            Fan
          </button>
          <button
            aria-pressed={view === "analyst"}
            className={view === "analyst" ? "active" : ""}
            onClick={() => setView("analyst")}
          >
            Analyst
          </button>
        </nav>
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
      <main id="main" tabIndex={-1}>
        <div className="sr-only" role="status" aria-live="polite">
          {forkLoading
            ? "Running the comparison."
            : result
              ? `Comparison ready: ${result.description}`
              : ""}
        </div>
        {loadError ? (
          <div className="error-panel" role="alert">
            <h1>We couldn’t load the match.</h1>
            <p>{loadError}</p>
            <button className="primary" onClick={() => setRetry((x) => x + 1)}>
              Try again
            </button>
            <p className="small">
              API errors never silently fall back to fixture data.
            </p>
          </div>
        ) : !match || !viewProps ? (
          <div className="loading-panel" role="status">
            <LoaderCircle className="spin" /> Loading the match…
          </div>
        ) : (
          <>
            <MatchHeader
              match={match}
              matches={matches}
              matchId={matchId}
              setMatchId={setMatchId}
              analyst={view === "analyst"}
            />
            {sourceMode === "fixtures" && (
              <p className="fixture-notice">
                Offline mode: replays come from the completed simulator, with
                one featured comparison per match. Connect the engine to explore
                every decision.
              </p>
            )}
            {view === "fan" ? (
              <FanView {...viewProps} />
            ) : (
              <AnalystView {...viewProps} />
            )}
          </>
        )}
      </main>
      <footer className="site-footer">
        <span>Parallel Match</span>
        <span>Every club, player and match here is synthetic.</span>
        <button className="text-button" onClick={() => setShowHelp(true)}>
          About the model world <ArrowRight size={13} />
        </button>
      </footer>
      {showHelp && (
        <div className="modal-backdrop" onClick={() => setShowHelp(false)}>
          <section
            ref={helpRef}
            className="help-modal"
            role="dialog"
            aria-modal="true"
            aria-label="About the model world"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              className="icon-button close-modal"
              aria-label="Close about panel"
              onClick={() => setShowHelp(false)}
            >
              <X size={20} />
            </button>
            <h2>One decision. A different match.</h2>
            <p>
              Every club, player and event here is fictional. Real means the
              recorded synthetic match. What if means a simulated continuation
              after one changed decision.
            </p>
            <p>
              Each comparison plays hundreds of paired simulations from the
              moment of the decision, sharing random numbers, so the difference
              is the decision and not luck. The typical alternate replay is one
              possible path. Season precedent compares different matches and may
              disagree.
            </p>
            <p>
              The pitch shows ball-event positions only, not player tracking.
              Neither the simulation nor precedent is proof of what would happen
              in a real match.
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
