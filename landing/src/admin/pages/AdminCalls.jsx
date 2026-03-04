import { useState, useEffect, useCallback } from "react";
import { useParams, useSearchParams, Link } from "react-router-dom";
import { adminApi } from "../../lib/adminApi";

const RESULT_LABELS = { rdv: "RDV", transfer: "Transfert", abandoned: "Abandon", error: "Erreur", other: "Autre" };
const DAYS_OPTIONS = [7, 14, 30];

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
        setData(res);
      } catch (e) {
        setErr(e.message || "Erreur chargement appels");
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
  bg: "#0A1828",
  card: "#132840",
  border: "#1E3D56",
  accent: "#00E5A0",
  text: "#FFFFFF",
  muted: "#6B90A8",
  danger: "#FF6B6B",
};

  if (err && !data.items?.length) {
    return (
      <div
        style={{
          padding: "32px",
          background: "rgba(255,107,107,0.1)",
          border: "1px solid rgba(255,107,107,0.3)",
          borderRadius: 12,
          color: C.danger,
        }}
      >
        {err}
        <Link
          to={tenantId ? `/admin/tenants/${tenantId}` : "/admin"}
          style={{ display: "block", marginTop: 8, color: C.accent, fontWeight: 600 }}
        >
          ← Retour
        </Link>
      </div>
    );
  }

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
                    <th style={{ padding: "12px 16px", textAlign: "left", fontSize: 11, fontWeight: 600, color: C.muted, textTransform: "uppercase" }}>Call ID</th>
                    <th style={{ padding: "12px 16px", textAlign: "left", fontSize: 11, fontWeight: 600, color: C.muted, textTransform: "uppercase" }}>Début</th>
                    <th style={{ padding: "12px 16px", textAlign: "left", fontSize: 11, fontWeight: 600, color: C.muted, textTransform: "uppercase" }}>Durée (min)</th>
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
                          <Link to={`/admin/tenants/${row.tenant_id}`} style={{ color: C.accent }} onClick={(e) => e.stopPropagation()}>
                            #{row.tenant_id}
                          </Link>
                        </td>
                      )}
                      <td style={{ padding: "12px 16px", fontSize: 13, fontFamily: "monospace", color: C.text }}>{row.call_id || "—"}</td>
                      <td style={{ padding: "12px 16px", fontSize: 13, color: C.muted }}>
                        {row.started_at ? new Date(row.started_at).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" }) : "—"}
                      </td>
                      <td style={{ padding: "12px 16px", fontSize: 13, color: C.muted }}>{row.duration_min ?? "—"}</td>
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
                                ? "rgba(0,229,160,0.2)"
                                : row.result === "transfer"
                                ? "rgba(91,168,255,0.2)"
                                : row.result === "abandoned"
                                ? "rgba(255,179,71,0.2)"
                                : "rgba(107,144,168,0.2)",
                            color:
                              row.result === "rdv"
                                ? C.accent
                                : row.result === "transfer"
                                ? "#5BA8FF"
                                : row.result === "abandoned"
                                ? "#FFB347"
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
                    <code style={{ fontSize: 13, fontFamily: "monospace", background: "rgba(107,144,168,0.15)", padding: "4px 8px", borderRadius: 6, wordBreak: "break-all" }}>{callDetail.call_id}</code>
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
                        background: callDetail.result === "rdv" ? "rgba(0,229,160,0.2)" : callDetail.result === "transfer" ? "rgba(91,168,255,0.2)" : callDetail.result === "abandoned" ? "rgba(255,179,71,0.2)" : "rgba(107,144,168,0.2)",
                        color: callDetail.result === "rdv" ? C.accent : callDetail.result === "transfer" ? "#5BA8FF" : callDetail.result === "abandoned" ? "#FFB347" : C.muted,
                      }}
                    >
                      {RESULT_LABELS[callDetail.result] ?? callDetail.result}
                    </span>
                  </div>
                  <div style={{ fontSize: 13, color: C.muted }}>Durée : {callDetail.duration_min != null ? `${callDetail.duration_min} min` : "—"}</div>
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
                        <pre style={{ marginTop: 4, fontSize: 11, color: C.muted, background: "rgba(107,144,168,0.1)", padding: 8, borderRadius: 6, overflowX: "auto" }}>{JSON.stringify(evt.meta)}</pre>
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
