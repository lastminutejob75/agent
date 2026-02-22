import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { adminApi } from "../../lib/adminApi.js";

const STATUS_LABELS = { new: "Nouveau", contacted: "Contacté", converted: "Converti", lost: "Perdu" };

// Score commercial : volume 100+ → +50, 50-100 → +30, 25-50 → +20, Centre/Clinique → +30, secrétariat débordé → +20
function getLeadPriority(lead) {
  let score = 0;
  const vol = lead.daily_call_volume;
  if (vol === "100+") score += 50;
  else if (vol === "50-100") score += 30;
  else if (vol === "25-50") score += 20;
  const spec = (lead.medical_specialty || "").toLowerCase();
  if (spec.includes("centre médical") || spec.includes("clinique privée")) score += 30;
  const pain = lead.primary_pain_point || "";
  if (pain.includes("secrétariat est débordé")) score += 20;
  if (score >= 70) return { score, label: "Haute priorité", className: "bg-red-100 text-red-800" };
  if (score >= 40) return { score, label: "Moyenne", className: "bg-amber-100 text-amber-800" };
  return { score, label: "Standard", className: "bg-slate-100 text-slate-700" };
}

function formatDate(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("fr-FR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function hoursSummary(oh) {
  if (!oh || typeof oh !== "object") return "—";
  const days = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"];
  const parts = [];
  for (let i = 0; i < 7; i++) {
    const k = String(i);
    const s = oh[k];
    if (s && !s.closed && (s.start || s.end))
      parts.push(`${days[i]} ${s.start || "?"}-${s.end || "?"}`);
  }
  return parts.length ? parts.join(", ") : "—";
}

export default function AdminLeadsList() {
  const [leads, setLeads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("");

  useEffect(() => {
    adminApi
      .leadsList(filter || undefined)
      .then((r) => setLeads(r.leads || []))
      .catch(() => setLeads([]))
      .finally(() => setLoading(false));
  }, [filter]);

  return (
    <div>
      <h1 className="text-2xl font-bold text-slate-800 mb-4">Leads</h1>
      <div className="mb-4 flex gap-2">
        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
        >
          <option value="">Tous</option>
          <option value="new">Nouveaux</option>
          <option value="contacted">Contactés</option>
          <option value="converted">Convertis</option>
          <option value="lost">Perdus</option>
        </select>
      </div>
      {loading ? (
        <p className="text-slate-500">Chargement…</p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
          <table className="min-w-full divide-y divide-slate-200">
            <thead className="bg-slate-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold text-slate-600 uppercase">Date</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-slate-600 uppercase">Email</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-slate-600 uppercase">Spécialité</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-slate-600 uppercase">Appels/jour</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-slate-600 uppercase">Douleur</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-slate-600 uppercase">Priorité</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-slate-600 uppercase">Assistante</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-slate-600 uppercase">Horaires</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-slate-600 uppercase">Statut</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-slate-600 uppercase">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {leads.length === 0 ? (
                <tr>
                  <td colSpan={10} className="px-4 py-8 text-center text-slate-500">
                    Aucun lead
                  </td>
                </tr>
              ) : (
                leads.map((lead) => {
                  const prio = getLeadPriority(lead);
                  return (
                  <tr key={lead.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3 text-sm text-slate-600">{formatDate(lead.created_at)}</td>
                    <td className="px-4 py-3 text-sm font-medium text-slate-800">{lead.email}</td>
                    <td className="px-4 py-3 text-sm text-slate-600">{lead.medical_specialty || "—"}</td>
                    <td className="px-4 py-3 text-sm text-slate-600">{lead.daily_call_volume}</td>
                    <td className="px-4 py-3 text-sm text-slate-500 max-w-[140px] truncate" title={lead.primary_pain_point || ""}>{lead.primary_pain_point || "—"}</td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${prio.className}`} title={`Score: ${prio.score}`}>
                        {prio.label}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-slate-600">
                      {lead.assistant_name} ({lead.voice_gender === "female" ? "F" : "M"})
                    </td>
                    <td className="px-4 py-3 text-sm text-slate-500 max-w-xs truncate" title={hoursSummary(lead.opening_hours)}>
                      {hoursSummary(lead.opening_hours)}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${
                          lead.status === "new"
                            ? "bg-amber-100 text-amber-800"
                            : lead.status === "converted"
                              ? "bg-green-100 text-green-800"
                              : lead.status === "lost"
                                ? "bg-slate-100 text-slate-600"
                                : "bg-slate-100 text-slate-700"
                        }`}
                      >
                        {STATUS_LABELS[lead.status] || lead.status}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <Link
                        to={`/admin/leads/${lead.id}`}
                        className="text-indigo-600 hover:underline text-sm font-medium"
                      >
                        Voir
                      </Link>
                    </td>
                  </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
