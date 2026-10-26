import type { ForkResult } from "../types";
import { percent } from "../model";
import { useI18n } from "../i18n";
export function ProbabilityChart({
  result,
  home,
}: {
  result: ForkResult;
  home: string;
}) {
  const { t } = useI18n();
  const a = result.original.win_prob,
    b = result.alternate.win_prob;
  const end = Math.max(
    90,
    ...a.map((p) => p.minute),
    ...b.map((p) => p.minute),
  );
  const x = (min: number) => 46 + (min / end) * 574;
  const y = (p: number) => 226 - p * 190;
  const path = (values: typeof a) =>
    values
      .map((p, i) => `${i === 0 ? "M" : "L"}${x(p.minute)},${y(p.home)}`)
      .join(" ");
  return (
    <section className="probability card">
      <div className="section-title">
        <h3>{t("chart.title", { team: home })}</h3>
        <span className="small-label">
          {result.placeholder ? t("chart.placeholder") : t("chart.estimates")}
        </span>
      </div>
      <div className="chart-legend">
        <span>
          <i className="legend-line original" />
          {t("chart.original")}
        </span>
        <span>
          <i className="legend-line alternate" />
          {t("chart.alternate")}
        </span>
        <span className="chart-key">{t("chart.key")}</span>
      </div>
      <svg
        viewBox="0 0 640 270"
        role="img"
        aria-label={t("chart.aria", {
          team: home,
          a: percent(a.at(-1)?.home ?? 0),
          b: percent(b.at(-1)?.home ?? 0),
          min: result.divergence.min,
          note: result.placeholder
            ? t("chart.ariaPlaceholder")
            : t("chart.ariaEstimates"),
        })}
      >
        {[0, 0.5, 1].map((v) => (
          <g key={v}>
            <line
              x1="46"
              x2="620"
              y1={y(v)}
              y2={y(v)}
              stroke="var(--rule-strong)"
            />
            <text x="0" y={y(v) + 5} fill="var(--muted)" fontSize="14">
              {percent(v)}
            </text>
          </g>
        ))}
        {[0, 30, 60, 90].map((v) => (
          <text
            key={v}
            x={x(v)}
            y="258"
            fill="var(--muted)"
            fontSize="14"
            textAnchor="middle"
          >
            {v}′
          </text>
        ))}
        <line
          x1={x(result.divergence.t / 60)}
          x2={x(result.divergence.t / 60)}
          y1="17"
          y2="227"
          stroke="var(--muted)"
          strokeDasharray="3 4"
        />
        <path d={path(a)} fill="none" stroke="var(--ink)" strokeWidth="2" />
        <path
          d={path(
            b.filter((p) => p.minute >= Math.floor(result.divergence.t / 60)),
          )}
          fill="none"
          stroke="var(--hue)"
          strokeWidth="2.5"
          strokeDasharray="7 3"
        />
        <text
          x={Math.max(45, x(result.divergence.t / 60) + 6)}
          y="13"
          fontSize="14"
          fill="var(--muted)"
        >
          {t("chart.decision", { min: result.divergence.min })}
        </text>
      </svg>
      <p className="muted small">
        {result.placeholder ? `${t("chart.fixtureNote")} ` : ""}
        {t("chart.note")}
      </p>
    </section>
  );
}
