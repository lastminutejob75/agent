import { Suspense, lazy, useState, useEffect } from "react";
import { api } from "../lib/api.js";
import {
  buildTransferConfigSignature,
  isTransferConfigConfirmed,
  sanitizePhoneInput,
  normalizeFrenchPhone,
} from "../lib/transferConfig.js";

const CallTransferSettings = lazy(() => import("../components/CallTransferSettings.jsx"));

function SettingsSectionFallback({ text = "Chargement…" }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
      <p className="text-sm text-gray-500">{text}</p>
    </div>
  );
}

function buildTransferInitialConfig(me) {
  if (!me) return null;
  const hasTransferConfig =
    Boolean(me.transfer_config_confirmed_signature) ||
    Boolean(me.transfer_config_confirmed_at) ||
    Boolean(me.transfer_number) ||
    Boolean(me.transfer_practitioner_phone) ||
    Boolean(me.transfer_always_urgent) ||
    Boolean(me.transfer_no_consultation) ||
    Boolean(me.transfer_live_enabled) ||
    me.transfer_callback_enabled === false ||
    Boolean((me.transfer_cases || []).length) ||
    Boolean(Object.keys(me.transfer_hours || {}).length);
  if (!hasTransferConfig) return null;
  return {
    main_number: me.transfer_number || me.phone_number || "",
    always_urgent: Boolean(me.transfer_always_urgent),
    transfer_cases: Array.isArray(me.transfer_cases) ? me.transfer_cases : [],
    hours: me.transfer_hours || {},
    no_consultation: Boolean(me.transfer_no_consultation),
    practitioner_phone: me.transfer_practitioner_phone || "",
    live_enabled: Boolean(me.transfer_live_enabled),
    callback_enabled: me.transfer_callback_enabled !== false,
    confirmed: isTransferConfigConfirmed(me) || (!me.transfer_config_confirmed_signature && Boolean(me.transfer_config_confirmed_at)),
    confirmed_at: me.transfer_config_confirmed_at || "",
  };
}

export default function AppSettings() {
  const [params, setParams] = useState({ contact_email: "", timezone: "", calendar_id: "" });
  const [loading, setLoading] = useState(false);
  const [saved, setSaved] = useState(false);
  const [err, setErr] = useState(null);
  const [transferInitialConfig, setTransferInitialConfig] = useState(null);
  const [transferSaved, setTransferSaved] = useState(false);
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
          phone_number: me.phone_number || "",
        });
        setTransferInitialConfig(buildTransferInitialConfig(me));
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
          <label className="block text-sm font-medium text-gray-700">Numero du cabinet</label>
          <input
            type="tel"
            value={params.phone_number || ""}
            onChange={(e) => setParams((p) => ({ ...p, phone_number: sanitizePhoneInput(e.target.value) }))}
            placeholder="+33123456789"
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

      <Suspense fallback={<SettingsSectionFallback text="Chargement de la configuration du transfert…" />}>
        <CallTransferSettings
          cabinetPhone={params.phone_number || ""}
          initialConfig={transferInitialConfig}
          onSave={async (payload) => {
            const liveEnabled = transferInitialConfig?.live_enabled !== false;
            const callbackEnabled = transferInitialConfig?.callback_enabled !== false;
            const transferNumber = normalizeFrenchPhone(payload.main_number || params.phone_number || "");
            const confirmedAt = new Date().toISOString();
            const nextConfig = {
              main_number: transferNumber,
              always_urgent: Boolean(payload.always_urgent),
              transfer_cases: payload.transfer_cases || [],
              hours: payload.hours || {},
              no_consultation: Boolean(payload.no_consultation),
              practitioner_phone: transferInitialConfig?.practitioner_phone || "",
              live_enabled: liveEnabled,
              callback_enabled: callbackEnabled,
              confirmed: true,
              confirmed_at: confirmedAt,
            };
            await api.tenantPatchParams({
              transfer_number: transferNumber,
              transfer_live_enabled: liveEnabled ? "true" : "false",
              transfer_callback_enabled: callbackEnabled ? "true" : "false",
              transfer_cases: payload.transfer_cases || [],
              transfer_hours: payload.hours || {},
              transfer_always_urgent: payload.always_urgent ? "true" : "false",
              transfer_no_consultation: payload.no_consultation ? "true" : "false",
              transfer_config_confirmed_signature: buildTransferConfigSignature({
                phone_number: params.phone_number || "",
                transfer_number: transferNumber,
                transfer_practitioner_phone: transferInitialConfig?.practitioner_phone || "",
                transfer_live_enabled: liveEnabled ? "true" : "false",
                transfer_callback_enabled: callbackEnabled ? "true" : "false",
                transfer_cases: payload.transfer_cases || [],
                transfer_hours: payload.hours || {},
                transfer_always_urgent: payload.always_urgent ? "true" : "false",
                transfer_no_consultation: payload.no_consultation ? "true" : "false",
              }),
              transfer_config_confirmed_at: confirmedAt,
            });
            setTransferInitialConfig(nextConfig);
            setTransferSaved(true);
            return { confirmed_at: confirmedAt };
          }}
        />
      </Suspense>
      {transferSaved && <p className="text-sm text-emerald-600">Configuration du transfert enregistree.</p>}

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
