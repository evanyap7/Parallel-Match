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
  word,
} from "../model";
import { Pitch } from "./Pitch";
import { Transport } from "./Transport";
import { MomentRibbon } from "./MomentRibbon";
import { AgentNarrative } from "./AgentPanels";
import { useI18n, type T } from "../i18n";
import { DecisionControls } from "./DecisionControls";
import type { Change, ForkResult, MatchEvent } from "../types";
import type { ViewProps } from "./viewProps";

/** The opening words of the answer, matching the question the fan asked. */
function answerLead(change: Change, t: T, e?: MatchEvent) {
  switch (change.type) {
    case "flip_call":
      if (e?.call === "penalty") return t("lead.noPenalty");
      if (e?.call === "offside") return t("lead.flagDown");
      if (e?.call === "onside") return t("lead.flagUp");
      if (e?.call === "no_foul") return t("lead.foulGiven");
      return t("lead.noFoul");
    case "not_sent_off":
      return t("lead.keptOn");
    case "shot_outcome":
      return change.outcome === "goal" ? t("lead.shotIn") : t("lead.noGoal");
    case "card":
      return change.card
        ? t("lead.card", { card: word(change.card, t) })
        : t("lead.noCard");
    case "substitution":
      return t("lead.sub");
    case "tactics":
      return t("lead.tactics");
  }
}

/** Fan view: a story with one question and one answer. Numbers stay out of
    the way; the analyst view carries the evidence. */
export function FanView(p: ViewProps) {
  const { t } = useI18n();
  const { match, selected, change, result, transport } = p;
  const key = useMemo(
    () => keyMoments(p.moments, 8, p.selectedId),
    [p.moments, p.selectedId],
  );
  const ask = change ? whatIfQuestion(change, selected, t) : undefined;
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
              <h2 id="call-title">{momentHeadline(selected, t)}</h2>
              <p className="call-law">
                {selected.law ? `${t("fan.law", { law: selected.law })} ` : ""}
                {t("fan.notWrong")}
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
                    <LoaderCircle size={18} className="spin" />{" "}
                    {t("fan.replaying")}
                  </>
                ) : (
                  <>
                    {ask ?? t("fan.nothing")}{" "}
                    <ArrowRight size={18} />
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
                  {t("fan.offlineOne")}{" "}
                  <button className="text-button" onClick={p.loadExample}>
                    {t("fan.showExample")}
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
                  <label htmlFor="fan-what-if">{t("fan.askOwn")}</label>
                  <div className="ask-row">
                    <input
                      id="fan-what-if"
                      maxLength={300}
                      value={p.whatIf}
                      onChange={(e) => p.setWhatIf(e.target.value)}
                      placeholder={t("fan.placeholder")}
                    />
                    <button
                      className="secondary"
                      disabled={!p.whatIf.trim() || p.forkLoading}
                    >
                      {t("fan.ask")}
                    </button>
                  </div>
                </form>
              )}
            </>
          ) : (
            <p>{t("fan.noMoments")}</p>
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
  const { t, r } = useI18n();
  const { result, match, side, selected } = p;
  const club = clubName(p.focus);
  const { before, after } = winChance(result, side);
  const ci = result.uncertainty.shift_ci95[side];
  const uncertain = ci[0] <= 0 && ci[1] >= 0;
  const lead = answerLead(result.change, t, selected);
  const h = result.history;
  return (
    <section className="verdict-sheet" aria-labelledby="verdict-title">
      <div className="verdict-main">
        <h2 id="verdict-title" className="verdict-line">
          {before !== null && after !== null ? (
            r(
              after < before
                ? "verdict.drops"
                : after > before
                  ? "verdict.rises"
                  : "verdict.stays",
              {
                lead,
                club,
                a: <b>{percent(before)}</b>,
                b: <b className="alt">{percent(after)}</b>,
              },
            )
          ) : (
            t("verdict.unknown", { lead })
          )}
        </h2>
        {uncertain && (
          <p className="verdict-caveat">
            {t("verdict.caveat")}
          </p>
        )}
        <div className="see-for" role="group" aria-label={t("verdict.seeFor")}>
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
              <span>{t("verdict.real")}</span>
              <i style={{ width: percent(before) }} />
              <b>{percent(before)}</b>
            </div>
            <div className="win-bar alt">
              <span>{t("verdict.whatIf")}</span>
              <i style={{ width: percent(after) }} />
              <b>{percent(after)}</b>
            </div>
          </div>
        )}
        <div className="likely-score">
          <span>{t("verdict.likely")}</span>
          <div>
            <span className="score-chip">
              {scoreText(result.original.final_score)}
              <small>{t("verdict.realTag")}</small>
            </span>
            <span className="score-chip alt">
              {scoreText(result.alternate.final_score)}
              <small>{t("verdict.whatIfTag")}</small>
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
          {t(
            h.agrees_with_simulation === true
              ? "verdict.histSame"
              : h.agrees_with_simulation === false
                ? "verdict.histOther"
                : "verdict.histNone",
            { n: h.n },
          )}
        </p>
      )}
      <p className="small muted">
        {t("verdict.basis", { n: result.rollouts.toLocaleString() })}
      </p>
    </section>
  );
}
