import { useState, useEffect, useCallback } from "react";
import { useParams, Link } from "react-router-dom";
import { adminApi } from "../../lib/adminApi";

const RESULT_LABELS = { rdv: "RDV", transfer: "Transfert", abandoned: "Abandon", other: "Autre" };
const DAYS_OPTIONS = [7, 14, 30];

export default function AdminCalls() {
  const { id: tenantIdParam } = useParams();
  const tenantId = tenantIdParam ? parseInt(tenantIdParam, 10) : null;
  const [tenant, setTenant] = useState(null);
  const [data, setData] = useState({ items: [], next_cursor: null, days: 7 });
  const [days, setDays] = useState(7);
  const [resultFilter, setResultFilter] = useState(null); // null | 'rdv' | 'error'
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

  if (err && !data.items?.length) {
    return (
      <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
        {err}
        <Link to={tenantId ? `/admin/tenants/${tenantId}` : "/admin"} className="block mt-2 text-indigo-600 hover:underline">
          ← Retour
        </Link>
      </div>
    );
  }

  const name = tenant?.name || (tenantId ? `#${tenantId}` : null);

  return (
    <div className="flex gap-0">
      <div className={selectedCall ? "flex-1 min-w-0" : "w-full"}>
        <div className="flex flex-wrap items-center gap-2">
          {tenantId ? (
            <>
              <Link to="/admin/tenants" className="text-gray-600 hover:text-gray-900">← Clients</Link>
              <span className="text-gray-400">/</span>
              <Link to={`/admin/tenants/${tenantId}`} className="text-gray-600 hover:text-gray-900">{name}</Link>
              <span className="text-gray-400">/</span>
            </>
          ) : (
            <>
              <Link to="/admin" className="text-gray-600 hover:text-gray-900">← Dashboard</Link>
              <span className="text-gray-400">/</span>
            </>
          )}
          <span className="font-medium text-gray-900">Appels</span>
        </div>

        <div className="mt-4 flex flex-wrap items-center justify-between gap-4">
          <h1 className="text-2xl font-bold text-gray-900">
            {tenantId ? `Appels · ${name}` : "Appels (tous clients)"}
          </h1>
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-sm text-gray-500">Période</span>
            <select
              value={days}
              onChange={(e) => setDays(Number(e.target.value))}
              className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm text-gray-900"
            >
              {DAYS_OPTIONS.map((d) => (
                <option key={d} value={d}>{d} j</option>
              ))}
            </select>
            <label className="flex items-center gap-2 text-sm text-gray-700">
              <input
                type="checkbox"
                checked={resultFilter === "rdv"}
                onChange={(e) => setResultFilter(e.target.checked ? "rdv" : null)}
                className="rounded border-gray-300"
              />
              Seulement RDV confirmés
            </label>
            <label className="flex items-center gap-2 text-sm text-gray-700">
              <input
                type="checkbox"
                checked={resultFilter === "error"}
                onChange={(e) => setResultFilter(e.target.checked ? "error" : null)}
                className="rounded border-gray-300"
              />
              Seulement erreurs
            </label>
          </div>
        </div>

        <div className="mt-6 overflow-x-auto rounded-xl border border-gray-200 bg-white shadow-sm">
          {loading && !data.items?.length ? (
            <div className="p-8 text-gray-500 text-center">Chargement…</div>
          ) : !data.items?.length ? (
            <div className="p-8 text-gray-500 text-center">Aucun appel sur la période.</div>
          ) : (
            <>
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    {!tenantId && <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Client</th>}
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Call ID</th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Début</th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Durée (min)</th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Résultat</th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Dernier event</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {data.items.map((row) => (
                    <tr
                      key={row.call_id + (row.last_event_at || "")}
                      className="hover:bg-gray-50 cursor-pointer"
                      onClick={() => openDrawer(row)}
                    >
                      {!tenantId && (
                        <td className="px-4 py-2 text-sm">
                          <Link to={`/admin/tenants/${row.tenant_id}`} className="text-indigo-600 hover:underline" onClick={(e) => e.stopPropagation()}>
                            #{row.tenant_id}
                          </Link>
                        </td>
                      )}
                      <td className="px-4 py-2 text-sm font-mono text-gray-700">{row.call_id || "—"}</td>
                      <td className="px-4 py-2 text-sm text-gray-600">
                        {row.started_at ? new Date(row.started_at).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" }) : "—"}
                      </td>
                      <td className="px-4 py-2 text-sm text-gray-600">{row.duration_min ?? "—"}</td>
                      <td className="px-4 py-2">
                        <span
                          className={`inline-flex px-2 py-0.5 text-xs font-medium rounded-full ${
                            row.result === "rdv"
                              ? "bg-green-100 text-green-800"
                              : row.result === "transfer"
                              ? "bg-blue-100 text-blue-800"
                              : row.result === "abandoned"
                              ? "bg-amber-100 text-amber-800"
                              : "bg-gray-100 text-gray-700"
                          }`}
                        >
                          {RESULT_LABELS[row.result] ?? row.result}
                        </span>
                      </td>
                      <td className="px-4 py-2 text-sm text-gray-600">{row.last_event || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {data.next_cursor && (
                <div className="border-t border-gray-100 p-3 text-center">
                  <button
                    type="button"
                    onClick={loadMore}
                    disabled={loading}
                    className="px-4 py-2 text-sm font-medium text-indigo-600 border border-indigo-200 rounded-lg hover:bg-indigo-50 disabled:opacity-50"
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
        <div className="w-[420px] shrink-0 border-l border-gray-200 bg-white flex flex-col shadow-lg">
          <div className="p-4 border-b border-gray-100 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-900">Détail de l’appel</h2>
            <button
              type="button"
              onClick={() => setSelectedCall(null)}
              className="text-gray-400 hover:text-gray-600 text-xl leading-none"
              aria-label="Fermer"
            >
              ×
            </button>
          </div>
          <div className="p-4 flex-1 overflow-y-auto">
            {loadingDetail && !callDetail ? (
              <p className="text-gray-500 text-sm">Chargement…</p>
            ) : callDetail ? (
              <>
                <div className="space-y-2">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs font-medium text-gray-500">Call ID</span>
                    <code className="text-sm font-mono bg-gray-100 px-2 py-0.5 rounded break-all">{callDetail.call_id}</code>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-medium text-gray-500">Résultat</span>
                    <span
                      className={`inline-flex px-2 py-0.5 text-xs font-medium rounded-full ${
                        callDetail.result === "rdv"
                          ? "bg-green-100 text-green-800"
                          : callDetail.result === "transfer"
                          ? "bg-blue-100 text-blue-800"
                          : callDetail.result === "abandoned"
                          ? "bg-amber-100 text-amber-800"
                          : "bg-gray-100 text-gray-700"
                      }`}
                    >
                      {RESULT_LABELS[callDetail.result] ?? callDetail.result}
                    </span>
                  </div>
                  <div className="text-sm text-gray-600">
                    Durée : {callDetail.duration_min != null ? `${callDetail.duration_min} min` : "—"}
                  </div>
                </div>
                <div className="mt-4 flex gap-2">
                  <button
                    type="button"
                    onClick={copyCallId}
                    className="px-3 py-1.5 text-sm font-medium text-indigo-600 border border-indigo-200 rounded-lg hover:bg-indigo-50"
                  >
                    Copier call_id
                  </button>
                  <button
                    type="button"
                    onClick={refreshDetail}
                    disabled={loadingDetail}
                    className="px-3 py-1.5 text-sm font-medium text-gray-700 border border-gray-200 rounded-lg hover:bg-gray-50 disabled:opacity-50"
                  >
                    Rafraîchir
                  </button>
                </div>
                <h3 className="mt-6 text-sm font-semibold text-gray-800">Timeline</h3>
                <ul className="mt-2 space-y-2">
                  {callDetail.events?.map((evt, i) => (
                    <li key={i} className="text-sm border-l-2 border-indigo-200 pl-3 py-1">
                      <span className="text-gray-500">
                        {new Date(evt.created_at).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "medium" })}
                      </span>
                      <span className="font-medium text-gray-800 ml-2">{evt.event}</span>
                      {evt.meta && Object.keys(evt.meta).length > 0 && (
                        <pre className="mt-1 text-xs text-gray-500 bg-gray-50 p-2 rounded overflow-x-auto">
                          {JSON.stringify(evt.meta)}
                        </pre>
                      )}
                    </li>
                  ))}
                </ul>
              </>
            ) : (
              <div className="text-center py-6">
                <p className="text-gray-600 text-sm">Aucun événement trouvé pour cet appel.</p>
                <button
                  type="button"
                  onClick={() => setSelectedCall(null)}
                  className="mt-3 px-3 py-1.5 text-sm font-medium text-indigo-600 border border-indigo-200 rounded-lg hover:bg-indigo-50"
                >
                  Fermer
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
