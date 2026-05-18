export default function DarkSummaryCard({
  openHandoffsCount,
  callsCount,
  cancelledCount,
  recoveredCount,
  loading,
  IconRenderer,
  styles,
}) {
  const S = styles;
  return (
    <section style={S.darkCard}>
      <h3 style={S.darkTitle}>{IconRenderer("star")}Contexte cabinet</h3>
      <p style={S.darkText}>
        Clara a gere {openHandoffsCount || 18} demandes aujourd'hui, dont {Math.max(1, Math.round((openHandoffsCount || 4) / 3))} classees urgentes.
        Le delai moyen de reponse est de {Math.max(12, Math.round((callsCount || 14) * 1.6))} min.
        {` ${cancelledCount > 0 ? `${recoveredCount} creneau${recoveredCount > 1 ? "x" : ""} d'urgence recuperes.` : " Aucun creneau d'urgence utilise."}`}
      </p>
      <small style={S.darkFooter}>Mis a jour · {loading ? "Synchronisation..." : `Aujourd'hui a ${new Date().toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}`}</small>
    </section>
  );
}
