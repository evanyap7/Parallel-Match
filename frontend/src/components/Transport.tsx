import { GitBranch, Pause, Play, RotateCcw } from "lucide-react";
import { clockLabel, word } from "../model";
import { useI18n } from "../i18n";
import type { ForkResult, MatchEvent } from "../types";
import type { TransportState } from "./viewProps";

const SPEEDS = [6, 12, 24, 48];

/** Shared replay clock for both pitches. The analyst version shows every
    moment and the speed control; the fan version only the key moments. */
export function Transport({
  state,
  markers,
  selectedId,
  onSelect,
  result,
  detailed = false,
}: {
  state: TransportState;
  markers: MatchEvent[];
  selectedId: string;
  onSelect: (e: MatchEvent) => void;
  result?: ForkResult;
  detailed?: boolean;
}) {
  const { t } = useI18n();
  const { time, end, playing, speed, setTime, setPlaying, setSpeed } = state;
  const at = (t: number) => `${end ? (t / end) * 100 : 0}%`;
  return (
    <section
      className={`transport${detailed ? " detailed" : ""}`}
      aria-label={t("tr.controls")}
    >
      <div className="transport-row">
        <button
          className="play-button"
          aria-label={playing ? t("tr.pause") : t("tr.play")}
          onClick={() => {
            if (time >= end) setTime(0);
            setPlaying((p) => !p);
          }}
        >
          {playing ? <Pause size={18} /> : <Play size={18} />}
        </button>
        <button
          className="icon-button"
          aria-label={t("tr.restart")}
          onClick={() => {
            setTime(0);
            setPlaying(false);
          }}
        >
          <RotateCcw size={16} />
        </button>
        <span className="transport-clock">
          <strong>{clockLabel(time)}</strong>
          <span> / {clockLabel(end)}</span>
        </span>
        {detailed && (
          <label className="speed-label">
            {t("tr.speed")}
            <select
              value={speed}
              onChange={(e) => setSpeed(Number(e.target.value))}
            >
              {SPEEDS.map((s) => (
                <option key={s} value={s}>
                  {s}×
                </option>
              ))}
            </select>
          </label>
        )}
      </div>
      <div className="scrubber">
        <input
          type="range"
          min="0"
          max={end}
          step="1"
          value={time}
          aria-label={t("tr.position")}
          aria-valuetext={clockLabel(time)}
          onChange={(e) => {
            setTime(Number(e.target.value));
            setPlaying(false);
          }}
        />
        <div className="moment-markers">
          {markers.map((e) => (
            <button
              key={e.id}
              aria-label={t("tr.select", { type: word(e.type, t), min: e.min })}
              title={`${e.min}′ · ${word(e.type, t)}`}
              aria-current={e.id === selectedId ? "true" : undefined}
              className={e.id === selectedId ? "selected" : ""}
              style={{ left: at(e.t) }}
              onClick={() => onSelect(e)}
            />
          ))}
          {result && (
            <span
              className="divergence-pin"
              style={{ left: at(result.divergence.t) }}
            >
              <GitBranch size={12} /> {t("tr.fork", { min: result.divergence.min })}
            </span>
          )}
        </div>
      </div>
      <div className="timeline-labels" aria-hidden="true">
        <span>{t("tr.kickoff")}</span>
        <span>{t("match.fullTime")}</span>
      </div>
    </section>
  );
}
