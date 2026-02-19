import { Link } from "react-router-dom";

export default function TenantCardKpis({ stats7d, tenantId }) {
  const calls = stats7d?.calls_total ?? 0;
  const abandoned = stats7d?.calls_abandoned ?? 0;
  const transfers = stats7d?.transfers_total ?? 0;
  const rdv = stats7d?.appointments_total ?? 0;
  const abandonRate = calls > 0 ? Math.round((abandoned / calls) * 100) : 0;
  const antiLoop = stats7d?.anti_loop_total ?? "—";

  return (
    <section className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">KPIs rapides (7j)</h2>
      <div className="grid grid-cols-2 gap-3 text-sm">
        <div className="bg-slate-50 rounded-lg p-3">
          <div className="text-gray-500 text-xs">Appels</div>
          <div className="text-lg font-bold text-gray-900">{calls}</div>
        </div>
        <div className="bg-slate-50 rounded-lg p-3">
          <div className="text-gray-500 text-xs">Abandons</div>
          <div className="text-lg font-bold text-gray-900">{abandoned}</div>
        </div>
        <div className="bg-slate-50 rounded-lg p-3">
          <div className="text-gray-500 text-xs">Transferts</div>
          <div className="text-lg font-bold text-gray-900">{transfers}</div>
        </div>
        <div className="bg-slate-50 rounded-lg p-3">
          <div className="text-gray-500 text-xs">RDV confirmés</div>
          <div className="text-lg font-bold text-gray-900">{rdv}</div>
        </div>
        <div className="bg-slate-50 rounded-lg p-3">
          <div className="text-gray-500 text-xs">Taux abandon %</div>
          <div className="text-lg font-bold text-gray-900">{abandonRate}%</div>
        </div>
        <div className="bg-slate-50 rounded-lg p-3">
          <div className="text-gray-500 text-xs">Anti-loop 7j</div>
          <div className="text-lg font-bold text-gray-900">{antiLoop}</div>
        </div>
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <Link to={`/admin/tenants/${tenantId}/calls`} className="px-3 py-1.5 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700">
          Voir appels
        </Link>
        <Link to="/admin/quality" className="px-3 py-1.5 border border-gray-300 text-sm rounded-lg hover:bg-gray-50">
          Voir quality
        </Link>
      </div>
    </section>
  );
}
