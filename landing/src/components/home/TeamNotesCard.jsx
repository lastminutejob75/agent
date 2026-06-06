export default function TeamNotesCard({
  noteText = "",
  onNoteChange,
  onSave,
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
    </section>
  );
}
