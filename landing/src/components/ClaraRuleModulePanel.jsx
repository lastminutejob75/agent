export default function ClaraRuleModulePanel({
  activeModule,
  activeRuleState,
  getRuleCompleteness,
  onToggle,
  onChangeNote,
  onClose,
  onSave,
  styles,
  colors,
  PillComponent,
  BtnComponent,
}) {
  if (!activeModule) return null;
  const S = styles || {};
  const C = colors || {};
  const Pill = PillComponent;
  const Btn = BtnComponent;
  return (
    <section style={S.moduleCard}>
      <div style={S.moduleCardHead}>
        <div>
          <h3 style={{ ...S.h3, margin: 0 }}>{activeModule.title}</h3>
          <p style={{ margin: "6px 0 0", color: C.muted, fontSize: 14 }}>{activeModule.description}</p>
        </div>
        <Pill tone={activeModule.tone}>{getRuleCompleteness(activeModule.key).label}</Pill>
      </div>
      <div className="uwi-clara-module-checks" style={S.moduleChecks}>
        <label style={S.check}>
          <input
            type="checkbox"
            checked={Boolean(activeRuleState.enabled)}
            onChange={(e) => onToggle("enabled", e.target.checked)}
          /> Activer la regle
        </label>
        <label style={S.check}>
          <input
            type="checkbox"
            checked={Boolean(activeRuleState.notifyTeam)}
            onChange={(e) => onToggle("notifyTeam", e.target.checked)}
          /> Notifier l'equipe
        </label>
        <label style={S.check}>
          <input
            type="checkbox"
            checked={Boolean(activeRuleState.notifyPatients)}
            onChange={(e) => onToggle("notifyPatients", e.target.checked)}
          /> Informer les patients
        </label>
      </div>
      <textarea
        style={S.textarea}
        value={String(activeRuleState.note || "")}
        onChange={(e) => onChangeNote(e.target.value)}
        placeholder="Ajouter une precision operationnelle..."
      />
      <div style={S.moduleActions}>
        <Btn onClick={onClose}>Fermer</Btn>
        <Btn variant="teal" onClick={onSave}>Enregistrer la configuration</Btn>
      </div>
    </section>
  );
}
