import { clubName, readable } from "../model";
import type { Match, MatchSummary } from "../types";

const STORY: Record<string, string> = {
  comeback: "Comeback",
  early_red: "Early red card",
  late_winner: "Late winner",
  penalty_drama: "Penalty drama",
  tight_offside: "Tight offside",
};

/** Broadcast-style scoreline. It is the screen's h1: the fixture is the subject. */
export function MatchHeader({
  match,
  matches,
  matchId,
  setMatchId,
  analyst,
}: {
  match: Match;
  matches: MatchSummary[];
  matchId: string;
  setMatchId: (id: string) => void;
  analyst: boolean;
}) {
  const summary = matches.find((m) => m.match_id === match.match_id);
  const story = summary?.story
    ? (STORY[summary.story] ?? readable(summary.story))
    : null;
  return (
    <section className="match-header">
      <div className="match-heading">
        <h1 className="scoreline">
          <span className="team home">
            {clubName(match.home)}
            <abbr title={clubName(match.home)}>{match.home}</abbr>
          </span>
          <span className="score">
            <span>{match.score[0]}</span>
            <span className="score-sep" aria-label="to">
              –
            </span>
            <span>{match.score[1]}</span>
          </span>
          <span className="team away">
            {clubName(match.away)}
            <abbr title={clubName(match.away)}>{match.away}</abbr>
          </span>
        </h1>
        <p className="match-meta">
          <span>Full time</span>
          {story && <span className="story">{story}</span>}
          <span>Synthetic league</span>
          {analyst && (
            <>
              <span>{match.match_id}</span>
              <span>{match.events.length.toLocaleString()} events</span>
              {match.seed !== undefined && <span>seed {match.seed}</span>}
            </>
          )}
        </p>
      </div>
      {matches.length > 1 && (
        <label className="match-picker">
          <span>Match</span>
          <select value={matchId} onChange={(e) => setMatchId(e.target.value)}>
            {matches.map((m) => (
              <option key={m.match_id} value={m.match_id}>
                {m.home && m.away ? `${m.home} v ${m.away}` : m.match_id}
                {m.story ? ` · ${STORY[m.story] ?? readable(m.story)}` : ""}
              </option>
            ))}
          </select>
        </label>
      )}
    </section>
  );
}
