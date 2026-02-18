import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { api } from "../lib/api.js";

export default function AdminClientNew() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    name: "",
    contact_email: "",
    timezone: "Europe/Paris",
    business_type: "",
    notes: "",
  });
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  async function onSubmit(e) {
    e.preventDefault();
    setErrorMsg("");
    setLoading(true);
    try {
      const payload = {
        name: form.name.trim(),
        contact_email: form.contact_email.trim(),
        timezone: form.timezone || "Europe/Paris",
        business_type: form.business_type.trim() || undefined,
        notes: form.notes.trim() || undefined,
      };
      const created = await api.adminCreateTenant(payload);
      navigate(`/admin/tenants/${created.tenant_id}`);
    } catch (err) {
      const code = err?.data?.error_code;
      if (err.status === 409 && code === "EMAIL_ALREADY_ASSIGNED") {
        setErrorMsg("Cet email est déjà rattaché à un autre client (v1 : 1 email = 1 tenant).");
      } else {
        setErrorMsg(err.message || "Erreur lors de la création.");
      }
    } finally {
      setLoading(false);
    }
  }

  const inputClass =
    "block w-full mt-1 px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-[#0066CC] focus:border-[#0066CC] text-gray-900 bg-white";
  const labelClass = "block text-sm font-medium text-gray-700";

  return (
    <div className="max-w-2xl mx-auto px-6 py-8">
      <Link to="/admin" className="inline-block text-gray-600 hover:text-gray-900 mb-4">
        ← Admin
      </Link>
      <h1 className="text-2xl font-semibold text-gray-900 mt-2">Créer un client</h1>

      {errorMsg && (
        <div className="mt-4 p-3 border border-red-300 bg-red-50 text-red-800 rounded-lg text-sm">
          {errorMsg}
        </div>
      )}

      <form onSubmit={onSubmit} className="flex flex-col gap-5 mt-6">
        <label className={labelClass}>
          Nom entreprise *
          <input
            type="text"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            required
            minLength={2}
            maxLength={120}
            className={inputClass}
          />
        </label>

        <label className={labelClass}>
          Email contact *
          <input
            type="email"
            value={form.contact_email}
            onChange={(e) => setForm({ ...form, contact_email: e.target.value })}
            required
            className={inputClass}
          />
        </label>

        <label className={labelClass}>
          Fuseau horaire
          <input
            type="text"
            value={form.timezone}
            onChange={(e) => setForm({ ...form, timezone: e.target.value })}
            className={inputClass}
          />
        </label>

        <label className={labelClass}>
          Type de business
          <input
            type="text"
            value={form.business_type}
            onChange={(e) => setForm({ ...form, business_type: e.target.value })}
            placeholder="medical / artisan / …"
            className={inputClass}
          />
        </label>

        <label className={labelClass}>
          Notes internes
          <textarea
            value={form.notes}
            onChange={(e) => setForm({ ...form, notes: e.target.value })}
            rows={4}
            className={inputClass + " resize-y"}
          />
        </label>

        <button
          type="submit"
          disabled={loading}
          className="mt-2 px-5 py-2.5 bg-[#0066CC] text-white font-medium rounded-lg hover:bg-[#0052A3] disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? "Création…" : "Créer le client"}
        </button>
      </form>
    </div>
  );
}
