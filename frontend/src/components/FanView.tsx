import { useMemo } from "react";
import { ArrowRight, LoaderCircle } from "lucide-react";
import {
  clubName,
  keyMoments,
  momentHeadline,
  percent,
  scoreText,
  whatIfQuestion,
  winChance,
} from "../model";
import { Pitch } from "./Pitch";
import { Transport } from "./Transport";
import { MomentRibbon } from "./MomentRibbon";
import { AgentNarrative } from "./AgentPanels";
import { DecisionControls } from "./DecisionControls";
import type { Change, ForkResult, MatchEvent } from "../types";
import type { ViewProps } from "./viewProps";

/** The opening words of the answer, matching the question the fan asked. */
function answerLead(change: Change, e?: MatchEvent) {
  switch (change.type) {
    case "flip_call":
      if (e?.call === "penalty") return "Without the penalty";
      if (e?.call === "offside") return "With the flag kept down";
      if (e?.call === "onside") return "With the offside flag";
      if (e?.call === "no_foul") return "With the foul given";
      return "Without the foul";
    case "not_sent_off":
      return "With the player kept on";
    case "shot_outcome":
      return change.outcome === "goal"
        ? "If the shot had gone in"
        : "Without the goal";
    case "card":
      return change.card ? `With a ${change.card} card` : "Without the card";
    case "substitution":
      return "With your change";
    case "tactics":
      return "With the new tactics";
  }
}

/** Fan view: a story with one question and one answer. Numbers stay out of
    the way; the analyst view carries the evidence. */
export function FanView(p: ViewProps) {
  const { match, selected, change, result, transport } = p;
  const key = useMemo(
    () => keyMoments(p.moments, 8, p.selectedId),
    [p.moments, p.selectedId],
  );
  const ask = change ? whatIfQuestion(change, selected) : undefined;
  return (
    <div className="fan">
      <MomentRibbon
        moments={key}
        match={match}
        end={transport.end}
        selectedId={p.selectedId}
        onSelect={p.chooseMoment}
      />
      <div className="fan-stage">
        <section className="call-card" aria-labelledby="call-title">
          {selected ? (
            <>
              <p className="call-minute">{selected.min}′</p>
              <h2 id="call-title">{momentHeadline(selected)}</h2>
              <p className="call-law">
                {selected.law ? `Decided under ${selected.law}. ` : ""}
                Replaying it does not mean the call was wrong.
              </p>
              {p.liveEngine && change?.type === "substitution" && (
                <DecisionControls
                  event={selected}
                  match={match}
                  clubs={p.clubs}
                  change={change}
                  onChange={p.updateChange}
                />
              )}
              <button
                className="primary ask"
                disabled={!p.changeReady || !p.canMock || p.forkLoading}
                onClick={() => p.explore()}
              >
                {p.forkLoading ? (
                  <>
                    <LoaderCircle size={18} className="spin" /> Replaying the
                    match…
                  </>
                ) : (
                  <>
                    {ask ?? "Nothing to change at this moment"}{" "}
                    <ArrowRight size={18} />
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
                  Offline mode has one example per match.{" "}
                  <button className="text-button" onClick={p.loadExample}>
                    Show the example
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
                  onSubmit={(e) => {
                    e.preventDefault();
                    p.explore(true);
                  }}
                >
                  <label htmlFor="fan-what-if">Or ask in your own words</label>
                  <div className="ask-row">
                    <input
                      id="fan-what-if"
                      maxLength={300}
                      value={p.whatIf}
                      onChange={(e) => p.setWhatIf(e.target.value)}
                      placeholder="What if that wasn’t a penalty?"
                    />
                    <button
                      className="secondary"
                      disabled={!p.whatIf.trim() || p.forkLoading}
                    >
                      Ask
                    </button>
                  </div>
                </form>
              )}
            </>
          ) : (
            <p>No moments to replay in this match.</p>
          )}
        </section>
        <div className="fan-broadcast">
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
            state={transport}
            markers={key}
            selectedId={p.selectedId}
            onSelect={p.chooseMoment}
            result={result}
          />
        </div>
      </div>
      {result && <FanVerdict {...p} result={result} />}
    </div>
  );
}

function FanVerdict(p: ViewProps & { result: ForkResult }) {
  const { result, match, side, selected } = p;
  const club = clubName(p.focus);
  const clubs = club.endsWith("s") ? `${club}’` : `${club}’s`;
  const { before, after } = winChance(result, side);
  const ci = result.uncertainty.shift_ci95[side];
  const uncertain = ci[0] <= 0 && ci[1] >= 0;
  const lead = answerLead(result.change, selected);
  const h = result.history;
  return (
    <section className="verdict-sheet" aria-labelledby="verdict-title">
      <div className="verdict-main">
        <h2 id="verdict-title" className="verdict-line">
          {before !== null && after !== null ? (
            <>
              {lead}, {clubs} chance of winning{" "}
              {after < before ? "drops" : after > before ? "rises" : "stays"}{" "}
              from <b>{percent(before)}</b> to{" "}
              <b className="alt">{percent(after)}</b>.
            </>
          ) : (
            `${lead}, the rest of the match plays out differently.`
          )}
        </h2>
        {uncertain && (
          <p className="verdict-caveat">
            The simulations split on the direction, so treat this as uncertain.
          </p>
        )}
        <div className="see-for" role="group" aria-label="See it for">
          {[match.home, match.away].map((code) => (
            <button
              key={code}
              aria-pressed={p.focus === code}
              className={p.focus === code ? "active" : ""}
              onClick={() => p.setFocus(code)}
            >
              {clubName(code)}
            </button>
          ))}
        </div>
      </div>
      <div className="verdict-figures">
        {before !== null && after !== null && (
          <div className="win-bars">
            <div className="win-bar">
              <span>Real match</span>
              <i style={{ width: percent(before) }} />
              <b>{percent(before)}</b>
            </div>
            <div className="win-bar alt">
              <span>What if</span>
              <i style={{ width: percent(after) }} />
              <b>{percent(after)}</b>
            </div>
          </div>
        )}
        <div className="likely-score">
          <span>Most likely final score</span>
          <div>
            <span className="score-chip">
              {scoreText(result.original.final_score)}
              <small>real</small>
            </span>
            <span className="score-chip alt">
              {scoreText(result.alternate.final_score)}
              <small>what if</small>
            </span>
          </div>
        </div>
      </div>
      <AgentNarrative
        key={`${match.match_id}:${p.selectedId}:${p.attempt}`}
        result={result}
        variant="fan"
      />
      {h && (
        <p className="history-line">
          In {h.n} similar calls this season,{" "}
          {h.agrees_with_simulation === true
            ? "history points the same way."
            : h.agrees_with_simulation === false
              ? "history points the other way, so treat this with care."
              : "there is not enough history to compare."}
        </p>
      )}
      <p className="small muted">
        Based on {result.rollouts.toLocaleString()} simulations of the rest of
        the match. A model world, not a prediction.
      </p>
    </section>
  );
}
