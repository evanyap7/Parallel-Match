import { clubName, readable } from "../model";
import { useI18n, type Key } from "../i18n";
import type { Match, MatchSummary } from "../types";

const STORIES = [
  "comeback",
  "early_red",
  "late_winner",
  "penalty_drama",
  "tight_offside",
];

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
  const { t } = useI18n();
  const storyName = (s: string) =>
    STORIES.includes(s) ? t(`story.${s}` as Key) : readable(s);
  const summary = matches.find((m) => m.match_id === match.match_id);
  const story = summary?.story ? storyName(summary.story) : null;
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
            <span className="score-sep" aria-label={t("match.to")}>
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
          <span>{t("match.fullTime")}</span>
          {story && <span className="story">{story}</span>}
          <span>{t("match.synthetic")}</span>
          {analyst && (
            <>
              <span>{match.match_id}</span>
              <span>{t("match.events", { n: match.events.length.toLocaleString() })}</span>
              {match.seed !== undefined && <span>{t("match.seed", { n: match.seed })}</span>}
            </>
          )}
        </p>
      </div>
      {matches.length > 1 && (
        <label className="match-picker">
          <span>{t("match.pick")}</span>
          <select value={matchId} onChange={(e) => setMatchId(e.target.value)}>
            {matches.map((m) => (
              <option key={m.match_id} value={m.match_id}>
                {m.home && m.away ? `${m.home} v ${m.away}` : m.match_id}
                {m.story ? ` · ${storyName(m.story)}` : ""}
              </option>
            ))}
          </select>
        </label>
      )}
    </section>
  );
}
