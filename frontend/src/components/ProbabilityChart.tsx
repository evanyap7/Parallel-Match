import type { ForkResult } from "../types";
import { percent } from "../model";
export function ProbabilityChart({
  result,
  home,
}: {
  result: ForkResult;
  home: string;
}) {
  const a = result.original.win_prob,
    b = result.alternate.win_prob;
  const end = Math.max(90, ...a.map((p) => p.min), ...b.map((p) => p.min));
  const x = (min: number) => 34 + (min / end) * 446;
  const y = (p: number) => 140 - p * 120;
  const path = (values: typeof a) =>
    values
      .map((p, i) => `${i === 0 ? "M" : "L"}${x(p.min)},${y(p.home)}`)
      .join(" ");
  return (
    <section className="probability card">
      <div className="section-title">
        <h3>{home} win probability</h3>
        <span className="small-label">
          {result.placeholder ? "PLACEHOLDER CURVES" : "MODEL ESTIMATES"}
        </span>
      </div>
      <div className="chart-legend">
        <span>
          <i className="legend-line original" />
          Original
        </span>
        <span>
          <i className="legend-line alternate" />
          Alternate
        </span>
        <span className="chart-key">Full scenario comparison</span>
      </div>
      <svg
        viewBox="0 0 500 170"
        role="img"
        aria-label={`${home} win probability comparison. ${result.placeholder ? "All curve values are fixture placeholders." : "Simulation estimates, not real-world predictions."}`}
      >
        {[0, 0.5, 1].map((v) => (
          <g key={v}>
            <line x1="34" x2="480" y1={y(v)} y2={y(v)} stroke="#ffffff12" />
            <text x="0" y={y(v) + 4} fill="#7f8d90" fontSize="10">
              {percent(v)}
            </text>
          </g>
        ))}
        {[0, 30, 60, 90].map((v) => (
          <text
            key={v}
            x={x(v)}
            y="161"
            fill="#7f8d90"
            fontSize="10"
            textAnchor="middle"
          >
            {v}′
          </text>
        ))}
        <line
          x1={x(result.divergence.t / 60)}
          x2={x(result.divergence.t / 60)}
          y1="17"
          y2="141"
          stroke="#a6afb3"
          strokeDasharray="3 4"
        />
        <path d={path(a)} fill="none" stroke="#b8ee78" strokeWidth="2.5" />
        <path d={path(b)} fill="none" stroke="#a99dff" strokeWidth="2.5" />
        <text
          x={Math.max(45, x(result.divergence.t / 60) + 6)}
          y="12"
          fontSize="9"
          fill="#adb8b9"
        >
          DECISION {result.divergence.min}′
        </text>
      </svg>
      <p className="muted small">
        {result.placeholder
          ? "Illustrative fixture values; not measured simulator output. "
          : ""}
        Lines join supplied samples. A typical replay is one possible path.
      </p>
    </section>
  );
}
