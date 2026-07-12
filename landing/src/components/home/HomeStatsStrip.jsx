import { useNavigate } from "react-router-dom";

export default function HomeStatsStrip({
  stats,
  loading = false,
  onStatClick,
  styles,
  soft,
  colors,
  IconRenderer,
}) {
  const navigate = useNavigate();
  const S = styles;
  return (
    <section className="uwi-dashboard-stats-strip" style={S.statsStrip}>
      <div className="uwi-dashboard-stats-grid" style={S.statsGrid}>
        {stats.map(([value, label, note, tone, icon, to]) => (
          <button
            key={label}
            type="button"
            disabled={loading || !to}
            onClick={() => {
              if (to) navigate(to);
              else if (typeof onStatClick === "function") onStatClick(label);
            }}
            style={{
              ...S.statBox,
              ...(loading ? { opacity: 0.72, cursor: "default" } : null),
            }}
            aria-busy={loading || undefined}
            aria-label={to && !loading ? `${label} — ouvrir` : label}
          >
            <em style={{ background: soft[tone], color: colors[tone] }}>{IconRenderer(icon, 17)}</em>
            <strong>{value}</strong>
            <span>{label}</span>
            <small>{note}</small>
          </button>
        ))}
      </div>
    </section>
  );
}
