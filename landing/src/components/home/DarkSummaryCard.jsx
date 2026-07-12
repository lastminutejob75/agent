import { useEffect, useState } from "react";

const NOTE_PREVIEW_LIMIT = 180;

function shortNote(text) {
  const raw = String(text || "");
  if (raw.length <= NOTE_PREVIEW_LIMIT) return raw;
  return `${raw.slice(0, NOTE_PREVIEW_LIMIT).trimEnd()}...`;
}

function joinHumanList(parts = []) {
  const clean = parts.filter(Boolean);
  if (clean.length === 0) return "";
  if (clean.length === 1) return clean[0];
  if (clean.length === 2) return `${clean[0]} et ${clean[1]}`;
  return `${clean.slice(0, -1).join(", ")} et ${clean[clean.length - 1]}`;
}

export default function DarkSummaryCard({
  handledTodayCount,
  urgentCount,
  avgResponseMinutes,
  summaryLoading = false,
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

  const summaryText = (() => {
    if (summaryLoading) {
      return "Résumé IA du contexte cabinet en cours de génération…";
    }
    const hasSignals = teamNotes.length > 0 || handledTodayCount > 0 || urgentCount > 0 || Number.isFinite(avgResponseMinutes);
    if (!hasSignals) {
      return "Résumé IA prêt, mais aucune activité significative n'a encore été détectée aujourd'hui.";
    }
    const notesCorpus = teamNotes
      .slice(0, 6)
      .map((item) => String(item?.text || ""))
      .join(" ")
      .toLowerCase();
    const hasNoShow = /no[\s-]?show|absence|absent/.test(notesCorpus);
    const hasTelemed = /t[ée]l[ée]m[ée]decine|t[ée]l[ée]consultation|visio/.test(notesCorpus);
    const hasReminder = /rappel|relance/.test(notesCorpus);

    const contextParts = [];
    if (hasNoShow) contextParts.push("les absences et no-show restent un enjeu operationnel");
    if (hasTelemed) contextParts.push("la telemedecine est utilisee comme modalite de suivi");
    if (hasReminder) contextParts.push("les relances patients structurent une partie du suivi");
    if (teamNotes.length > 0 && contextParts.length === 0) {
      contextParts.push("les notes d'equipe indiquent un suivi clinique et administratif actif");
    }

    const contextSentence = teamNotes.length > 0
      ? `Les dernieres notes d'equipe montrent que ${joinHumanList(contextParts)}`
      : "Le contexte cabinet repose principalement sur l'activite operationnelle du jour";

    const activityParts = [];
    if (handledTodayCount > 0) {
      activityParts.push(`${handledTodayCount} demande${handledTodayCount > 1 ? "s" : ""} traitee${handledTodayCount > 1 ? "s" : ""} aujourd'hui`);
    }
    if (urgentCount > 0) {
      activityParts.push(`${urgentCount} urgente${urgentCount > 1 ? "s" : ""}`);
    }
    if (Number.isFinite(avgResponseMinutes)) {
      activityParts.push(`un delai moyen de reponse de ${delayLabel}`);
    }
    const activitySentence = activityParts.length > 0
      ? `Sur l'activite recente, on observe ${joinHumanList(activityParts)}.`
      : "L'activite recente reste moderee.";

    const priorityParts = [];
    if (hasNoShow || hasReminder) {
      priorityParts.push("renforcer les rappels J-1 et J-0 pour limiter les absences evitables");
    }
    if (hasTelemed) {
      priorityParts.push("stabiliser les criteres d'orientation vers la teleconsultation");
    }
    if (urgentCount > 0) {
      priorityParts.push("maintenir un tri prioritaire des demandes urgentes");
    }
    if (priorityParts.length === 0 && handledTodayCount > 0) {
      priorityParts.push("poursuivre la cadence actuelle de traitement");
    }
    const prioritySentence = priorityParts.length > 0
      ? `Priorites recommandees : ${joinHumanList(priorityParts)}.`
      : "";

    return `Resume IA : ${contextSentence}. ${activitySentence}${prioritySentence ? ` ${prioritySentence}` : ""}`.trim();
  })();

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
      <h3 style={S.darkTitle}>{IconRenderer("edit")}Transmission équipe</h3>
      <p style={S.darkText}>Les informations utiles à partager avec le cabinet.</p>
      <div style={S.darkDivider} />
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
      <details style={S.darkActivityDetails}>
        <summary style={S.darkActivitySummary}>Résumé d&apos;activité Clara</summary>
        <p style={S.darkActivityText}>{summaryText}</p>
      </details>
      <small style={S.darkFooter}>Mis a jour · {loading ? "Synchronisation..." : `Aujourd'hui a ${new Date().toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}`}</small>
    </section>
  );
}
