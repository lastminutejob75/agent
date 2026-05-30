import { useCallback, useEffect, useState } from "react";
import { api } from "../../lib/api";

function formatSummaryAge(iso) {
  if (!iso) return "";
  const dt = new Date(iso);
  if (Number.isNaN(dt.getTime())) return "";
  const diffMin = Math.round((Date.now() - dt.getTime()) / 60000);
  if (diffMin < 2) return "à l'instant";
  if (diffMin < 60) return `il y a ${diffMin} min`;
  const diffH = Math.round(diffMin / 60);
  if (diffH < 24) return `il y a ${diffH} h`;
  return dt.toLocaleDateString("fr-FR", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

function SummaryBody({ sections, accessLimited, loading, error, generatedAt, fromCache }) {
  if (loading) {
    return <p className="text-sm text-white/70">Génération du résumé…</p>;
  }
  if (error) {
    return <p className="text-sm text-white/80">{error}</p>;
  }
  const s = sections || {};
  const points = Array.isArray(s.points_attention) ? s.points_attention.filter(Boolean) : [];
  const pending = Array.isArray(s.en_attente) ? s.en_attente.filter(Boolean) : [];

  return (
    <>
      {accessLimited ? (
        <p className="mb-3 rounded-xl border border-amber-300/40 bg-amber-400/10 px-3 py-2 text-xs font-semibold text-amber-100">
          Accès limité : résumé réception uniquement (données de santé protégées).
        </p>
      ) : null}
      <p className="text-[17px] leading-8 text-white/95">
        {s.une_ligne || s.contexte_recent || "Historique insuffisant pour générer un résumé détaillé."}
      </p>
      {s.contexte_recent && s.une_ligne ? (
        <p className="mt-3 text-sm leading-7 text-white/85">{s.contexte_recent}</p>
      ) : null}
      {points.length > 0 ? (
        <ul className="mt-4 flex flex-wrap gap-2">
          {points.map((item) => (
            <li
              key={item}
              className="rounded-full border border-white/25 bg-white/10 px-3 py-1 text-xs font-bold text-white/95"
            >
              {item}
            </li>
          ))}
        </ul>
      ) : null}
      {pending.length > 0 ? (
        <div className="mt-4 rounded-xl border border-white/20 bg-white/5 px-3 py-2.5">
          <div className="text-xs font-black uppercase tracking-wide text-[#11D6DB]">En attente</div>
          <ul className="mt-2 space-y-1 text-sm text-white/90">
            {pending.map((item) => (
              <li key={item}>• {item}</li>
            ))}
          </ul>
        </div>
      ) : null}
      <p className="mt-5 text-sm italic text-white/65">
        Mis à jour {formatSummaryAge(generatedAt) || "—"}
        {fromCache ? " · cache" : ""}
      </p>
    </>
  );
}

/** Résumé IA de fiche patient (GET /summary). */
export default function PatientContextSummary({ phone, refreshNonce = 0, compact = false }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [sections, setSections] = useState({});
  const [meta, setMeta] = useState({ generated_at: "", from_cache: false, access_limited: false });

  const load = useCallback(async () => {
    if (!phone) return;
    setLoading(true);
    setError("");
    try {
      const res = await api.tenantGetPatientSummary(phone);
      const summary = res?.summary || {};
      setSections(summary.sections_json || {});
      setMeta({
        generated_at: summary.generated_at || "",
        from_cache: Boolean(summary.from_cache),
        access_limited: Boolean(summary.access_limited),
      });
    } catch (e) {
      setError(e?.message || "Résumé indisponible.");
      setSections({});
    } finally {
      setLoading(false);
    }
  }, [phone]);

  useEffect(() => {
    void load();
  }, [load, refreshNonce]);

  if (compact) {
    return (
      <SummaryBody
        sections={sections}
        accessLimited={meta.access_limited}
        loading={loading}
        error={error}
        generatedAt={meta.generated_at}
        fromCache={meta.from_cache}
      />
    );
  }

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <div className="text-sm font-black uppercase tracking-wide text-[#11D6DB]">● Résumé IA</div>
        <div className="text-sm italic text-white/60">Généré par IA</div>
      </div>
      <SummaryBody
        sections={sections}
        accessLimited={meta.access_limited}
        loading={loading}
        error={error}
        generatedAt={meta.generated_at}
        fromCache={meta.from_cache}
      />
    </div>
  );
}
