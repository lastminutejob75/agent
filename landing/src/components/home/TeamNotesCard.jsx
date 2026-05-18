export default function TeamNotesCard({
  onSave,
  IconRenderer,
  BtnComponent,
  styles,
  colors,
}) {
  const S = styles;
  const C = colors;
  const Btn = BtnComponent;
  return (
    <section style={S.card}>
      <h3 style={S.cardTitle}>{IconRenderer("edit", 17)}Notes de l'equipe</h3>
      <p style={{ margin: "0 0 10px", color: C.muted }}>Partagez une information avec le cabinet.</p>
      <input style={S.input} placeholder="Ajouter une note pour l'equipe..." />
      <Btn variant="teal" onClick={onSave}>Enregistrer</Btn>
    </section>
  );
}
