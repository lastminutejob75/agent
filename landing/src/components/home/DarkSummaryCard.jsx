import { useEffect, useState } from "react";

const NOTE_PREVIEW_LIMIT = 180;

function shortNote(text) {
  const raw = String(text || "");
  if (raw.length <= NOTE_PREVIEW_LIMIT) return raw;
  return `${raw.slice(0, NOTE_PREVIEW_LIMIT).trimEnd()}...`;
}

export default function DarkSummaryCard({
  handledTodayCount,
  urgentCount,
  avgResponseMinutes,
  teamNotes = [],
  teamNoteDraft = "",
  onTeamNoteChange,
  onTeamNoteSave,
  onTeamNoteEdit,
  onTeamNoteDelete,
  teamNoteSaving = false,
  teamNoteActionLoadingId = "",
  loading,
  IconRenderer,
  styles,
}) {
  const S = styles;
  const [expandedIds, setExpandedIds] = useState({});
  const [editingId, setEditingId] = useState("");
  const [editingDraft, setEditingDraft] = useState("");

  useEffect(() => {
    if (!editingId) return;
    if (!teamNotes.some((item) => String(item?.id || "") === editingId)) {
      setEditingId("");
      setEditingDraft("");
    }
  }, [editingId, teamNotes]);

  const delayLabel = Number.isFinite(avgResponseMinutes)
    ? `${avgResponseMinutes} min`
    : "—";

  const toggleExpanded = (noteId) => {
    setExpandedIds((prev) => ({ ...prev, [noteId]: !prev[noteId] }));
  };

  const startEdit = (item) => {
    setEditingId(String(item?.id || ""));
    setEditingDraft(String(item?.text || ""));
  };

  const cancelEdit = () => {
    setEditingId("");
    setEditingDraft("");
  };

  const saveEdit = async () => {
    if (!editingId || typeof onTeamNoteEdit !== "function") return;
    const ok = await onTeamNoteEdit(editingId, editingDraft);
    if (ok) cancelEdit();
  };

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
            const noteId = String(item?.id || "");
            const isBusy = String(teamNoteActionLoadingId || "") === noteId;
            const isExpanded = Boolean(expandedIds[noteId]);
            const isEditing = editingId === noteId;
            const text = String(item?.text || "");
            const hasOverflow = text.length > NOTE_PREVIEW_LIMIT;
            const dt = new Date(String(item?.createdAt || ""));
            const hasDate = !Number.isNaN(dt.getTime());
            return (
              <div key={noteId || item.id} style={S.darkNoteItem}>
                {isEditing ? (
                  <div style={S.darkNoteEditor}>
                    <textarea
                      value={editingDraft}
                      onChange={(event) => setEditingDraft(event.target.value)}
                      style={S.darkNoteEditInput}
                      disabled={isBusy}
                    />
                    <div style={S.darkNoteEditorBtns}>
                      <button
                        type="button"
                        onClick={() => {
                          void saveEdit();
                        }}
                        disabled={isBusy}
                        style={{ ...S.darkNoteMiniBtn, opacity: isBusy ? 0.7 : 1 }}
                      >
                        {isBusy ? "Enregistrement..." : "Enregistrer"}
                      </button>
                      <button
                        type="button"
                        onClick={cancelEdit}
                        disabled={isBusy}
                        style={{ ...S.darkNoteMiniBtn, opacity: isBusy ? 0.7 : 1 }}
                      >
                        Annuler
                      </button>
                    </div>
                  </div>
                ) : (
                  <>
                    <p style={S.darkNoteText}>{isExpanded ? text : shortNote(text)}</p>
                    <div style={S.darkNoteActions}>
                      {hasOverflow ? (
                        <button
                          type="button"
                          onClick={() => toggleExpanded(noteId)}
                          disabled={isBusy}
                          style={{ ...S.darkNoteActionBtn, opacity: isBusy ? 0.7 : 1 }}
                        >
                          {isExpanded ? "Afficher moins" : "Lire la suite"}
                        </button>
                      ) : null}
                      <button
                        type="button"
                        onClick={() => startEdit(item)}
                        disabled={isBusy || typeof onTeamNoteEdit !== "function"}
                        style={{ ...S.darkNoteActionBtn, opacity: (isBusy || typeof onTeamNoteEdit !== "function") ? 0.7 : 1 }}
                      >
                        Modifier
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          if (typeof onTeamNoteDelete === "function") void onTeamNoteDelete(noteId);
                        }}
                        disabled={isBusy || typeof onTeamNoteDelete !== "function"}
                        style={{ ...S.darkNoteActionBtn, opacity: (isBusy || typeof onTeamNoteDelete !== "function") ? 0.7 : 1 }}
                      >
                        {isBusy ? "Suppression..." : "Supprimer"}
                      </button>
                    </div>
                  </>
                )}
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
