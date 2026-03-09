import { useState, useEffect } from "react";
import { api } from "../lib/api.js";

export default function AppSettings() {
  const [params, setParams] = useState({ contact_email: "", timezone: "", calendar_id: "" });
  const [loading, setLoading] = useState(false);
  const [saved, setSaved] = useState(false);
  const [err, setErr] = useState(null);
  const [passwords, setPasswords] = useState({ newPassword: "", confirmPassword: "" });
  const [passwordLoading, setPasswordLoading] = useState(false);
  const [passwordSaved, setPasswordSaved] = useState(false);
  const [passwordErr, setPasswordErr] = useState(null);

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

  async function handlePasswordSubmit(e) {
    e.preventDefault();
    setPasswordErr(null);
    setPasswordSaved(false);

    if ((passwords.newPassword || "").trim().length < 8) {
      setPasswordErr("Le mot de passe doit contenir au moins 8 caractères.");
      return;
    }
    if (passwords.newPassword !== passwords.confirmPassword) {
      setPasswordErr("Les mots de passe ne correspondent pas.");
      return;
    }

    setPasswordLoading(true);
    try {
      await api.tenantChangePassword(passwords.newPassword);
      setPasswordSaved(true);
      setPasswords({ newPassword: "", confirmPassword: "" });
    } catch (e) {
      setPasswordErr(e.message || "Erreur");
    } finally {
      setPasswordLoading(false);
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

      <form
        id="security"
        onSubmit={handlePasswordSubmit}
        className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm space-y-4 max-w-md"
        style={{ scrollMarginTop: 96 }}
      >
        <div>
          <h3 className="text-base font-semibold text-gray-900">Sécurité</h3>
          <p className="mt-1 text-sm text-gray-600">Changez votre mot de passe d'accès à l'espace client.</p>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700">Nouveau mot de passe</label>
          <input
            type="password"
            value={passwords.newPassword}
            onChange={(e) => setPasswords((p) => ({ ...p, newPassword: e.target.value }))}
            minLength={8}
            className="mt-1 w-full rounded-lg border border-gray-300 px-4 py-2 text-gray-900"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700">Confirmer</label>
          <input
            type="password"
            value={passwords.confirmPassword}
            onChange={(e) => setPasswords((p) => ({ ...p, confirmPassword: e.target.value }))}
            minLength={8}
            className="mt-1 w-full rounded-lg border border-gray-300 px-4 py-2 text-gray-900"
          />
        </div>
        {passwordErr && <p className="text-sm text-red-600">{passwordErr}</p>}
        {passwordSaved && <p className="text-sm text-emerald-600">Mot de passe mis à jour.</p>}
        <button
          type="submit"
          disabled={passwordLoading}
          className="rounded-lg bg-slate-900 px-4 py-2 font-medium text-white hover:bg-slate-800 disabled:opacity-50"
        >
          {passwordLoading ? "Enregistrement..." : "Enregistrer"}
        </button>
      </form>
    </div>
  );
}
