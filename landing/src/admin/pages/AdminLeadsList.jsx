import { useState, useEffect } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { adminApi } from "../../lib/adminApi.js";
import { formatOpeningHoursCompact, formatOpeningHoursPretty, getAmplitudeBadge, getAmplitudeScore } from "../../lib/openingHoursPretty.js";

const STATUS_LABELS = { new: "Nouveau", contacted: "Contacté", converted: "Converti", lost: "Perdu" };
const STATUS_FILTERS = [
  { value: "", label: "Tous" },
  { value: "new", label: "Nouveaux" },
  { value: "contacted", label: "Contactés" },
  { value: "converted", label: "Convertis" },
  { value: "lost", label: "Perdus" },
];

// Score commercial : volume + spécialité + douleur + amplitude horaire
function getLeadPriority(lead) {
  let score = 0;
  const vol = lead.daily_call_volume;
  if (vol === "100+") score += 50;
  else if (vol === "50-100") score += 30;
  else if (vol === "25-50") score += 20;
  const spec = (lead.medical_specialty || "").toLowerCase();
  if (spec === "centre_medical" || spec === "clinique_privee") score += 30;
  const pain = lead.primary_pain_point || "";
  if (pain.includes("secrétariat n'arrive pas") || pain.includes("secrétariat est débordé")) score += 20;
  score += getAmplitudeScore(lead);
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


export default function AdminLeadsList() {
  const [searchParams, setSearchParams] = useSearchParams();
  const statusParam = searchParams.get("status") || "";
  const enterpriseParam = searchParams.get("enterprise") === "1";
  const [leads, setLeads] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    adminApi
      .leadsList({ status: statusParam || undefined, enterprise: enterpriseParam || undefined })
      .then((r) => setLeads(r.leads || []))
      .catch(() => setLeads([]))
      .finally(() => setLoading(false));
  }, [statusParam, enterpriseParam]);

  const setStatusFilter = (value) => {
    const next = new URLSearchParams(searchParams);
    if (value) next.set("status", value);
    else next.delete("status");
    setSearchParams(next);
  };
  const setEnterpriseFilter = (on) => {
    const next = new URLSearchParams(searchParams);
    if (on) next.set("enterprise", "1");
    else next.delete("enterprise");
    setSearchParams(next);
  };

  return (
    <div>
      <h1 className="text-2xl font-bold text-slate-800 mb-4">Leads</h1>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <span className="text-sm font-medium text-slate-600">Pipeline :</span>
        {STATUS_FILTERS.map(({ value, label }) => (
          <button
            key={value || "all"}
            type="button"
            onClick={() => setStatusFilter(value)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              statusParam === value
                ? "bg-indigo-600 text-white"
                : "bg-slate-100 text-slate-700 hover:bg-slate-200"
            }`}
          >
            {label}
          </button>
        ))}
        <span className="text-slate-300 mx-1">|</span>
        <button
          type="button"
          onClick={() => setEnterpriseFilter(!enterpriseParam)}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            enterpriseParam ? "bg-amber-500 text-white" : "bg-slate-100 text-slate-700 hover:bg-slate-200"
          }`}
        >
          🔥 Grands comptes
        </button>
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
                <th className="px-4 py-3 text-left text-xs font-semibold text-slate-600 uppercase"></th>
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
                  <td colSpan={11} className="px-4 py-8 text-center text-slate-500">
                    Aucun lead
                  </td>
                </tr>
              ) : (
                leads.map((lead) => {
                  const prio = getLeadPriority(lead);
                  const ampBadge = getAmplitudeBadge(lead);
                  return (
                  <tr key={lead.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3 text-sm text-slate-600">{formatDate(lead.created_at)}</td>
                    <td className="px-4 py-3 text-sm font-medium text-slate-800">{lead.email}</td>
                    <td className="px-4 py-3 text-sm text-slate-600">{lead.medical_specialty_label || lead.medical_specialty || "—"}</td>
                    <td className="px-4 py-3 text-sm text-slate-600">{lead.daily_call_volume}</td>
                    <td className="px-4 py-3 flex flex-wrap gap-1">
                      {(lead.is_enterprise || lead.daily_call_volume === "100+") && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold bg-amber-100 text-amber-800" title="Grand compte potentiel">
                          🔥 Grand compte
                        </span>
                      )}
                      {ampBadge && (
                        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${ampBadge.className}`} title={ampBadge.label}>
                          ⏰ {ampBadge.label}
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-sm text-slate-500 max-w-[140px] truncate" title={lead.primary_pain_point || ""}>{lead.primary_pain_point || "—"}</td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${prio.className}`} title={`Score: ${prio.score}`}>
                        {prio.label}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-slate-600">
                      {lead.assistant_name} ({lead.voice_gender === "female" ? "F" : "M"})
                    </td>
                    <td className="px-4 py-3 text-sm text-slate-500 max-w-xs truncate" title={formatOpeningHoursPretty(lead.opening_hours)}>
                      {formatOpeningHoursCompact(lead.opening_hours)}
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
