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
import { LanguagePicker } from "./components/LanguagePicker";
import { useI18n } from "./i18n";
import type { ViewProps } from "./components/viewProps";
import type {
  Change,
  Club,
  ForkResult,
  Match,
  MatchEvent,
  MatchSummary,
} from "./types";
const errorText = (error: unknown, fallback: string) =>
  error instanceof Error ? error.message : fallback;
export default function App() {
  const { t } = useI18n();
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
        if (!list.length) throw new Error(t("err.noMatches"));
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
        if (!ctrl.signal.aborted) setLoadError(errorText(e, t("err.generic")));
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
        if (!ctrl.signal.aborted) setLoadError(errorText(e, t("err.generic")));
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
        throw new Error(t("err.anchor"));
      setResult(response);
      setTime(response.divergence.t);
      setAttempt((a) => a + 1);
    } catch (e) {
      if (!ctrl.signal.aborted) setForkError(errorText(e, t("err.generic")));
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
        <nav className="view-switch" aria-label={t("nav.view")}>
          <button
            aria-pressed={view === "fan"}
            className={view === "fan" ? "active" : ""}
            onClick={() => setView("fan")}
          >
            {t("nav.fan")}
          </button>
          <button
            aria-pressed={view === "analyst"}
            className={view === "analyst" ? "active" : ""}
            onClick={() => setView("analyst")}
          >
            {t("nav.analyst")}
          </button>
        </nav>
        <div className="topbar-right">
          <LanguagePicker />
          <AgentStatus />
          <span className="source-pill">
            <span className="status-dot" />
            {sourceMode === "fixtures" ? t("src.offline") : t("src.live")}
          </span>
          <button
            className="icon-button"
            onClick={() => setShowHelp(true)}
            aria-label={t("help.open")}
          >
            <CircleHelp size={19} />
          </button>
        </div>
      </header>
      <main id="main" tabIndex={-1}>
        <div className="sr-only" role="status" aria-live="polite">
          {forkLoading
            ? t("live.running")
            : result
              ? t("live.ready", { description: result.description })
              : ""}
        </div>
        {loadError ? (
          <div className="error-panel" role="alert">
            <h1>{t("load.error")}</h1>
            <p>{loadError}</p>
            <button className="primary" onClick={() => setRetry((x) => x + 1)}>
              {t("load.retry")}
            </button>
            <p className="small">{t("load.noFallback")}</p>
          </div>
        ) : !match || !viewProps ? (
          <div className="loading-panel" role="status">
            <LoaderCircle className="spin" /> {t("load.loading")}
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
              <p className="fixture-notice">{t("offline.notice")}</p>
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
        <span>{t("footer.synthetic")}</span>
        <button className="text-button" onClick={() => setShowHelp(true)}>
          {t("footer.about")} <ArrowRight size={13} />
        </button>
      </footer>
      {showHelp && (
        <div className="modal-backdrop" onClick={() => setShowHelp(false)}>
          <section
            ref={helpRef}
            className="help-modal"
            role="dialog"
            aria-modal="true"
            aria-label={t("footer.about")}
            onClick={(e) => e.stopPropagation()}
          >
            <button
              className="icon-button close-modal"
              aria-label={t("help.close")}
              onClick={() => setShowHelp(false)}
            >
              <X size={20} />
            </button>
            <h2>{t("help.title")}</h2>
            <p>{t("help.p1")}</p>
            <p>{t("help.p2")}</p>
            <p>{t("help.p3")}</p>
            <button className="primary" onClick={() => setShowHelp(false)}>
              {t("help.back")}
            </button>
          </section>
        </div>
      )}
    </div>
  );
}
