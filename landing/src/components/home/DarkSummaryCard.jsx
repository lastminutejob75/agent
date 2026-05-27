export default function DarkSummaryCard({
  handledTodayCount,
  urgentCount,
  avgResponseMinutes,
  cancelledCount,
  recoveredCount,
  loading,
  IconRenderer,
  styles,
}) {
  const S = styles;
  const delayLabel = Number.isFinite(avgResponseMinutes)
    ? `${avgResponseMinutes} min`
    : "—";
  return (
    <section style={S.darkCard}>
      <h3 style={S.darkTitle}>{IconRenderer("star")}Contexte cabinet</h3>
      <p style={S.darkText}>
        Clara a traité {handledTodayCount} demande{handledTodayCount > 1 ? "s" : ""} aujourd&apos;hui
        {urgentCount > 0 ? `, dont ${urgentCount} classée${urgentCount > 1 ? "s" : ""} urgente${urgentCount > 1 ? "s" : ""}` : ""}.
        {" "}Le délai moyen de réponse est de {delayLabel}.
        {` ${cancelledCount > 0 ? `${recoveredCount} creneau${recoveredCount > 1 ? "x" : ""} d'urgence recuperes.` : " Aucun creneau d'urgence utilise."}`}
      </p>
      <small style={S.darkFooter}>Mis a jour · {loading ? "Synchronisation..." : `Aujourd'hui a ${new Date().toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}`}</small>
    </section>
  );
}
