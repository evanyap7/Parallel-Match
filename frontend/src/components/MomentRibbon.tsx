import { clubName, momentHeadline, momentTag } from "../model";
import type { Match, MatchEvent } from "../types";

const GAP = 7; // percent of the match a label needs before the next one on its row

/** A broadcast match timeline: home moments above the line, away below. */
export function MomentRibbon({
  moments,
  match,
  end,
  selectedId,
  onSelect,
}: {
  moments: MatchEvent[];
  match: Match;
  end: number;
  selectedId: string;
  onSelect: (e: MatchEvent) => void;
}) {
  const last: Record<string, number[]> = { home: [], away: [] };
  const placed = moments.map((e) => {
    const side = e.team === match.away ? "away" : "home";
    const pos = end ? (e.t / end) * 100 : 0;
    const rows = last[side];
    let level = rows.findIndex((p) => pos - p >= GAP);
    if (level === -1) level = rows.length;
    rows[level] = pos;
    return { e, side, pos, level: Math.min(level, 2) };
  });
  return (
    <section className="ribbon" aria-labelledby="ribbon-title">
      <div className="ribbon-head">
        <h2 id="ribbon-title">Key moments</h2>
        <p>Pick one, then replay the match with a different call.</p>
      </div>
      <div className="ribbon-track">
        <span className="ribbon-side home" aria-hidden="true">
          {clubName(match.home)}
        </span>
        <span className="ribbon-side away" aria-hidden="true">
          {clubName(match.away)}
        </span>
        <div className="ribbon-line" aria-hidden="true">
          <span style={{ left: "0%" }}>0′</span>
          <span style={{ left: `${end ? (2700 / end) * 100 : 50}%` }}>45′</span>
          <span style={{ left: "100%" }}>FT</span>
        </div>
        <ol className="ribbon-pins">
          {placed.map(({ e, side, pos, level }) => (
            <li
              key={e.id}
              className={`pin ${side} level-${level}${e.id === selectedId ? " selected" : ""}`}
              style={{ left: `${pos}%` }}
            >
              <button
                aria-current={e.id === selectedId ? "true" : undefined}
                onClick={() => onSelect(e)}
              >
                <span className="pin-min">{e.min}′</span>
                <span className="pin-tag">{momentTag(e)}</span>
                <span className="pin-label">{momentHeadline(e)}</span>
              </button>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
