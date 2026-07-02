// Tiny dependency-free line chart for a short numeric series (oldest → newest).
export function Sparkline({ values, label }: { values: number[]; label: string }) {
  const w = 168;
  const h = 32;
  const pad = 3;
  if (values.length < 2) return null;

  const max = Math.max(...values);
  const min = Math.min(...values);
  const range = max - min || 1;
  const step = (w - pad * 2) / (values.length - 1);
  const y = (v: number) => pad + (h - pad * 2) * (1 - (v - min) / range);

  const points = values.map((v, i) => `${(pad + i * step).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const lastX = pad + (values.length - 1) * step;

  return (
    <svg
      width={w}
      height={h}
      viewBox={`0 0 ${w} ${h}`}
      role="img"
      aria-label={label}
      className="overflow-visible"
    >
      <polyline
        points={points}
        fill="none"
        stroke="var(--color-accent)"
        strokeWidth="1.5"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      <circle cx={lastX} cy={y(values[values.length - 1]!)} r="2.5" fill="var(--color-accent)" />
    </svg>
  );
}
