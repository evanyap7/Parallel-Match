import type { Change, Club, Match, MatchEvent } from "../types";
import { changeLabel, changesFor, clubName } from "../model";

export function availablePlayers(
  club: Club | undefined,
  match: Match,
  step: number,
) {
  if (!club) return { on: [], bench: [] };
  const active = new Set(club.squad.slice(0, 11).map((p) => p.id));
  const played = new Set(active);
  for (const e of match.events) {
    if (e.step >= step) break;
    if (e.team !== club.code) continue;
    if (e.type === "substitution") {
      if (e.off) active.delete(e.off);
      if (e.player) {
        active.add(e.player);
        played.add(e.player);
      }
    }
    if (e.type === "card" && e.color === "red" && e.player)
      active.delete(e.player);
  }
  return {
    on: club.squad.filter((p) => active.has(p.id)),
    bench: club.squad.filter((p) => !played.has(p.id)),
  };
}

export function DecisionControls({
  event,
  match,
  clubs,
  change,
  onChange,
}: {
  event: MatchEvent;
  match: Match;
  clubs: Club[];
  change?: Change;
  onChange: (c: Change) => void;
}) {
  const options = [...changesFor(event)];
  if (event.type === "foul")
    options.push(
      { type: "card", card: null },
      { type: "card", card: "yellow" },
      { type: "card", card: "red" },
    );
  if (!options.some((c) => c.type === "substitution"))
    options.push({ type: "substitution" });
  options.push({ type: "tactics", team: match.home, set: { press: 0.8 } });
  const key = (c: Change) =>
    c.type === "shot_outcome"
      ? `${c.type}:${c.outcome}`
      : c.type === "card"
        ? `${c.type}:${c.card}`
        : c.type;
  const team =
    change && "team" in change ? (change.team ?? match.home) : match.home;
  const players = availablePlayers(
    clubs.find((c) => c.code === team),
    match,
    event.step,
  );
  function switchTeam(code: string) {
    if (change?.type === "tactics") onChange({ ...change, team: code });
    else {
      const pool = availablePlayers(
        clubs.find((c) => c.code === code),
        match,
        event.step,
      );
      onChange({
        type: "substitution",
        team: code,
        off: pool.on[0]?.id,
        on: pool.bench[0]?.id,
      });
    }
  }
  return (
    <div className="decision-controls">
      <label>
        Choose an alternative
        <select
          value={change ? key(change) : ""}
          onChange={(e) => {
            const option = options.find((c) => key(c) === e.target.value)!;
            if (option.type === "substitution") {
              const pool = availablePlayers(
                clubs.find((c) => c.code === match.home),
                match,
                event.step,
              );
              onChange({
                ...option,
                team: match.home,
                off: pool.on[0]?.id,
                on: pool.bench[0]?.id,
              });
            } else onChange(option);
          }}
        >
          {options.map((c) => (
            <option key={key(c)} value={key(c)}>
              {changeLabel(c, event)}
            </option>
          ))}
        </select>
      </label>
      {(change?.type === "substitution" || change?.type === "tactics") && (
        <>
          <label>
            Team
            <select value={team} onChange={(e) => switchTeam(e.target.value)}>
              {[match.home, match.away].map((code) => (
                <option key={code} value={code}>
                  {clubName(code)}
                </option>
              ))}
            </select>
          </label>
          {change.type === "tactics" ? (
            <label>
              Pressing intensity · {Math.round(change.set.press * 100)}%
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={change.set.press}
                onChange={(e) =>
                  onChange({
                    ...change,
                    set: { press: Number(e.target.value) },
                  })
                }
              />
            </label>
          ) : (
            <>
              <label>
                Player off
                <select
                  value={change.off ?? ""}
                  onChange={(e) =>
                    onChange({ ...change, team, off: e.target.value })
                  }
                >
                  <option value="" disabled>
                    Select a player
                  </option>
                  {players.on.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name} · {p.pos} ({p.id})
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Player on
                <select
                  value={change.on ?? ""}
                  onChange={(e) =>
                    onChange({ ...change, team, on: e.target.value })
                  }
                >
                  <option value="" disabled>
                    Select a player
                  </option>
                  {players.bench.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name} · {p.pos} ({p.id})
                    </option>
                  ))}
                </select>
              </label>
              {!players.bench.length && (
                <p className="small muted">
                  No unused players available. Choose another intervention.
                </p>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}
