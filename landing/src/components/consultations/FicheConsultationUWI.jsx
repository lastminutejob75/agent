import { useMemo, useState } from "react";
import {
  Stethoscope, Activity, FlaskConical, Sparkles,
  Save, Plus, X, User, Calendar, Heart, Thermometer, Wind, Loader2,
  Scale, AlertTriangle, FileText, ChevronDown, ChevronUp, Search,
  Check, Lock,
} from "lucide-react";

/**
 * Fiche de consultation UWI — design affiné
 * --------------------------------------------------------------
 * - Dossier patient persistant en lecture seule (édité depuis la fiche patient)
 * - Mode rapide (défaut) / complet
 * - Constantes numériques structurées -> métriques SQL
 * - Synthèse IA générée backend via onGenerateSummary(draft), validée praticien
 *
 * Props :
 *  - patient                  : GET /api/tenant/patients/:id
 *  - onSave(payload)          : POST /api/tenant/patients/:id/consultations
 *  - onGenerateSummary(draft) : POST /api/tenant/consultations/summary -> {resume, contexte}
 *  - initialDraft             : { date?: string, motif?: string, appointment_id?: string }
 */

// ---- Tokens design system UWI (pas de fontFamily inline) ----
const C = {
  teal: "#009CA4",
  tealDark: "#007A80",
  tealSoft: "#E9F7F7",
  tealGhost: "#F4FBFB",
  navy: "#0A1628",
  navy2: "#102240",
  ink: "#1F2A37",
  muted: "#69727E",
  faint: "#98A1AC",
  line: "#E8ECEF",
  bg: "#F5F7F8",
  card: "#FFFFFF",
  amber: "#B45309",
  amberSoft: "#FEF4E4",
  amberLine: "#F3C98B",
  red: "#B42318",
  redSoft: "#FEF3F2",
  headerGrad: "linear-gradient(135deg, #0A1628 0%, #102240 55%, #0E3A44 100%)",
  shadow: "0 1px 2px rgba(10,22,40,0.04), 0 4px 16px rgba(10,22,40,0.05)",
  shadowHeader: "0 8px 28px rgba(10,22,40,0.22)",
  focusRing: "0 0 0 3px rgba(0,156,164,0.14)",
};

const PATIENT_MOCK = {
  id: "pat_001",
  nom: "M. X",
  age: 32,
  sexe: "H",
  antecedents_medicaux: "Aucun antécédent médical majeur connu",
  antecedents_chirurgicaux: "—",
  allergies: "Aucune allergie connue",
  traitements: "Aucun traitement en cours",
};

const EXAMENS_PRESETS = [
  "NFS", "Hémoglobine", "Ferritine sérique", "Fer sérique",
  "CRP", "Réticulocytes", "Frottis sanguin", "Ionogramme",
  "Créatinine", "Glycémie à jeun", "TSH", "Bilan hépatique",
  "ECG", "Radiographie thoracique",
];

const EMPTY = {
  motif: "",
  anamnese: "",
  etatGeneral: "",
  examenPhysique: "",
  fc: "", pas: "", pad: "", temp: "", spo2: "", fr: "", poids: "", taille: "",
  impression: "",
  cim10: "",
  examens: [],
  prescription: "",
  orientation: "",
  suiviRdv: "",
  suiviConsignes: "",
  notePraticien: "",
  resumeIa: "",
  contexteIa: "",
};

export default function FicheConsultationUWI({
  patient = PATIENT_MOCK,
  onSave,
  onGenerateSummary,
  initialDraft = {},
}) {
  const today = new Date().toISOString().slice(0, 10);

  const [mode, setMode] = useState("rapide");
  const [date, setDate] = useState(initialDraft?.date || today);
  const [c, setC] = useState({
    ...EMPTY,
    motif: String(initialDraft?.motif || ""),
  });
  const set = (k) => (v) => setC((s) => ({ ...s, [k]: v }));

  const [examenInput, setExamenInput] = useState("");
  const [showDossier, setShowDossier] = useState(true);
  const [saved, setSaved] = useState(null);
  const [showJson, setShowJson] = useState(false);
  const [iaLoading, setIaLoading] = useState(false);
  const [iaError, setIaError] = useState(null);

  const imc = useMemo(() => {
    const p = num(c.poids);
    const t = num(c.taille) ? Number(c.taille) / 100 : null;
    if (!p || !t) return null;
    return (p / (t * t)).toFixed(1);
  }, [c.poids, c.taille]);

  const canSave = c.motif.trim().length > 0 && c.impression.trim().length > 0;

  const completion = useMemo(() => {
    const required =
      mode === "rapide"
        ? [c.motif, c.impression, c.suiviConsignes]
        : [c.motif, c.anamnese, c.etatGeneral, c.impression, c.suiviConsignes];
    const filled = required.filter((x) => x.trim().length > 0).length;
    return Math.round((filled / required.length) * 100);
  }, [c, mode]);

  const addExamen = (label) => {
    const v = (label ?? examenInput).trim();
    if (!v || c.examens.includes(v)) return;
    setC((s) => ({ ...s, examens: [...s.examens, v] }));
    setExamenInput("");
  };
  const removeExamen = (v) =>
    setC((s) => ({ ...s, examens: s.examens.filter((x) => x !== v) }));

  const buildDraft = () => ({
    patient_id: patient.id,
    appointment_id: initialDraft?.appointment_id || null,
    date,
    mode_consultation: mode,
    motif: c.motif,
    anamnese: c.anamnese,
    examen_clinique: {
      etat_general: c.etatGeneral,
      examen_physique: c.examenPhysique,
      constantes: {
        fc_bpm: num(c.fc),
        pa_systolique: num(c.pas),
        pa_diastolique: num(c.pad),
        temperature_c: num(c.temp),
        spo2_pct: num(c.spo2),
        fr_min: num(c.fr),
        poids_kg: num(c.poids),
        taille_cm: num(c.taille),
        imc: imc ? Number(imc) : null,
      },
    },
    impression_clinique: c.impression,
    cim10: c.cim10 || null,
    conduite_a_tenir: {
      examens_complementaires: c.examens,
      prescription: c.prescription,
      orientation: c.orientation,
      suivi: { prochain_rdv: c.suiviRdv || null, consignes: c.suiviConsignes },
    },
  });

  const handleGenerateSummary = async () => {
    if (!onGenerateSummary) {
      setIaError("Génération non branchée (prop onGenerateSummary absente).");
      return;
    }
    setIaLoading(true);
    setIaError(null);
    try {
      const res = await onGenerateSummary(buildDraft());
      setC((s) => ({
        ...s,
        resumeIa: res?.resume ?? s.resumeIa,
        contexteIa: res?.contexte ?? s.contexteIa,
      }));
    } catch {
      setIaError("Échec de la génération. Réessaie ou complète manuellement.");
    } finally {
      setIaLoading(false);
    }
  };

  const handleSave = () => {
    if (!canSave) return;
    const payload = {
      ...buildDraft(),
      ia_uwi:
        c.resumeIa || c.contexteIa
          ? {
              resume_consultation: c.resumeIa,
              contexte_patient: c.contexteIa,
              validated_by_practitioner: true,
            }
          : null,
      note_praticien: c.notePraticien || null,
    };
    setSaved(payload);
    setShowJson(true);
    onSave?.(payload);
  };

  const isComplete = mode === "complete";

  return (
    <div className="min-h-screen w-full px-4 py-6" style={{ background: C.bg, color: C.ink }}>
      <div className="mx-auto max-w-3xl">

        {/* ================= En-tête ================= */}
        <header
          className="sticky top-3 z-20 mb-6 overflow-hidden rounded-3xl"
          style={{ background: C.headerGrad, boxShadow: C.shadowHeader }}
        >
          {/* halo teal décoratif */}
          <div
            className="pointer-events-none absolute -right-14 -top-20 h-52 w-52 rounded-full"
            style={{ background: "radial-gradient(circle, rgba(0,156,164,0.35) 0%, transparent 70%)" }}
          />
          <div className="relative flex flex-wrap items-center justify-between gap-4 px-6 py-5">
            <div className="flex min-w-0 items-center gap-3.5">
              <div
                className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl"
                style={{ background: "rgba(0,156,164,0.18)", border: "1px solid rgba(0,156,164,0.45)" }}
              >
                <Stethoscope size={21} color="#4FD1D9" />
              </div>
              <div className="min-w-0">
                <p className="text-[10px] font-bold uppercase tracking-[0.22em]" style={{ color: "#5FAEB3" }}>
                  Consultation
                </p>
                <h1 className="mt-0.5 truncate text-xl font-extrabold tracking-tight text-white">
                  {patient.nom}
                  <span className="ml-2 text-sm font-medium" style={{ color: "#8FA3B8" }}>
                    {patient.age} ans{patient.sexe ? ` · ${patient.sexe}` : ""}
                  </span>
                </h1>
              </div>
            </div>

            <div className="flex items-center gap-2.5">
              <label
                className="hidden items-center gap-2 rounded-xl px-3 py-2 sm:flex"
                style={{ background: "rgba(255,255,255,0.07)", border: "1px solid rgba(255,255,255,0.10)" }}
              >
                <Calendar size={14} color="#5FAEB3" />
                <input
                  type="date"
                  value={date}
                  onChange={(e) => setDate(e.target.value)}
                  className="bg-transparent text-sm font-medium text-white outline-none [color-scheme:dark]"
                />
              </label>
              <button
                onClick={handleSave}
                disabled={!canSave}
                className="flex items-center gap-2 rounded-xl px-5 py-2.5 text-sm font-bold text-white transition hover:brightness-110 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-40"
                style={{ background: C.teal, boxShadow: "0 2px 10px rgba(0,156,164,0.35)" }}
              >
                <Save size={15} /> Enregistrer
              </button>
            </div>
          </div>

          {/* barre de progression intégrée au header */}
          <div className="relative h-1 w-full" style={{ background: "rgba(255,255,255,0.08)" }}>
            <div
              className="h-full transition-all duration-500"
              style={{ width: `${completion}%`, background: "linear-gradient(90deg, #009CA4, #4FD1D9)" }}
            />
          </div>
        </header>

        {/* ================= Mode + statut ================= */}
        <section className="mb-5 flex flex-wrap items-center justify-between gap-3 px-1">
          <div
            className="flex rounded-full p-1"
            style={{ background: "#EBEFF1", border: `1px solid ${C.line}` }}
          >
            <ModeBtn active={mode === "rapide"} onClick={() => setMode("rapide")}>Rapide</ModeBtn>
            <ModeBtn active={isComplete} onClick={() => setMode("complete")}>Complet</ModeBtn>
          </div>

          {canSave ? (
            <span className="flex items-center gap-1.5 text-xs font-semibold" style={{ color: C.tealDark }}>
              <Check size={14} /> Prêt à enregistrer · {completion}%
            </span>
          ) : (
            <span className="text-xs font-medium" style={{ color: C.faint }}>
              Motif et impression clinique requis · {completion}%
            </span>
          )}
        </section>

        {/* ================= Dossier patient ================= */}
        <Card
          icon={<User size={15} />}
          title="Dossier patient"
          subtitle="Persistant — édité depuis la fiche patient"
          tinted
          right={
            <button
              onClick={() => setShowDossier((s) => !s)}
              className="rounded-full px-3 py-1 text-[11px] font-bold uppercase tracking-wide transition hover:opacity-80"
              style={{ color: C.tealDark }}
            >
              {showDossier ? "Masquer" : "Afficher"}
            </button>
          }
        >
          {showDossier && (
            <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
              <ReadField label="Antécédents médicaux" value={patient.antecedents_medicaux || "—"} />
              <ReadField label="Antécédents chirurgicaux" value={patient.antecedents_chirurgicaux || "—"} />
              <ReadField label="Allergies" value={patient.allergies || "—"} />
              <ReadField label="Traitements en cours" value={patient.traitements || "—"} />
            </div>
          )}
        </Card>

        {/* ================= Motif & anamnèse ================= */}
        <Card icon={<FileText size={15} />} title="Motif & anamnèse">
          <Label required>Motif de consultation</Label>
          <TextArea rows={2} value={c.motif} onChange={set("motif")}
            placeholder="Ex. Fatigue importante évoluant depuis plusieurs semaines." />
          <div className="mt-4">
            <Label>Anamnèse / histoire de la maladie</Label>
            <TextArea rows={isComplete ? 5 : 3} value={c.anamnese} onChange={set("anamnese")}
              placeholder="Symptômes, chronologie, facteurs associés, retentissement…" />
          </div>
        </Card>

        {/* ================= Examen clinique ================= */}
        <Card icon={<Activity size={15} />} title="Examen clinique">
          <Label>État général</Label>
          <TextArea rows={2} value={c.etatGeneral} onChange={set("etatGeneral")}
            placeholder="Ex. Altéré, asthénie marquée. Conjonctives pâles…" />

          <div className="mt-5 mb-2.5 flex items-baseline justify-between">
            <Label noMargin>Constantes</Label>
            <span className="text-[10px] font-medium" style={{ color: C.faint }}>
              hors norme = surligné
            </span>
          </div>
          <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-4">
            <Vital icon={<Heart size={13} />} label="FC" unit="bpm" value={c.fc} onChange={set("fc")}
              hint="60–100" flag={num(c.fc) != null && (Number(c.fc) > 100 || Number(c.fc) < 60)} />
            <PA pas={c.pas} pad={c.pad} setPas={set("pas")} setPad={set("pad")} />
            <Vital icon={<Thermometer size={13} />} label="Temp" unit="°C" step="0.1" value={c.temp} onChange={set("temp")}
              hint="36–37.5" flag={num(c.temp) != null && (Number(c.temp) >= 38 || Number(c.temp) < 35)} />
            <Vital icon={<Wind size={13} />} label="SpO₂" unit="%" value={c.spo2} onChange={set("spo2")}
              hint="≥ 95" flag={num(c.spo2) != null && Number(c.spo2) < 94} />
            {isComplete && (
              <>
                <Vital icon={<Wind size={13} />} label="FR" unit="/min" value={c.fr} onChange={set("fr")} hint="12–20" />
                <Vital icon={<Scale size={13} />} label="Poids" unit="kg" step="0.1" value={c.poids} onChange={set("poids")} />
                <Vital icon={<Scale size={13} />} label="Taille" unit="cm" value={c.taille} onChange={set("taille")} />
                <div
                  className="rounded-2xl px-3.5 py-3"
                  style={{ background: C.tealSoft, border: "1px solid #C9E9EA" }}
                >
                  <p className="text-[10px] font-bold uppercase tracking-[0.14em]" style={{ color: C.tealDark }}>
                    IMC auto
                  </p>
                  <p className="mt-1.5 text-2xl font-extrabold tabular-nums" style={{ color: C.navy }}>
                    {imc ?? "—"}
                  </p>
                </div>
              </>
            )}
          </div>

          {isComplete && (
            <div className="mt-5">
              <Label>Examen physique</Label>
              <TextArea rows={3} value={c.examenPhysique} onChange={set("examenPhysique")}
                placeholder="Par appareil : cardio-pulmonaire, abdominal, neuro…" />
            </div>
          )}
        </Card>

        {/* ================= Impression clinique ================= */}
        <Card icon={<Search size={15} />} title="Impression clinique">
          <Label required>Hypothèse / conclusion</Label>
          <TextArea rows={2} value={c.impression} onChange={set("impression")}
            placeholder="Ex. Syndrome anémique à explorer." />
          {isComplete && (
            <div className="mt-4 max-w-[200px]">
              <Label>Code CIM-10</Label>
              <Input value={c.cim10} onChange={set("cim10")} placeholder="D64.9" />
            </div>
          )}
        </Card>

        {/* ================= Conduite à tenir ================= */}
        <Card icon={<FlaskConical size={15} />} title="Examens & conduite à tenir">
          <Label>Examens complémentaires demandés</Label>

          {c.examens.length > 0 && (
            <div className="mb-3 flex flex-wrap gap-1.5">
              {c.examens.map((e) => (
                <span
                  key={e}
                  className="group flex items-center gap-1.5 rounded-full py-1 pl-3 pr-1.5 text-[13px] font-semibold text-white"
                  style={{ background: C.teal }}
                >
                  {e}
                  <button
                    onClick={() => removeExamen(e)}
                    className="flex h-4.5 w-4.5 items-center justify-center rounded-full transition"
                    style={{ background: "rgba(255,255,255,0.18)" }}
                  >
                    <X size={11} />
                  </button>
                </span>
              ))}
            </div>
          )}

          <div className="flex gap-2">
            <input
              value={examenInput}
              onChange={(e) => setExamenInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addExamen())}
              placeholder="Ajouter un examen…"
              className="min-w-0 flex-1 rounded-xl border px-3.5 py-2.5 text-sm outline-none transition"
              style={{ borderColor: C.line }}
              onFocus={(e) => { e.currentTarget.style.borderColor = C.teal; e.currentTarget.style.boxShadow = C.focusRing; }}
              onBlur={(e) => { e.currentTarget.style.borderColor = C.line; e.currentTarget.style.boxShadow = "none"; }}
            />
            <button
              onClick={() => addExamen()}
              className="flex items-center gap-1 rounded-xl px-3.5 py-2.5 text-sm font-bold text-white transition hover:brightness-110 active:scale-[0.98]"
              style={{ background: C.navy }}
            >
              <Plus size={15} />
            </button>
          </div>

          <div className="mt-3 flex flex-wrap gap-1.5">
            {EXAMENS_PRESETS.filter((p) => !c.examens.includes(p)).map((p) => (
              <button
                key={p}
                onClick={() => addExamen(p)}
                className="rounded-full px-3 py-1 text-xs font-semibold transition hover:-translate-y-px"
                style={{ background: C.tealGhost, color: C.tealDark, border: "1px solid #D6EEEF" }}
              >
                {p}
              </button>
            ))}
          </div>

          <Divider />

          <div className="space-y-4">
            <div>
              <Label>Prescription / traitement</Label>
              <TextArea rows={2} value={c.prescription} onChange={set("prescription")}
                placeholder="Médicaments, posologie, durée…" />
            </div>
            {isComplete && (
              <div>
                <Label>Orientation</Label>
                <Input value={c.orientation} onChange={set("orientation")}
                  placeholder="Ex. Avis hématologie si anémie confirmée" />
              </div>
            )}
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div>
                <Label>Prochain RDV</Label>
                <Input type="date" value={c.suiviRdv} onChange={set("suiviRdv")} />
              </div>
              <div>
                <Label>Consignes de suivi</Label>
                <Input value={c.suiviConsignes} onChange={set("suiviConsignes")}
                  placeholder="Ex. Reconsulter si aggravation" />
              </div>
            </div>
          </div>
        </Card>

        {/* ================= Synthèse UWI ================= */}
        <section
          className="mb-4 overflow-hidden rounded-3xl"
          style={{ background: C.card, border: "1px solid #CDEBEC", boxShadow: C.shadow }}
        >
          {/* bandeau */}
          <div
            className="flex flex-wrap items-center justify-between gap-3 px-6 py-4"
            style={{ background: "linear-gradient(135deg, #E9F7F7 0%, #F4FBFB 100%)", borderBottom: "1px solid #DFF1F2" }}
          >
            <div className="flex items-center gap-2.5">
              <span
                className="flex h-8 w-8 items-center justify-center rounded-xl"
                style={{ background: C.teal }}
              >
                <Sparkles size={15} color="#fff" />
              </span>
              <div>
                <h2 className="text-sm font-extrabold" style={{ color: C.navy }}>Synthèse UWI</h2>
                <p className="text-[11px]" style={{ color: C.muted }}>
                  Générée à partir de la fiche · relue et validée par vous
                </p>
              </div>
            </div>
            <button
              onClick={handleGenerateSummary}
              disabled={iaLoading || !c.motif.trim()}
              className="flex items-center gap-1.5 rounded-xl px-3.5 py-2 text-xs font-bold text-white transition hover:brightness-110 active:scale-[0.98] disabled:opacity-40"
              style={{ background: C.teal }}
            >
              {iaLoading ? <Loader2 size={13} className="animate-spin" /> : <Sparkles size={13} />}
              {c.resumeIa ? "Régénérer" : "Générer"}
            </button>
          </div>

          <div className="px-6 py-5">
            {iaError && (
              <p className="mb-3 rounded-xl px-3 py-2 text-xs font-semibold" style={{ background: C.redSoft, color: C.red }}>
                {iaError}
              </p>
            )}
            <Label>Résumé de la consultation</Label>
            <TextArea rows={4} value={c.resumeIa} onChange={set("resumeIa")}
              placeholder="Généré automatiquement à l'enregistrement — ou cliquez sur Générer pour relire avant." />
            <div className="mt-4">
              <Label>Contexte patient à mettre à jour</Label>
              <TextArea rows={2} value={c.contexteIa} onChange={set("contexteIa")}
                placeholder="Éléments à retenir pour les prochains appels et RDV." />
            </div>
            <div className="mt-4">
              <Label icon={<Lock size={10} />}>Note interne praticien</Label>
              <TextArea rows={2} value={c.notePraticien} onChange={set("notePraticien")}
                placeholder="Privée — exclue du contexte Clara et des communications patient." />
            </div>
          </div>
        </section>

        {/* ================= Aperçu API ================= */}
        {saved && (
          <div className="mt-5 overflow-hidden rounded-2xl" style={{ background: C.card, border: `1px solid ${C.line}` }}>
            <button
              onClick={() => setShowJson((s) => !s)}
              className="flex w-full items-center justify-between px-5 py-3.5 text-sm font-bold"
              style={{ color: C.navy }}
            >
              Données enregistrées · aperçu API
              {showJson ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            </button>
            {showJson && (
              <pre
                className="overflow-x-auto px-5 py-4 text-xs leading-relaxed"
                style={{ borderTop: `1px solid ${C.line}`, color: C.muted, background: "#FBFCFC" }}
              >
                {JSON.stringify(saved, null, 2)}
              </pre>
            )}
          </div>
        )}

        <p className="mt-6 pb-4 text-center text-[11px]" style={{ color: C.faint }}>
          UWI · les données de consultation restent dans le dossier du cabinet
        </p>
      </div>
    </div>
  );
}

/* ----------------------------- sous-composants ----------------------------- */

function num(v) {
  if (v === "" || v == null) return null;
  const n = Number(v);
  return Number.isNaN(n) ? null : n;
}

function ModeBtn({ active, onClick, children }) {
  return (
    <button
      onClick={onClick}
      className="rounded-full px-4 py-1.5 text-[13px] font-bold transition"
      style={{
        background: active ? "#FFFFFF" : "transparent",
        color: active ? C.navy : C.faint,
        boxShadow: active ? "0 1px 4px rgba(10,22,40,0.10)" : "none",
      }}
    >
      {children}
    </button>
  );
}

function Card({ icon, title, subtitle, right, tinted, children }) {
  return (
    <section
      className="mb-4 rounded-3xl px-6 py-5"
      style={{
        background: tinted ? "#FBFDFD" : C.card,
        border: `1px solid ${C.line}`,
        boxShadow: C.shadow,
      }}
    >
      <div className="mb-4 flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <span
            className="flex h-8 w-8 items-center justify-center rounded-xl"
            style={{ background: C.tealSoft, color: C.tealDark }}
          >
            {icon}
          </span>
          <div>
            <h2 className="text-sm font-extrabold tracking-tight" style={{ color: C.navy }}>{title}</h2>
            {subtitle && <p className="text-[11px]" style={{ color: C.muted }}>{subtitle}</p>}
          </div>
        </div>
        {right}
      </div>
      {children}
    </section>
  );
}

function Label({ children, required, noMargin, icon }) {
  return (
    <p
      className={`flex items-center gap-1 text-[10.5px] font-bold uppercase tracking-[0.14em] ${noMargin ? "" : "mb-1.5"}`}
      style={{ color: C.muted }}
    >
      {icon}
      {children}
      {required && <span style={{ color: C.teal }}>*</span>}
    </p>
  );
}

function Divider() {
  return <div className="my-5 h-px w-full" style={{ background: C.line }} />;
}

function TextArea({ value, onChange, ...rest }) {
  return (
    <textarea
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="w-full resize-y rounded-xl border px-3.5 py-2.5 text-sm leading-relaxed outline-none transition placeholder:text-slate-300"
      style={{ borderColor: C.line, background: "#FDFDFE" }}
      onFocus={(e) => { e.currentTarget.style.borderColor = C.teal; e.currentTarget.style.boxShadow = C.focusRing; e.currentTarget.style.background = "#FFFFFF"; }}
      onBlur={(e) => { e.currentTarget.style.borderColor = C.line; e.currentTarget.style.boxShadow = "none"; e.currentTarget.style.background = "#FDFDFE"; }}
      {...rest}
    />
  );
}

function Input({ value, onChange, type = "text", ...rest }) {
  return (
    <input
      type={type}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="w-full rounded-xl border px-3.5 py-2.5 text-sm outline-none transition placeholder:text-slate-300"
      style={{ borderColor: C.line, background: "#FDFDFE" }}
      onFocus={(e) => { e.currentTarget.style.borderColor = C.teal; e.currentTarget.style.boxShadow = C.focusRing; e.currentTarget.style.background = "#FFFFFF"; }}
      onBlur={(e) => { e.currentTarget.style.borderColor = C.line; e.currentTarget.style.boxShadow = "none"; e.currentTarget.style.background = "#FDFDFE"; }}
      {...rest}
    />
  );
}

function ReadField({ label, value }) {
  return (
    <div
      className="rounded-xl px-3.5 py-2.5"
      style={{ background: "#FFFFFF", border: `1px solid ${C.line}` }}
    >
      <p className="text-[10px] font-bold uppercase tracking-[0.14em]" style={{ color: C.faint }}>{label}</p>
      <p className="mt-1 text-[13px] font-medium leading-snug" style={{ color: C.ink }}>{value}</p>
    </div>
  );
}

function Vital({ icon, label, unit, value, onChange, hint, step, flag }) {
  return (
    <div
      className="rounded-2xl px-3.5 py-3 transition"
      style={{
        border: `1px solid ${flag ? C.amberLine : C.line}`,
        background: flag ? C.amberSoft : C.card,
      }}
    >
      <div className="flex items-center justify-between">
        <span
          className="flex items-center gap-1 text-[10px] font-bold uppercase tracking-[0.14em]"
          style={{ color: flag ? C.amber : C.faint }}
        >
          {icon} {label}
        </span>
        {flag && <AlertTriangle size={12} color={C.amber} />}
      </div>
      <div className="mt-1.5 flex items-baseline gap-1">
        <input
          type="number"
          step={step}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="—"
          className="w-full min-w-0 bg-transparent text-[22px] font-extrabold tabular-nums outline-none placeholder:text-slate-300"
          style={{ color: C.navy }}
        />
        <span className="text-[11px] font-semibold" style={{ color: C.faint }}>{unit}</span>
      </div>
      {hint && (
        <p className="mt-0.5 text-[10px] tabular-nums" style={{ color: flag ? C.amber : C.faint }}>
          norme {hint}
        </p>
      )}
    </div>
  );
}

function PA({ pas, pad, setPas, setPad }) {
  return (
    <div className="rounded-2xl px-3.5 py-3" style={{ border: `1px solid ${C.line}`, background: C.card }}>
      <span className="flex items-center gap-1 text-[10px] font-bold uppercase tracking-[0.14em]" style={{ color: C.faint }}>
        <Activity size={13} /> PA
      </span>
      <div className="mt-1.5 flex items-baseline gap-0.5">
        <input type="number" value={pas} onChange={(e) => setPas(e.target.value)} placeholder="—"
          className="w-11 min-w-0 bg-transparent text-[22px] font-extrabold tabular-nums outline-none placeholder:text-slate-300"
          style={{ color: C.navy }} />
        <span className="text-lg font-bold" style={{ color: C.faint }}>/</span>
        <input type="number" value={pad} onChange={(e) => setPad(e.target.value)} placeholder="—"
          className="w-11 min-w-0 bg-transparent text-[22px] font-extrabold tabular-nums outline-none placeholder:text-slate-300"
          style={{ color: C.navy }} />
        <span className="text-[11px] font-semibold" style={{ color: C.faint }}>mmHg</span>
      </div>
      <p className="mt-0.5 text-[10px]" style={{ color: C.faint }}>syst / diast</p>
    </div>
  );
}
