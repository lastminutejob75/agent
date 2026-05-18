import { useState, useEffect, useCallback } from "react";
import { useParams, useSearchParams, Link } from "react-router-dom";
import { adminApi } from "../../lib/adminApi";
import { T } from "../theme.js";

const RESULT_LABELS = { rdv: "RDV", transfer: "Transfert", abandoned: "Abandon", error: "Erreur", other: "Autre" };
const DAYS_OPTIONS = [7, 14, 30];

const SAMPLE_CALL_ITEMS = [
  { tenant_id: 1001, tenant_name: "Cabinet Dentaire Martin", caller_phone: "+33611112222", objective: "Prendre rendez-vous contrôle annuel", call_id: "call_demo_1001_001", started_at: new Date(Date.now() - 20 * 60 * 1000).toISOString(), last_event_at: new Date(Date.now() - 14 * 60 * 1000).toISOString(), duration_sec: 362, result: "rdv", last_event: "booking_confirmed", __sample: true },
  { tenant_id: 1002, tenant_name: "Centre Médical République", caller_phone: "+33622223333", objective: "Parler au secrétariat pour résultat d'examen", call_id: "call_demo_1002_004", started_at: new Date(Date.now() - 55 * 60 * 1000).toISOString(), last_event_at: new Date(Date.now() - 48 * 60 * 1000).toISOString(), duration_sec: 401, result: "transfer", last_event: "transferred_human", __sample: true },
  { tenant_id: 1003, tenant_name: "Kiné Performance Lyon", caller_phone: "+33633334444", objective: "Annulation de séance", call_id: "call_demo_1003_009", started_at: new Date(Date.now() - 95 * 60 * 1000).toISOString(), last_event_at: new Date(Date.now() - 92 * 60 * 1000).toISOString(), duration_sec: 122, result: "abandoned", last_event: "user_abandon", __sample: true },
  { tenant_id: 1004, tenant_name: "Cabinet Infirmier Pasteur", caller_phone: "+33644445555", objective: "Demande urgente de visite à domicile", call_id: "call_demo_1004_012", started_at: new Date(Date.now() - 140 * 60 * 1000).toISOString(), last_event_at: new Date(Date.now() - 136 * 60 * 1000).toISOString(), duration_sec: 198, result: "error", last_event: "error", __sample: true },
  { tenant_id: 1005, tenant_name: "Clinique Orion", caller_phone: "+33655556666", objective: "Confirmer un rendez-vous spécialiste", call_id: "call_demo_1005_014", started_at: new Date(Date.now() - 4 * 3600 * 1000).toISOString(), last_event_at: new Date(Date.now() - 4 * 3600 * 1000 + 330000).toISOString(), duration_sec: 330, result: "rdv", last_event: "booking_confirmed", __sample: true },
  { tenant_id: 1006, tenant_name: "Maison de Santé Voltaire", caller_phone: "+33666667777", objective: "Demander transfert vers médecin traitant", call_id: "call_demo_1006_018", started_at: new Date(Date.now() - 6 * 3600 * 1000).toISOString(), last_event_at: new Date(Date.now() - 6 * 3600 * 1000 + 280000).toISOString(), duration_sec: 280, result: "transfer", last_event: "transferred_human", __sample: true },
  { tenant_id: 1007, tenant_name: "Cabinet Ophta Vision Plus", caller_phone: "+33677778888", objective: "Question sur délai de consultation", call_id: "call_demo_1007_020", started_at: new Date(Date.now() - 8 * 3600 * 1000).toISOString(), last_event_at: new Date(Date.now() - 8 * 3600 * 1000 + 160000).toISOString(), duration_sec: 160, result: "abandoned", last_event: "user_abandon", __sample: true },
  { tenant_id: 1008, tenant_name: "Laboratoire Médical Nova", caller_phone: "+33688889999", objective: "Prendre rendez-vous prise de sang", call_id: "call_demo_1008_026", started_at: new Date(Date.now() - 10 * 3600 * 1000).toISOString(), last_event_at: new Date(Date.now() - 10 * 3600 * 1000 + 370000).toISOString(), duration_sec: 370, result: "rdv", last_event: "booking_confirmed", __sample: true },
  { tenant_id: 1009, tenant_name: "Cabinet Sage-Femme Bel Air", caller_phone: "+33612121212", objective: "Suivi grossesse - demande rappel", call_id: "call_demo_1009_031", started_at: new Date(Date.now() - 13 * 3600 * 1000).toISOString(), last_event_at: new Date(Date.now() - 13 * 3600 * 1000 + 220000).toISOString(), duration_sec: 220, result: "transfer", last_event: "transferred_human", __sample: true },
  { tenant_id: 1010, tenant_name: "Centre Imagerie Wilson", caller_phone: "+33613131313", objective: "Problème de confirmation SMS", call_id: "call_demo_1010_035", started_at: new Date(Date.now() - 18 * 3600 * 1000).toISOString(), last_event_at: new Date(Date.now() - 18 * 3600 * 1000 + 145000).toISOString(), duration_sec: 145, result: "error", last_event: "error", __sample: true },
];

function buildSampleCallDetail(row) {
  return {
    call_id: row.call_id,
    result: row.result,
    duration_sec: row.duration_sec,
    events: [
      { created_at: row.started_at, event: "call_started", meta: { tenant_id: row.tenant_id } },
      { created_at: row.last_event_at, event: row.last_event || "call_ended", meta: { source: "sample_data" } },
    ],
  };
}

function getTenantName(row) {
  return row?.tenant_name || row?.name || `Tenant #${row?.tenant_id ?? "—"}`;
}

function getCallerNumber(row) {
  return (
    row?.caller_phone ||
    row?.phone_number ||
    row?.from_number ||
    row?.caller ||
    row?.patient_phone ||
    "—"
  );
}

function getCallObjective(row) {
  return (
    row?.objective ||
    row?.motif ||
    row?.intent ||
    row?.reason ||
    row?.topic ||
    row?.summary ||
    row?.last_event ||
    "—"
  );
}

function formatDurationLabel(item) {
  const sec = Number(item?.duration_sec);
  if (Number.isFinite(sec) && sec >= 0) {
    const min = Math.floor(sec / 60);
    const rem = sec % 60;
    return `${min}'${String(rem).padStart(2, "0")}`;
  }
  const mins = Number(item?.duration_min);
  if (Number.isFinite(mins) && mins >= 0) return `${Math.floor(mins)}'00`;
  const startRaw = String(item?.started_at || "").trim();
  const endRaw = String(item?.last_event_at || "").trim();
  if (startRaw && endRaw) {
    const startTs = new Date(startRaw).getTime();
    const endTs = new Date(endRaw).getTime();
    if (!Number.isNaN(startTs) && !Number.isNaN(endTs) && endTs >= startTs) {
      const total = Math.floor((endTs - startTs) / 1000);
      const min = Math.floor(total / 60);
      const rem = total % 60;
      return `${min}'${String(rem).padStart(2, "0")}`;
    }
  }
  return "0'00";
}

export default function AdminCalls() {
  const { id: tenantIdParam } = useParams();
  const [searchParams] = useSearchParams();
  const tenantIdFromPath = tenantIdParam ? parseInt(tenantIdParam, 10) : null;
  const tenantIdFromQuery = searchParams.get("tenant_id");
  const tenantId = tenantIdFromPath ?? (tenantIdFromQuery ? parseInt(tenantIdFromQuery, 10) : null);
  const [tenant, setTenant] = useState(null);
  const [data, setData] = useState({ items: [], next_cursor: null, days: 7 });
  const [days, setDays] = useState(() => {
    const d = searchParams.get("days");
    return d ? parseInt(d, 10) : 7;
  });
  const [resultFilter, setResultFilter] = useState(() => {
    const r = searchParams.get("result");
    return r && ["rdv", "transfer", "abandoned", "error"].includes(r) ? r : null;
  });
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);
  const [isSampleMode, setIsSampleMode] = useState(false);
  const [selectedCall, setSelectedCall] = useState(null); // { tenantId, callId }
  const [callDetail, setCallDetail] = useState(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  const load = useCallback(
    async (cursor = null) => {
      setErr(null);
      setLoading(true);
      try {
        if (tenantId) {
          const t = await adminApi.getTenant(tenantId).catch(() => null);
          setTenant(t);
        }
        const res = await adminApi.getCalls({
          tenantId: tenantId ?? undefined,
          days,
          limit: 50,
          cursor: cursor ?? undefined,
          result: resultFilter ?? undefined,
        });
        const items = Array.isArray(res?.items) ? res.items : [];
        if (items.length > 0) {
          setData(res);
          setIsSampleMode(false);
        } else {
          const sample = tenantId ? SAMPLE_CALL_ITEMS.filter((it) => it.tenant_id === tenantId) : SAMPLE_CALL_ITEMS;
          setData({ items: sample, next_cursor: null, days, __sample: true });
          setIsSampleMode(true);
        }
      } catch (e) {
        setErr(e.message || "Erreur chargement appels");
        const sample = tenantId ? SAMPLE_CALL_ITEMS.filter((it) => it.tenant_id === tenantId) : SAMPLE_CALL_ITEMS;
        setData({ items: sample, next_cursor: null, days, __sample: true });
        setIsSampleMode(true);
      } finally {
        setLoading(false);
      }
    },
    [tenantId, days, resultFilter]
  );

  useEffect(() => {
    load();
  }, [load]);

  function loadMore() {
    if (!data.next_cursor || loading) return;
    setLoading(true);
    adminApi
      .getCalls({
        tenantId: tenantId ?? undefined,
        days,
        limit: 50,
        cursor: data.next_cursor,
        result: resultFilter ?? undefined,
      })
      .then((res) => setData((prev) => ({ ...res, items: [...prev.items, ...res.items] })))
      .catch((e) => setErr(e.message))
      .finally(() => setLoading(false));
  }

  function openDrawer(row) {
    if (row?.__sample) {
      setSelectedCall({ tenantId: row.tenant_id ?? tenantId ?? null, callId: row.call_id });
      setCallDetail(buildSampleCallDetail(row));
      setLoadingDetail(false);
      return;
    }
    const tid = row.tenant_id ?? tenantId;
    if (!tid || !row.call_id) return;
    setSelectedCall({ tenantId: tid, callId: row.call_id });
    setCallDetail(null);
    setLoadingDetail(true);
    adminApi
      .getCallDetail(tid, row.call_id)
      .then(setCallDetail)
      .catch(() => setCallDetail(null))
      .finally(() => setLoadingDetail(false));
  }

  function refreshDetail() {
    if (!selectedCall) return;
    setLoadingDetail(true);
    adminApi
      .getCallDetail(selectedCall.tenantId, selectedCall.callId)
      .then(setCallDetail)
      .finally(() => setLoadingDetail(false));
  }

  function copyCallId() {
    if (!selectedCall?.callId) return;
    navigator.clipboard.writeText(selectedCall.callId);
  }

const C = {
  bg: T.bgPage,
  card: T.bgCard,
  border: T.border,
  accent: T.teal,
  text: T.text,
  muted: T.textMuted,
  danger: T.red,
};

  const name = tenant?.name || (tenantId ? `#${tenantId}` : null);

  return (
    <div style={{ padding: "32px", background: C.bg, minHeight: "100vh", display: "flex", gap: 0 }}>
      <div style={{ flex: selectedCall ? 1 : "none", minWidth: 0, width: selectedCall ? undefined : "100%" }}>
        <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 8 }}>
          {tenantId ? (
            <>
              <Link to="/admin/tenants" style={{ color: C.muted }}>← Clients</Link>
              <span style={{ color: C.muted }}>/</span>
              <Link to={`/admin/tenants/${tenantId}`} style={{ color: C.muted }}>{name}</Link>
              <span style={{ color: C.muted }}>/</span>
            </>
          ) : (
            <>
              <Link to="/admin" style={{ color: C.muted }}>← Dashboard</Link>
              <span style={{ color: C.muted }}>/</span>
            </>
          )}
          <span style={{ fontWeight: 600, color: C.text }}>Appels</span>
        </div>

        <div style={{ marginTop: 16, display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 16 }}>
          <h1 style={{ fontSize: 24, fontWeight: 800, color: C.text, letterSpacing: -0.8, margin: 0 }}>
            {tenantId ? `Appels · ${name}` : "Appels (tous clients)"}
          </h1>
          <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 12 }}>
            <span style={{ fontSize: 13, color: C.muted }}>Période</span>
            <select
              value={days}
              onChange={(e) => setDays(Number(e.target.value))}
              style={{
                borderRadius: 8,
                border: `1px solid ${C.border}`,
                padding: "6px 12px",
                fontSize: 13,
                background: C.card,
                color: C.text,
              }}
            >
              {DAYS_OPTIONS.map((d) => (
                <option key={d} value={d}>{d} j</option>
              ))}
            </select>
            <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: C.muted }}>
              <input
                type="checkbox"
                checked={resultFilter === "rdv"}
                onChange={(e) => setResultFilter(e.target.checked ? "rdv" : null)}
                style={{ accentColor: C.accent }}
              />
              Seulement RDV confirmés
            </label>
            <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: C.muted }}>
              <input
                type="checkbox"
                checked={resultFilter === "error"}
                onChange={(e) => setResultFilter(e.target.checked ? "error" : null)}
                style={{ accentColor: C.accent }}
              />
              Seulement erreurs
            </label>
          </div>
        </div>

        {err && (
          <div style={{ marginTop: 16, padding: "10px 12px", borderRadius: 10, background: T.redLight, border: `1px solid ${T.red}40`, color: C.danger, fontSize: 13 }}>
            {err}
          </div>
        )}
        {isSampleMode && (
          <div style={{ marginTop: 12, padding: "10px 12px", borderRadius: 10, background: T.yellowLight, border: `1px solid ${T.yellow}66`, color: T.yellowText, fontSize: 13 }}>
            Affichage en mode exemple (appels fictifs).
          </div>
        )}

        <div style={{ marginTop: 24, overflowX: "auto", borderRadius: 16, border: `1px solid ${C.border}`, background: C.card }}>
          {loading && !data.items?.length ? (
            <div style={{ padding: 32, textAlign: "center", color: C.muted }}>Chargement…</div>
          ) : !data.items?.length ? (
            <div style={{ padding: 32, textAlign: "center", color: C.muted }}>Aucun appel sur la période.</div>
          ) : (
            <>
              <table style={{ minWidth: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ borderBottom: `1px solid ${C.border}` }}>
                    {!tenantId && <th style={{ padding: "12px 16px", textAlign: "left", fontSize: 11, fontWeight: 600, color: C.muted, textTransform: "uppercase" }}>Client</th>}
                    <th style={{ padding: "12px 16px", textAlign: "left", fontSize: 11, fontWeight: 600, color: C.muted, textTransform: "uppercase" }}>Numéro</th>
                    <th style={{ padding: "12px 16px", textAlign: "left", fontSize: 11, fontWeight: 600, color: C.muted, textTransform: "uppercase" }}>But / motif</th>
                    <th style={{ padding: "12px 16px", textAlign: "left", fontSize: 11, fontWeight: 600, color: C.muted, textTransform: "uppercase" }}>Call ID</th>
                    <th style={{ padding: "12px 16px", textAlign: "left", fontSize: 11, fontWeight: 600, color: C.muted, textTransform: "uppercase" }}>Début</th>
                    <th style={{ padding: "12px 16px", textAlign: "left", fontSize: 11, fontWeight: 600, color: C.muted, textTransform: "uppercase" }}>Durée</th>
                    <th style={{ padding: "12px 16px", textAlign: "left", fontSize: 11, fontWeight: 600, color: C.muted, textTransform: "uppercase" }}>Résultat</th>
                    <th style={{ padding: "12px 16px", textAlign: "left", fontSize: 11, fontWeight: 600, color: C.muted, textTransform: "uppercase" }}>Dernier event</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((row) => (
                    <tr
                      key={row.call_id + (row.last_event_at || "")}
                      style={{ borderBottom: `1px solid ${C.border}`, cursor: "pointer" }}
                      onClick={() => openDrawer(row)}
                    >
                      {!tenantId && (
                        <td style={{ padding: "12px 16px", fontSize: 13 }}>
                          <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                            <Link to={`/admin/tenants/${row.tenant_id}`} style={{ color: C.accent }} onClick={(e) => e.stopPropagation()}>
                              {getTenantName(row)}
                            </Link>
                            <span style={{ fontSize: 11, color: C.muted }}>#{row.tenant_id}</span>
                          </div>
                        </td>
                      )}
                      <td style={{ padding: "12px 16px", fontSize: 13, color: C.text, fontFamily: "monospace" }}>{getCallerNumber(row)}</td>
                      <td style={{ padding: "12px 16px", fontSize: 13, color: C.muted, maxWidth: 280, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={getCallObjective(row)}>
                        {getCallObjective(row)}
                      </td>
                      <td style={{ padding: "12px 16px", fontSize: 13, fontFamily: "monospace", color: C.text }}>{row.call_id || "—"}</td>
                      <td style={{ padding: "12px 16px", fontSize: 13, color: C.muted }}>
                        {row.started_at ? new Date(row.started_at).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" }) : "—"}
                      </td>
                      <td style={{ padding: "12px 16px", fontSize: 13, color: C.muted }}>{formatDurationLabel(row)}</td>
                      <td style={{ padding: "12px 16px" }}>
                        <span
                          style={{
                            display: "inline-flex",
                            padding: "2px 8px",
                            fontSize: 11,
                            fontWeight: 600,
                            borderRadius: 6,
                            background:
                              row.result === "rdv"
                                ? T.tealLight
                                : row.result === "transfer"
                                ? "#EFF6FF"
                                : row.result === "abandoned"
                                ? T.yellowLight
                                : T.neutralLight,
                            color:
                              row.result === "rdv"
                                ? C.accent
                                : row.result === "transfer"
                                ? "#3B82F6"
                                : row.result === "abandoned"
                                ? T.yellowText
                                : C.muted,
                          }}
                        >
                          {RESULT_LABELS[row.result] ?? row.result}
                        </span>
                      </td>
                      <td style={{ padding: "12px 16px", fontSize: 13, color: C.muted }}>{row.last_event || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {data.next_cursor && (
                <div style={{ borderTop: `1px solid ${C.border}`, padding: 12, textAlign: "center" }}>
                  <button
                    type="button"
                    onClick={loadMore}
                    disabled={loading}
                    style={{
                      padding: "8px 16px",
                      fontSize: 13,
                      fontWeight: 600,
                      color: C.accent,
                      border: `1px solid ${C.accent}`,
                      borderRadius: 8,
                      background: "transparent",
                      cursor: "pointer",
                      opacity: loading ? 0.5 : 1,
                    }}
                  >
                    {loading ? "Chargement…" : "Voir plus"}
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* Drawer détail call */}
      {selectedCall && (
        <div style={{ width: 420, flexShrink: 0, borderLeft: `1px solid ${C.border}`, background: C.card, display: "flex", flexDirection: "column" }}>
          <div style={{ padding: 16, borderBottom: `1px solid ${C.border}`, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <h2 style={{ fontSize: 18, fontWeight: 600, color: C.text, margin: 0 }}>Détail de l’appel</h2>
            <button
              type="button"
              onClick={() => setSelectedCall(null)}
              style={{ background: "none", border: "none", color: C.muted, fontSize: 24, cursor: "pointer" }}
              aria-label="Fermer"
            >
              ×
            </button>
          </div>
          <div style={{ padding: 16, flex: 1, overflowY: "auto" }}>
            {loadingDetail && !callDetail ? (
              <p style={{ color: C.muted, fontSize: 13 }}>Chargement…</p>
            ) : callDetail ? (
              <>
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                    <span style={{ fontSize: 11, fontWeight: 600, color: C.muted }}>Call ID</span>
                    <code style={{ fontSize: 13, fontFamily: "monospace", background: T.neutralLight, padding: "4px 8px", borderRadius: 6, wordBreak: "break-all" }}>{callDetail.call_id}</code>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ fontSize: 11, fontWeight: 600, color: C.muted }}>Résultat</span>
                    <span
                      style={{
                        display: "inline-flex",
                        padding: "2px 8px",
                        fontSize: 11,
                        fontWeight: 600,
                        borderRadius: 6,
                        background: callDetail.result === "rdv" ? T.tealLight : callDetail.result === "transfer" ? "#EFF6FF" : callDetail.result === "abandoned" ? T.yellowLight : T.neutralLight,
                        color: callDetail.result === "rdv" ? C.accent : callDetail.result === "transfer" ? "#3B82F6" : callDetail.result === "abandoned" ? T.yellowText : C.muted,
                      }}
                    >
                      {RESULT_LABELS[callDetail.result] ?? callDetail.result}
                    </span>
                  </div>
                  <div style={{ fontSize: 13, color: C.muted }}>Durée : {formatDurationLabel(callDetail)}</div>
                </div>
                <div style={{ marginTop: 16, display: "flex", gap: 8 }}>
                  <button type="button" onClick={copyCallId} style={{ padding: "6px 12px", fontSize: 13, fontWeight: 600, color: C.accent, border: `1px solid ${C.accent}`, borderRadius: 8, background: "transparent", cursor: "pointer" }}>Copier call_id</button>
                  <button type="button" onClick={refreshDetail} disabled={loadingDetail} style={{ padding: "6px 12px", fontSize: 13, fontWeight: 600, color: C.muted, border: `1px solid ${C.border}`, borderRadius: 8, background: "transparent", cursor: "pointer", opacity: loadingDetail ? 0.5 : 1 }}>Rafraîchir</button>
                </div>
                <h3 style={{ marginTop: 24, fontSize: 13, fontWeight: 700, color: C.text }}>Timeline</h3>
                <ul style={{ marginTop: 8, padding: 0, listStyle: "none" }}>
                  {callDetail.events?.map((evt, i) => (
                    <li key={i} style={{ fontSize: 13, borderLeft: `2px solid ${C.accent}`, paddingLeft: 12, paddingTop: 4, paddingBottom: 4 }}>
                      <span style={{ color: C.muted }}>{new Date(evt.created_at).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "medium" })}</span>
                      <span style={{ fontWeight: 600, color: C.text, marginLeft: 8 }}>{evt.event}</span>
                      {evt.meta && Object.keys(evt.meta).length > 0 && (
                        <pre style={{ marginTop: 4, fontSize: 11, color: C.muted, background: T.bgSubtle, padding: 8, borderRadius: 6, overflowX: "auto" }}>{JSON.stringify(evt.meta)}</pre>
                      )}
                    </li>
                  ))}
                </ul>
              </>
            ) : (
              <div style={{ textAlign: "center", padding: "24px 0" }}>
                <p style={{ color: C.muted, fontSize: 13 }}>Aucun événement trouvé pour cet appel.</p>
                <button type="button" onClick={() => setSelectedCall(null)} style={{ marginTop: 12, padding: "6px 12px", fontSize: 13, fontWeight: 600, color: C.accent, border: `1px solid ${C.accent}`, borderRadius: 8, background: "transparent", cursor: "pointer" }}>Fermer</button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
