export default function DarkSummaryCard({
  handledTodayCount,
  urgentCount,
  avgResponseMinutes,
  teamNotes = [],
  teamNoteDraft = "",
  onTeamNoteChange,
  onTeamNoteSave,
  teamNoteSaving = false,
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
        {" "}Les prises de RDV, annulations et créneaux récupérés sont résumés dans les cartes du haut.
      </p>
      <div style={S.darkDivider} />
      <h4 style={S.darkNotesTitle}>✎ Notes de l&apos;équipe</h4>
      {teamNotes.length === 0 ? (
        <p style={S.darkNotesEmpty}>Aucune note cabinet pour le moment.</p>
      ) : (
        <div style={S.darkNotesList}>
          {teamNotes.slice(0, 4).map((item) => {
            const dt = new Date(String(item?.createdAt || ""));
            const hasDate = !Number.isNaN(dt.getTime());
            return (
              <div key={item.id} style={S.darkNoteItem}>
                <p style={S.darkNoteText}>{item.text}</p>
                <p style={S.darkNoteMeta}>
                  {item.author}
                  {hasDate ? ` · ${dt.toLocaleDateString("fr-FR")} ${dt.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}` : ""}
                </p>
              </div>
            );
          })}
        </div>
      )}
      <textarea
        value={teamNoteDraft}
        onChange={(event) => {
          if (typeof onTeamNoteChange === "function") onTeamNoteChange(event.target.value);
        }}
        placeholder="Ajouter une note pour l'equipe..."
        style={S.darkNoteInput}
      />
      <button
        type="button"
        onClick={() => {
          if (!teamNoteSaving && typeof onTeamNoteSave === "function") onTeamNoteSave();
        }}
        disabled={teamNoteSaving}
        style={{ ...S.darkNoteBtn, opacity: teamNoteSaving ? 0.65 : 1, cursor: teamNoteSaving ? "default" : "pointer" }}
      >
        {teamNoteSaving ? "Enregistrement..." : "Enregistrer"}
      </button>
      <small style={S.darkFooter}>Mis a jour · {loading ? "Synchronisation..." : `Aujourd'hui a ${new Date().toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}`}</small>
    </section>
  );
}
