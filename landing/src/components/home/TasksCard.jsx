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
      title="À faire maintenant"
      icon="warn"
      action={<button type="button" style={S.linkBtn} onClick={onOpenAll}>Voir tout ›</button>}
    >
      {taskRows.length === 0 ? (
        <p style={{ margin: 0, color: "#66758B", fontWeight: 600 }}>Aucune demande en attente.</p>
      ) : taskRows.map((task) => (
        <button key={task.id || task.title} type="button" onClick={() => onTaskClick(task)} style={S.task}>
          <i style={{ background: soft[task.tone], color: colors[task.tone] }}>{IconRenderer("doc", 17)}</i>
          <span><b>{task.title}</b><small>{task.sub}</small></span>
          <Pill tone={task.tone}>{task.badge}</Pill>
        </button>
      ))}
    </Card>
  );
}
