export default function TeamNotesCard({
  noteText = "",
  onNoteChange,
  onSave,
  savedNoteText = "",
  savedUpdatedAt = "",
  saving = false,
  IconRenderer,
  BtnComponent,
  styles,
  colors,
}) {
  const S = styles;
  const C = colors;
  const Btn = BtnComponent;
  const handleSave = () => {
    if (saving || typeof onSave !== "function") return;
    onSave();
  };
  const savedAtDate = savedUpdatedAt ? new Date(savedUpdatedAt) : null;
  const hasSavedAt = Boolean(savedAtDate && !Number.isNaN(savedAtDate.getTime()));
  const savedAtLabel = hasSavedAt
    ? `Enregistree le ${savedAtDate.toLocaleDateString("fr-FR")} a ${savedAtDate.toLocaleTimeString("fr-FR", {
      hour: "2-digit",
      minute: "2-digit",
    })}`
    : "";
  const savedNote = String(savedNoteText || "").trim();
  const hasSavedNote = savedNote.length > 0;

  return (
    <section style={S.card}>
      <h3 style={S.cardTitle}>{IconRenderer("edit", 17)}Notes de l'equipe</h3>
      <p style={{ margin: "0 0 10px", color: C.muted }}>Partagez une information avec le cabinet.</p>
      <input
        style={S.input}
        placeholder="Ajouter une note pour l'equipe..."
        value={noteText}
        onChange={(e) => {
          if (typeof onNoteChange === "function") onNoteChange(e.target.value);
        }}
      />
      <Btn variant="teal" onClick={handleSave}>{saving ? "Enregistrement..." : "Enregistrer"}</Btn>
      <div
        style={{
          marginTop: 12,
          padding: "10px 12px",
          borderRadius: 10,
          border: "1px solid #E2E8F0",
          background: "#F8FAFC",
        }}
      >
        <p style={{ margin: "0 0 4px", fontWeight: 700, color: "#0F172A" }}>Derniere note enregistree</p>
        <p style={{ margin: 0, color: "#334155", whiteSpace: "pre-wrap" }}>
          {hasSavedNote ? savedNote : "Aucune note enregistree pour le moment."}
        </p>
        {savedAtLabel ? (
          <p style={{ margin: "6px 0 0", color: C.muted, fontSize: 12 }}>
            {savedAtLabel}
          </p>
        ) : null}
      </div>
    </section>
  );
}
