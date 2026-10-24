import { GitBranch, Pause, Play, RotateCcw } from "lucide-react";
import { clockLabel, readable } from "../model";
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
  const { time, end, playing, speed, setTime, setPlaying, setSpeed } = state;
  const at = (t: number) => `${end ? (t / end) * 100 : 0}%`;
  return (
    <section
      className={`transport${detailed ? " detailed" : ""}`}
      aria-label="Replay controls"
    >
      <div className="transport-row">
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
        <span className="transport-clock">
          <strong>{clockLabel(time)}</strong>
          <span> / {clockLabel(end)}</span>
        </span>
        {detailed && (
          <label className="speed-label">
            Speed
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
          aria-label="Match replay position"
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
              aria-label={`Select ${readable(e.type)} at ${e.min} minutes`}
              title={`${e.min}′ · ${readable(e.type)}`}
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
              <GitBranch size={12} /> Fork {result.divergence.min}′
            </span>
          )}
        </div>
      </div>
      <div className="timeline-labels" aria-hidden="true">
        <span>Kick-off</span>
        <span>Full time</span>
      </div>
    </section>
  );
}
