export default function TasksCard({
  taskRows,
  onOpenAll,
  onTaskClick,
  CardComponent,
  PillComponent,
  IconRenderer,
  styles,
  soft,
  colors,
}) {
  const S = styles;
  const Card = CardComponent;
  const Pill = PillComponent;
  return (
    <Card
      title="A traiter"
      icon="warn"
      action={<button type="button" style={S.linkBtn} onClick={onOpenAll}>Voir tout ›</button>}
    >
      {taskRows.length === 0 ? (
        <p style={{ margin: 0, color: "#66758B", fontWeight: 600 }}>Aucune demande en attente.</p>
      ) : taskRows.map(([title, sub, tone, badge]) => (
        <button key={title} type="button" onClick={() => onTaskClick(title)} style={S.task}>
          <i style={{ background: soft[tone], color: colors[tone] }}>{IconRenderer("doc", 17)}</i>
          <span><b>{title}</b><small>{sub}</small></span>
          <Pill tone={tone}>{badge}</Pill>
        </button>
      ))}
    </Card>
  );
}
