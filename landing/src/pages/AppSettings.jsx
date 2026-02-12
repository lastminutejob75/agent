import { useState, useEffect } from "react";
import { api } from "../lib/api.js";

export default function AppSettings() {
  const [params, setParams] = useState({ contact_email: "", timezone: "", calendar_id: "" });
  const [loading, setLoading] = useState(false);
  const [saved, setSaved] = useState(false);
  const [err, setErr] = useState(null);

  useEffect(() => {
    api
      .tenantMe()
      .then((me) => {
        setParams({
          contact_email: me.contact_email || "",
          timezone: me.timezone || "Europe/Paris",
          calendar_id: me.calendar_id || "",
        });
      })
      .catch(setErr);
  }, []);

  async function handleSubmit(e) {
    e.preventDefault();
    setErr(null);
    setSaved(false);
    setLoading(true);
    try {
      await api.tenantPatchParams(params);
      setSaved(true);
    } catch (e) {
      setErr(e.message || "Erreur");
    } finally {
      setLoading(false);
    }
  }

  if (err) return <p className="text-red-600">{err}</p>;

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold text-gray-900">Paramètres</h2>
      <form onSubmit={handleSubmit} className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm space-y-4 max-w-md">
        <div>
          <label className="block text-sm font-medium text-gray-700">Email de contact</label>
          <input
            type="email"
            value={params.contact_email}
            onChange={(e) => setParams((p) => ({ ...p, contact_email: e.target.value }))}
            className="mt-1 w-full rounded-lg border border-gray-300 px-4 py-2 text-gray-900"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700">Fuseau horaire</label>
          <input
            type="text"
            value={params.timezone}
            onChange={(e) => setParams((p) => ({ ...p, timezone: e.target.value }))}
            placeholder="Europe/Paris"
            className="mt-1 w-full rounded-lg border border-gray-300 px-4 py-2 text-gray-900"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700">ID Calendrier</label>
          <input
            type="text"
            value={params.calendar_id}
            onChange={(e) => setParams((p) => ({ ...p, calendar_id: e.target.value }))}
            placeholder="Optionnel"
            className="mt-1 w-full rounded-lg border border-gray-300 px-4 py-2 text-gray-900"
          />
        </div>
        {saved && <p className="text-sm text-emerald-600">Paramètres enregistrés.</p>}
        <button
          type="submit"
          disabled={loading}
          className="rounded-lg bg-blue-600 px-4 py-2 font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? "Enregistrement..." : "Enregistrer"}
        </button>
      </form>
    </div>
  );
}
