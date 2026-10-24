import { useId } from "react";
import { Radio, GitBranch } from "lucide-react";
import { clockLabel, describe, eventAt, scoreText } from "../model";
import type { MatchEvent } from "../types";

interface Props {
  events: MatchEvent[];
  time: number;
  home: string;
  away: string;
  alternate?: boolean;
  pending?: boolean;
  divergence?: number;
}
export function Pitch({
  events,
  time,
  home,
  away,
  alternate = false,
  pending = false,
  divergence,
}: Props) {
  const id = useId().replaceAll(":", "");
  const current = eventAt(events, time);
  const recent = events
    .filter((e) => e.t <= time && e.t >= time - 25 && e.xy)
    .slice(-8);
  const ball = recent.at(-1)?.xy ?? current?.xy ?? [52.5, 34];
  const trail = recent.map((e) => e.xy!.join(",")).join(" ");
  const score = current?.score ?? [0, 0];
  return (
    <section
      className={`pitch-panel ${alternate ? "alternate" : ""}`}
      aria-label={`${alternate ? "Alternate" : "Original"} match replay`}
    >
      <div className="pitch-heading">
        <span className="pitch-title">
          {alternate ? <GitBranch size={13} /> : <Radio size={13} />}{" "}
          {alternate ? "Alternate timeline" : "Original timeline"}
        </span>
        <span className="live-label">
          {pending ? "Awaiting events" : "Synthetic replay"}
        </span>
      </div>
      <div className="scorebug">
        <span className="team-dot home" />
        {home}
        <strong>
          {pending ? "\u2013 : \u2013" : scoreText(score as [number, number])}
        </strong>
        {away}
        <span className="team-dot away" />
        <span className="clock">{clockLabel(time)}</span>
      </div>
      <div className="pitch-wrap">
        <div className="pitch-board">
          <svg
            viewBox="-6 -6 117 80"
            role="img"
            aria-label={
              pending
                ? "Alternate pitch waiting for simulator events"
                : `Ball event replay at ${clockLabel(time)}. ${describe(current)}`
            }
          >
            <defs>
              <pattern
                id={`stripes-${id}`}
                width="21"
                height="68"
                patternUnits="userSpaceOnUse"
              >
                <rect width="10.5" height="68" fill="#0a0a0a" opacity=".035" />
              </pattern>
            </defs>
            <rect
              x="0"
              y="0"
              width="105"
              height="68"
              rx=".5"
              fill={alternate ? "var(--pitch-alt)" : "var(--pitch)"}
            />
            <rect width="105" height="68" fill={`url(#stripes-${id})`} />
            <g fill="none" stroke="var(--pitch-line)" strokeWidth=".32">
              <rect width="105" height="68" />
              <path d="M52.5 0V68" />
              <circle cx="52.5" cy="34" r="9.15" />
              <path d="M0 13.84H16.5V54.16H0 M105 13.84H88.5V54.16H105 M0 24.84H5.5V43.16H0 M105 24.84H99.5V43.16H105 M0 30.34H-2V37.66H0 M105 30.34H107V37.66H105" />
              <path d="M16.5 26.7A9.15 9.15 0 0 1 16.5 41.3 M88.5 26.7A9.15 9.15 0 0 0 88.5 41.3" />
            </g>
            <g fill="var(--pitch-line)">
              <circle cx="11" cy="34" r=".4" />
              <circle cx="94" cy="34" r=".4" />
              <circle cx="52.5" cy="34" r=".4" />
            </g>
            {!pending && (
              <>
                <polyline
                  points={trail}
                  fill="none"
                  stroke={alternate ? "var(--hue)" : "var(--ink)"}
                  strokeWidth=".6"
                  strokeDasharray="1.5 1"
                  opacity=".8"
                />
                {recent.slice(0, -1).map((e, i) => (
                  <circle
                    key={e.id}
                    cx={e.xy![0]}
                    cy={e.xy![1]}
                    r=".65"
                    fill={alternate ? "var(--hue)" : "var(--ink)"}
                    opacity={((i + 1) / recent.length) * 0.6}
                  />
                ))}
                <circle
                  cx={ball[0]}
                  cy={ball[1]}
                  r="3.4"
                  fill="none"
                  stroke={alternate ? "var(--hue)" : "var(--ink)"}
                  strokeWidth=".4"
                  opacity=".45"
                />
                <circle
                  cx={ball[0]}
                  cy={ball[1]}
                  r="1.15"
                  fill="#fff"
                  stroke={alternate ? "var(--hue)" : "var(--ink)"}
                  strokeWidth=".5"
                />
              </>
            )}
          </svg>
          {!pending && (
            <span
              className="ball-tag"
              style={{
                left: `${((Math.min(92, Math.max(13, ball[0])) + 6) / 117) * 100}%`,
                top: `${((Math.max(6, ball[1] - 5) + 6) / 80) * 100}%`,
              }}
            >
              {current?.player ?? "BALL"}
            </span>
          )}
        </div>
        <p className="attack-note">{home} attacks →</p>
        {pending && (
          <div className="pending-pitch">
            <GitBranch size={25} />
            <strong>A different story starts here.</strong>
            <p>
              No alternate events have been supplied yet.
              <br />
              The replay will appear when the simulator provides them.
            </p>
            <span>Original events are never used as an alternate.</span>
          </div>
        )}
        {!pending && divergence !== undefined && time >= divergence && (
          <span className="forked-badge">After the fork</span>
        )}
      </div>
      <div className="pitch-caption">
        <span className={`status-dot ${pending ? "muted" : ""}`} />
        <span>
          {pending
            ? "Alternate replay pending · model world"
            : describe(current)}
        </span>
      </div>
      <p className="pitch-note">
        {pending
          ? "No invented player movement or match outcome."
          : "Recorded ball-event positions · schematic replay, not player tracking."}
      </p>
    </section>
  );
}
