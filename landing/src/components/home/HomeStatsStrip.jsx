export default function HomeStatsStrip({
  stats,
  onStatClick,
  styles,
  soft,
  colors,
  IconRenderer,
}) {
  const S = styles;
  return (
    <section style={S.statsStrip}>
      <div style={S.statsIntro}>
        <span>Activite du jour</span>
        <b>Supervision rapide</b>
      </div>
      <div style={S.statsGrid}>
        {stats.map(([value, label, note, tone, icon]) => (
          <button key={label} type="button" onClick={() => onStatClick(label)} style={S.statBox}>
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
