import { useState, useEffect } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { adminApi } from "../../lib/adminApi.js";

const DAYS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"];
const STATUS_OPTIONS = [
  { value: "new", label: "Nouveau" },
  { value: "contacted", label: "Contacté" },
  { value: "converted", label: "Converti" },
  { value: "lost", label: "Perdu" },
];

function formatDate(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("fr-FR");
  } catch {
    return iso;
  }
}

export default function AdminLeadDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [lead, setLead] = useState(null);
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [copied, setCopied] = useState(false);
  const [copiedLink, setCopiedLink] = useState(false);

  useEffect(() => {
    if (!id) return;
    adminApi
      .leadGet(id)
      .then(setLead)
      .catch(() => setLead(null));
  }, [id]);

  useEffect(() => {
    if (lead) setNotes(lead.notes ?? "");
  }, [lead]);

  const saveNotes = () => {
    if (!id) return;
    setSaving(true);
    adminApi
      .leadPatch(id, { notes })
      .then(() => setSaving(false))
      .catch(() => setSaving(false));
  };

  const setStatus = (status) => {
    if (!id) return;
    adminApi.leadPatch(id, { status }).then(() => {
      setLead((p) => (p ? { ...p, status } : null));
    });
  };

  const copyDirectLink = () => {
    const url = window.location.origin + window.location.pathname;
    navigator.clipboard.writeText(url);
    setCopiedLink(true);
    setTimeout(() => setCopiedLink(false), 2000);
  };

  const copySummary = () => {
    if (!lead) return;
    const lines = [
      `Email: ${lead.email}`,
      `Spécialité: ${lead.medical_specialty || "—"}`,
      `Point de douleur: ${lead.primary_pain_point || "—"}`,
      `Appels/jour: ${lead.daily_call_volume}`,
      `Assistante: ${lead.assistant_name} (voix ${lead.voice_gender === "female" ? "féminine" : "masculine"})`,
      `Rappel souhaité: ${lead.wants_callback ? "Oui" : "Non"}`,
      `Source: ${lead.source || "landing_cta"}`,
      `Date: ${formatDate(lead.created_at)}`,
    ];
    const oh = lead.opening_hours || {};
    lines.push("Horaires:");
    DAYS.forEach((d, i) => {
      const s = oh[String(i)] || oh[d.toLowerCase().slice(0, 3)];
      if (s && s.closed) lines.push(`  ${d}: Fermé`);
      else if (s && (s.start || s.end)) lines.push(`  ${d}: ${s.start || "?"} – ${s.end || "?"}`);
    });
    navigator.clipboard.writeText(lines.join("\n"));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (!lead && id) {
    return (
      <div className="py-8">
        <p className="text-slate-500">Chargement…</p>
      </div>
    );
  }
  if (!lead) {
    return (
      <div className="py-8">
        <p className="text-red-600">Lead non trouvé</p>
        <Link to="/admin/leads" className="text-indigo-600 hover:underline mt-2 inline-block">
          Retour à la liste
        </Link>
      </div>
    );
  }

  const mailto = `mailto:${lead.email}?subject=UWi – Votre assistante ${lead.assistant_name}`;

  return (
    <div>
      <div className="flex items-center gap-4 mb-6">
        <Link to="/admin/leads" className="text-slate-500 hover:text-slate-700 text-sm">
          ← Leads
        </Link>
        <h1 className="text-2xl font-bold text-slate-800">Lead – {lead.email}</h1>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <div className="rounded-xl border border-slate-200 bg-white p-6">
          <h2 className="text-sm font-semibold text-slate-500 uppercase mb-4">Informations</h2>
          <ul className="space-y-2 text-sm">
            <li><strong>Email:</strong> <a href={mailto} className="text-indigo-600 hover:underline">{lead.email}</a></li>
            <li><strong>Spécialité:</strong> {lead.medical_specialty || "—"}</li>
            <li><strong>Point de douleur:</strong> {lead.primary_pain_point || "—"}</li>
            <li><strong>Appels/jour:</strong> {lead.daily_call_volume}</li>
            <li><strong>Assistante:</strong> {lead.assistant_name}</li>
            <li><strong>Voix:</strong> {lead.voice_gender === "female" ? "Féminine" : "Masculine"}</li>
            <li><strong>Rappel souhaité:</strong> {lead.wants_callback ? "Oui" : "Non"}</li>
            <li><strong>Source:</strong> {lead.source || "landing_cta"}</li>
            <li><strong>Créé le:</strong> {formatDate(lead.created_at)}</li>
          </ul>
          <div className="mt-4 flex gap-2">
            <a href={mailto} className="px-3 py-1.5 rounded-lg bg-slate-100 text-slate-700 text-sm font-medium hover:bg-slate-200">
              Envoyer un email
            </a>
            <button
              type="button"
              onClick={() => {
                navigator.clipboard.writeText(lead.email);
                setCopied(true);
                setTimeout(() => setCopied(false), 2000);
              }}
              className="px-3 py-1.5 rounded-lg bg-slate-100 text-slate-700 text-sm font-medium hover:bg-slate-200"
            >
              Copier l'email
            </button>
          </div>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-6">
          <h2 className="text-sm font-semibold text-slate-500 uppercase mb-2">Horaires cabinet</h2>
          <ul className="space-y-1 text-sm">
            {DAYS.map((d, i) => {
              const s = (lead.opening_hours || {})[String(i)] || (lead.opening_hours || {})[d.toLowerCase().slice(0, 3)];
              return (
                <li key={d}>
                  {d}: {s && s.closed ? "Fermé" : s && (s.start || s.end) ? `${s.start || "?"} – ${s.end || "?"}` : "—"}
                </li>
              );
            })}
          </ul>
        </div>
      </div>

      <div className="mt-6 rounded-xl border border-slate-200 bg-white p-6">
        <h2 className="text-sm font-semibold text-slate-500 uppercase mb-2">Partage rapide</h2>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={copyDirectLink}
            className="px-4 py-2 rounded-lg bg-slate-100 text-slate-700 text-sm font-medium hover:bg-slate-200"
          >
            {copiedLink ? "Lien copié !" : "Copier lien direct"}
          </button>
          <button
            type="button"
            onClick={copySummary}
            className="px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700"
          >
            {copied ? "Copié !" : "Copier le résumé"}
          </button>
        </div>
      </div>

      <div className="mt-6 rounded-xl border border-slate-200 bg-white p-6">
        <h2 className="text-sm font-semibold text-slate-500 uppercase mb-3">Statut</h2>
        <div className="flex flex-wrap gap-2 mb-4">
          {STATUS_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              onClick={() => setStatus(opt.value)}
              className={`px-4 py-2 rounded-lg text-sm font-medium ${
                lead.status === opt.value
                  ? "bg-indigo-600 text-white"
                  : "bg-slate-100 text-slate-700 hover:bg-slate-200"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
        <h2 className="text-sm font-semibold text-slate-500 uppercase mb-2 mt-4">Notes</h2>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={4}
          className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
          placeholder="Notes internes…"
        />
        <button
          type="button"
          onClick={saveNotes}
          disabled={saving}
          className="mt-2 px-4 py-2 rounded-lg bg-slate-800 text-white text-sm font-medium hover:bg-slate-700 disabled:opacity-50"
        >
          {saving ? "Enregistrement…" : "Enregistrer"}
        </button>
      </div>
    </div>
  );
}
