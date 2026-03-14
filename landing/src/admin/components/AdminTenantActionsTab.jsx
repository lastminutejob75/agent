import { Suspense, lazy, useCallback, useEffect, useState } from "react";
import { adminApi, sendPaymentLink, sendTenantOnboardingLink, updateTenantFlags, updateTenantHoraires, updateTenantParams } from "../../lib/adminApi";
import { deriveHorairesText, normalizeBookingRules } from "../../lib/bookingUtils.js";
import {
  buildTransferConfigSignature,
  isTransferConfigConfirmed,
  normalizeFrenchPhone,
  parseTransferCases,
  parseTransferHours,
  sanitizePhoneInput,
} from "../../lib/transferConfig.js";

const ConfirmDialog = lazy(() => import("./ConfirmDialog"));

const TRANSFER_CASE_LABELS = {
  urgent: "Urgence medicale",
  unhappy: "Patient mecontent / situation sensible",
  complex: "Demande administrative complexe",
  insists: "Le patient insiste pour parler a quelqu'un",
  other: "Autre",
};

const TRANSFER_DAY_ORDER = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"];

function isValidFrenchPhone(value) {
  return /^\+33\d{9}$/.test(normalizeFrenchPhone(value));
}

function normalizeTenantPhoneParams(input) {
  const next = { ...(input || {}) };
  for (const key of ["phone_number", "transfer_number", "transfer_assistant_phone", "transfer_practitioner_phone"]) {
    const raw = next[key];
    if (raw == null || raw === "") continue;
    next[key] = normalizeFrenchPhone(raw);
  }
  return next;
}

function buildTransferConfirmationText({ cabinetPhone, assistantPhone, practitionerPhone }) {
  const cabinet = cabinetPhone || "numero du cabinet non renseigne";
  const assistant = assistantPhone || cabinet;
  if (practitionerPhone) {
    return `Validation enregistree : lorsqu'un appel necessitera une intervention humaine, l'assistante redirigera les appels recus au ${cabinet} vers ${assistant}, et vers ${practitionerPhone} si le patient demande a parler au medecin.`;
  }
  return `Validation enregistree : lorsqu'un appel necessitera une intervention humaine, l'assistante redirigera les appels recus au ${cabinet} vers ${assistant}.`;
}

function formatTransferHoursSummary(value) {
  const hours = parseTransferHours(value);
  const lines = TRANSFER_DAY_ORDER
    .map((day) => {
      const slot = hours?.[day];
      if (!slot || !slot.enabled) return null;
      return `${day} ${slot.from || "--:--"}-${slot.to || "--:--"}`;
    })
    .filter(Boolean);
  return lines.length ? lines.join(" | ") : "Aucune plage definie";
}

export default function AdminTenantActionsTab({ tenantId, tenant, onSaved, onDeleted, theme }) {
  const C = theme;
  const [flags, setFlags] = useState(tenant?.flags || {});
  const [params, setParams] = useState(tenant?.params || {});
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState(null);
  const [transferJustConfirmed, setTransferJustConfirmed] = useState(false);
  const [paymentLinkLoading, setPaymentLinkLoading] = useState(false);
  const [paymentLinkUrl, setPaymentLinkUrl] = useState("");
  const [paymentLinkEmail, setPaymentLinkEmail] = useState("");
  const [showOnboardingModal, setShowOnboardingModal] = useState(false);
  const [onboardingEmail, setOnboardingEmail] = useState("");
  const [onboardingLoading, setOnboardingLoading] = useState(false);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [deleteName, setDeleteName] = useState("");
  const [deletePhrase, setDeletePhrase] = useState("");
  const [deleteLoading, setDeleteLoading] = useState(false);

  useEffect(() => {
    setFlags(tenant?.flags || {});
    setParams(normalizeTenantPhoneParams(tenant?.params || {}));
    setOnboardingEmail(tenant?.contact_email || tenant?.params?.contact_email || tenant?.params?.billing_email || "");
  }, [tenant]);

  const FLAG_KEYS = ["ENABLE_LLM_ASSIST_START", "ENABLE_ANTI_LOOP", "ENABLE_TRANSFER", "ENABLE_BOOKING", "ENABLE_FAQ"];
  const PARAM_FIELDS = [
    { key: "calendar_id", label: "Agenda Google", placeholder: "test@group.calendar.google.com", mono: true },
    { key: "phone_number", label: "Numero du cabinet", placeholder: "+33123456789", mono: true },
    { key: "timezone", label: "Fuseau horaire", placeholder: "Europe/Paris", mono: true },
    { key: "assistant_name", label: "Nom de l'assistante IA", placeholder: "sophie", mono: false },
  ];

  const bookingRules = normalizeBookingRules(params);
  const horairesPreview = deriveHorairesText(bookingRules);
  const mirrorGoogleBookings = String(params.mirror_google_bookings_to_internal || "").toLowerCase() === "true";
  const isGoogleProvider = (params.calendar_provider || "none") === "google";
  const transferLiveEnabled = String(params.transfer_live_enabled || "").toLowerCase() === "true";
  const transferCallbackEnabled = String(params.transfer_callback_enabled || "").toLowerCase() !== "false";
  const normalizedPractitionerPhone = normalizeFrenchPhone(params.transfer_practitioner_phone || "");
  const assistantSourceRaw = params.transfer_number || params.phone_number || "";
  const assistantInputValue = params.transfer_number || "";
  const effectiveAssistantPhone = normalizeFrenchPhone(assistantSourceRaw);
  const cabinetPhone = normalizeFrenchPhone(params.phone_number || "");
  const assistantPhoneInvalid = Boolean(assistantSourceRaw) && !isValidFrenchPhone(assistantSourceRaw);
  const practitionerPhoneInvalid = Boolean(params.transfer_practitioner_phone) && !isValidFrenchPhone(params.transfer_practitioner_phone);
  const hasTransferTarget = Boolean(effectiveAssistantPhone || normalizedPractitionerPhone);
  const transferIsConfirmed = isTransferConfigConfirmed(params);
  const transferConfirmedDisplay = transferIsConfirmed || transferJustConfirmed;
  const transferConfirmationText = transferConfirmedDisplay
    ? buildTransferConfirmationText({
        cabinetPhone,
        assistantPhone: effectiveAssistantPhone,
        practitionerPhone: normalizedPractitionerPhone,
      })
    : "";
  const transferConfirmedAt = String(params.transfer_config_confirmed_at || "");
  const transferConfirmationDateLabel = transferConfirmedAt ? new Date(transferConfirmedAt).toLocaleString("fr-FR") : "";
  const transferValidationMessage = assistantPhoneInvalid
    ? "Le numero assistante repris automatiquement doit etre au format +33XXXXXXXXX."
    : practitionerPhoneInvalid
      ? "Le numero praticien doit etre au format +33XXXXXXXXX."
      : !hasTransferTarget && (transferLiveEnabled || transferCallbackEnabled)
        ? "Ajoute au moins un numero humain valide pour confirmer le transfert."
        : null;
  const transferStatusTone = transferValidationMessage ? C.danger : transferIsConfirmed ? C.accent : C.warning;
  const clientTransferCases = parseTransferCases(params.transfer_cases);
  const clientTransferCasesSummary = clientTransferCases.length
    ? clientTransferCases.map((item) => TRANSFER_CASE_LABELS[item] || item).join(" | ")
    : "Uniquement si le patient demande explicitement a parler a quelqu'un";
  const clientTransferHoursSummary = formatTransferHoursSummary(params.transfer_hours);
  const clientTransferAlwaysUrgent = String(params.transfer_always_urgent || "").toLowerCase() === "true";
  const clientTransferNoConsultation = String(params.transfer_no_consultation || "").toLowerCase() === "true";
  const normalizedTenantName = (tenant?.name || "").trim();
  const isSystemTenant = normalizedTenantName.toUpperCase() === "DEFAULT" || Number(tenantId) === 1;
  const isInactiveTenant = (tenant?.status || "").toLowerCase() === "inactive";
  const deleteNameMatch = deleteName.trim().toLowerCase() === normalizedTenantName.toLowerCase();
  const deletePhraseMatch = deletePhrase.trim().toUpperCase() === "SUPPRIMER";
  const canDelete = !isSystemTenant && !isInactiveTenant;
  const canConfirmDelete = canDelete && deleteNameMatch && deletePhraseMatch;
  const onboardingEligible = !((tenant?.params?.vapi_assistant_id || "").trim());

  const setPhoneParam = useCallback((key, value, finalize = false) => {
    setTransferJustConfirmed(false);
    setParams((current) => ({
      ...current,
      [key]: finalize ? normalizeFrenchPhone(value) : sanitizePhoneInput(value),
    }));
  }, []);

  const saveFlags = async () => {
    setSaving(true);
    setMsg(null);
    try {
      await updateTenantFlags(tenantId, flags);
      setMsg({ type: "success", text: "Flags sauvegardes ✓" });
      onSaved?.();
    } catch (e) {
      setMsg({ type: "error", text: e?.message || "Erreur" });
    } finally {
      setSaving(false);
    }
  };

  const saveParams = async (successText = "Params sauvegardes ✓", options = {}) => {
    const { confirmTransfer = false } = options;
    setSaving(true);
    setMsg(null);
    try {
      const nextParams = normalizeTenantPhoneParams(params);
      nextParams.transfer_assistant_phone = "";
      const nextSignature = buildTransferConfigSignature(nextParams);
      if (confirmTransfer) {
        nextParams.transfer_config_confirmed_signature = nextSignature;
        nextParams.transfer_config_confirmed_at = new Date().toISOString();
      } else if (
        String(nextParams.transfer_config_confirmed_signature || "") &&
        String(nextParams.transfer_config_confirmed_signature || "") !== nextSignature
      ) {
        nextParams.transfer_config_confirmed_signature = "";
        nextParams.transfer_config_confirmed_at = "";
      }
      await updateTenantParams(tenantId, nextParams);
      setParams(nextParams);
      setMsg({ type: "success", text: successText });
      onSaved?.();
      return nextParams;
    } catch (e) {
      setMsg({ type: "error", text: e?.message || "Erreur" });
      return null;
    } finally {
      setSaving(false);
    }
  };

  const confirmTransferConfiguration = async () => {
    setTransferJustConfirmed(true);
    const saved = await saveParams("Transfert humain confirme ✓", { confirmTransfer: true });
    if (!saved) {
      setTransferJustConfirmed(false);
    }
  };

  const saveHoraires = async () => {
    setSaving(true);
    setMsg(null);
    try {
      await updateTenantHoraires(tenantId, bookingRules);
      setParams((current) => ({ ...current, horaires: horairesPreview }));
      setMsg({ type: "success", text: `Horaires sauvegardes ✓ ${horairesPreview}` });
      onSaved?.();
    } catch (e) {
      setMsg({ type: "error", text: e?.message || "Erreur horaires" });
    } finally {
      setSaving(false);
    }
  };

  const handleSendPaymentLink = async () => {
    if (!tenantId) return;
    setPaymentLinkLoading(true);
    setMsg(null);
    try {
      const res = await sendPaymentLink(tenantId);
      setPaymentLinkUrl(res?.checkout_url || "");
      setPaymentLinkEmail(res?.email || "");
      setMsg({ type: "success", text: `Lien envoye a ${res?.email || "ce client"} ✓` });
      onSaved?.();
    } catch (e) {
      setMsg({ type: "error", text: e?.message || "Erreur lors de l'envoi du lien de paiement" });
    } finally {
      setPaymentLinkLoading(false);
    }
  };

  const copyPaymentLink = async () => {
    if (!paymentLinkUrl) return;
    try {
      await navigator.clipboard.writeText(paymentLinkUrl);
      setMsg({ type: "success", text: "Lien copie ✓" });
    } catch {
      setMsg({ type: "error", text: "Impossible de copier le lien" });
    }
  };

  const handleSendOnboardingLink = async () => {
    if (!tenantId || !onboardingEmail.trim()) {
      setMsg({ type: "error", text: "Email requis pour envoyer le lien onboarding" });
      return;
    }
    setOnboardingLoading(true);
    setMsg(null);
    try {
      const res = await sendTenantOnboardingLink(tenantId, {
        email: onboardingEmail.trim(),
        name: tenant?.name || "",
      });
      setMsg({ type: "success", text: `Lien envoye a ${res?.email || onboardingEmail.trim()} ✓` });
      setShowOnboardingModal(false);
      onSaved?.();
    } catch (e) {
      setMsg({ type: "error", text: e?.message || "Erreur lors de l'envoi du lien onboarding" });
    } finally {
      setOnboardingLoading(false);
    }
  };

  const handleDeleteTenant = async () => {
    if (!canConfirmDelete) return;
    setDeleteLoading(true);
    setMsg(null);
    try {
      await adminApi.deleteTenant(tenantId, {
        tenant_name: normalizedTenantName,
        confirmation_phrase: deletePhrase.trim(),
      });
      setMsg({ type: "success", text: "Compte client desactive ✓" });
      setDeleteModalOpen(false);
      setDeleteName("");
      setDeletePhrase("");
      onDeleted?.();
    } catch (e) {
      setMsg({ type: "error", text: e?.message || "Erreur lors de la suppression du client" });
    } finally {
      setDeleteLoading(false);
    }
  };

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, maxWidth: 900 }}>
      <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 16, padding: 22 }}>
        <div style={{ fontSize: 14, fontWeight: 700, color: C.text, marginBottom: 16 }}>Feature Flags</div>
        {FLAG_KEYS.map((key) => (
          <div key={key} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
            <span style={{ fontSize: 13, color: C.muted, fontFamily: "monospace" }}>{key}</span>
            <div
              role="button"
              tabIndex={0}
              onClick={() => setFlags((current) => ({ ...current, [key]: !current[key] }))}
              onKeyDown={(e) => e.key === "Enter" && setFlags((current) => ({ ...current, [key]: !current[key] }))}
              style={{
                width: 40,
                height: 22,
                borderRadius: 11,
                cursor: "pointer",
                background: flags[key] ? C.accent : C.border,
                position: "relative",
                transition: "background 0.2s",
              }}
            >
              <div
                style={{
                  width: 16,
                  height: 16,
                  borderRadius: "50%",
                  background: C.text,
                  position: "absolute",
                  top: 3,
                  left: flags[key] ? 21 : 3,
                  transition: "left 0.2s",
                }}
              />
            </div>
          </div>
        ))}
        <button
          type="button"
          onClick={saveFlags}
          disabled={saving}
          style={{
            marginTop: 8,
            width: "100%",
            padding: 10,
            borderRadius: 10,
            background: `linear-gradient(135deg,${C.accent},${C.accentDim})`,
            border: "none",
            color: C.bg,
            fontSize: 13,
            fontWeight: 700,
            cursor: "pointer",
            fontFamily: "inherit",
          }}
        >
          {saving ? "…" : "Sauvegarder les flags"}
        </button>
      </div>

      <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 16, padding: 22 }}>
        <div style={{ fontSize: 14, fontWeight: 700, color: C.text, marginBottom: 16 }}>Parametres</div>
        {PARAM_FIELDS.map((field) => (
          <div key={field.key} style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 11, color: C.muted, marginBottom: 4, fontFamily: "monospace", textTransform: "uppercase", letterSpacing: 0.5 }}>{field.label}</div>
            <input
              value={params[field.key] || ""}
              placeholder={field.placeholder}
              inputMode={field.key === "phone_number" || field.key === "transfer_number" ? "tel" : undefined}
              onChange={(e) => (
                field.key === "phone_number" || field.key === "transfer_number"
                  ? setPhoneParam(field.key, e.target.value)
                  : setParams((current) => ({ ...current, [field.key]: e.target.value }))
              )}
              onBlur={(e) => {
                if (field.key === "phone_number" || field.key === "transfer_number") {
                  setPhoneParam(field.key, e.target.value, true);
                }
              }}
              style={{
                width: "100%",
                background: C.surface,
                border: `1px solid ${C.border}`,
                borderRadius: 8,
                padding: "8px 12px",
                color: C.text,
                fontSize: 13,
                fontFamily: field.mono ? "monospace" : "inherit",
                outline: "none",
              }}
            />
          </div>
        ))}

        <div style={{ marginTop: 24, borderTop: `1px solid ${C.border}`, paddingTop: 16 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: C.blue, marginBottom: 12 }}>📲 Transfert humain hybride</div>
          <div style={{ fontSize: 12, color: C.muted, marginBottom: 12 }}>
            `Numero du cabinet` = ligne principale appelee par le patient. `Assistante physique` = personne vers qui l&apos;appel est transfere par defaut. `Praticien` = destination reservee aux demandes d&apos;avis medical.
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 12 }}>
            <div>
              <div style={{ fontSize: 11, color: C.muted, marginBottom: 4, display: "block" }}>Numero de l&apos;assistante physique</div>
              <input
                value={assistantInputValue}
                placeholder="+33123456789"
                inputMode="tel"
                onChange={(e) => setPhoneParam("transfer_number", e.target.value)}
                onBlur={(e) => setPhoneParam("transfer_number", e.target.value, true)}
                style={{
                  width: "100%",
                  background: C.surface,
                  border: `1px solid ${assistantPhoneInvalid ? C.danger : C.border}`,
                  borderRadius: 8,
                  padding: "8px 12px",
                  color: C.text,
                  fontSize: 13,
                  fontFamily: "monospace",
                  outline: "none",
                }}
              />
              <div style={{ marginTop: 6, fontSize: 11, color: assistantPhoneInvalid ? C.danger : C.muted }}>
                {assistantPhoneInvalid
                  ? "Format attendu : +33XXXXXXXXX."
                  : params.transfer_number
                    ? "Ce numero sera utilise pour transferer vers l'assistante physique."
                    : params.phone_number
                      ? "Laisse vide : le numero du cabinet sera utilise automatiquement."
                      : "Renseigne d'abord le numero du cabinet, ou saisis ici le numero direct de l'assistante physique."}
              </div>
            </div>
            <div>
              <div style={{ fontSize: 11, color: C.muted, marginBottom: 4, display: "block" }}>Numero du praticien</div>
              <input
                value={params.transfer_practitioner_phone || ""}
                placeholder="+33123456789"
                inputMode="tel"
                onChange={(e) => setPhoneParam("transfer_practitioner_phone", e.target.value)}
                onBlur={(e) => setPhoneParam("transfer_practitioner_phone", e.target.value, true)}
                style={{
                  width: "100%",
                  background: C.surface,
                  border: `1px solid ${practitionerPhoneInvalid ? C.danger : C.border}`,
                  borderRadius: 8,
                  padding: "8px 12px",
                  color: C.text,
                  fontSize: 13,
                  fontFamily: "monospace",
                  outline: "none",
                }}
              />
              <div style={{ marginTop: 6, fontSize: 11, color: practitionerPhoneInvalid ? C.danger : C.muted }}>
                {practitionerPhoneInvalid ? "Format attendu : +33XXXXXXXXX" : "Utilise uniquement si le patient demande a parler au medecin."}
              </div>
            </div>
          </div>

          <label style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10, cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={transferLiveEnabled}
              onChange={(e) => {
                setTransferJustConfirmed(false);
                setParams((current) => ({ ...current, transfer_live_enabled: e.target.checked ? "true" : "false" }));
              }}
            />
            <span style={{ fontSize: 12, color: C.text }}>Autoriser le live transfer vocal quand un numero humain est configure</span>
          </label>

          <label style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12, cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={transferCallbackEnabled}
              onChange={(e) => {
                setTransferJustConfirmed(false);
                setParams((current) => ({ ...current, transfer_callback_enabled: e.target.checked ? "true" : "false" }));
              }}
            />
            <span style={{ fontSize: 12, color: C.text }}>Autoriser le fallback en rappel quand le direct n&apos;aboutit pas</span>
          </label>

          <div
            style={{
              padding: "10px 12px",
              borderRadius: 10,
              background: "rgba(91,168,255,0.08)",
              border: `1px solid ${C.blue}33`,
              fontSize: 12,
              color: C.text,
            }}
          >
            <div style={{ color: C.blue, fontWeight: 700, marginBottom: 4 }}>Mode effectif</div>
            <div>
              {transferLiveEnabled && transferCallbackEnabled
                ? "Live transfer puis rappel si echec."
                : transferLiveEnabled
                  ? "Live transfer uniquement."
                  : transferCallbackEnabled
                    ? "Rappel uniquement."
                    : "Transfert hybride desactive."}
            </div>
            <div style={{ color: C.muted, marginTop: 6 }}>
              Ligne du cabinet : {cabinetPhone || "non renseigne"} · Assistante physique : {effectiveAssistantPhone || "non renseigne"} · Praticien : {normalizedPractitionerPhone || "non renseigne"}
            </div>
            {transferValidationMessage ? (
              <div style={{ color: C.danger, marginTop: 8 }}>{transferValidationMessage}</div>
            ) : (
              <div style={{ color: transferStatusTone, marginTop: 8, fontWeight: 700 }}>
                {transferConfirmedDisplay
                  ? "Configuration confirmee."
                  : hasTransferTarget
                    ? "Configuration modifiee : confirmation requise."
                    : "Complete la configuration avant confirmation."}
              </div>
            )}
          </div>

          <div
            style={{
              marginTop: 12,
              padding: "10px 12px",
              borderRadius: 10,
              background: "rgba(255,255,255,0.03)",
              border: `1px solid ${C.border}`,
              fontSize: 12,
              color: C.text,
            }}
          >
            <div style={{ color: C.accent, fontWeight: 700, marginBottom: 6 }}>Preferences definies cote client</div>
            <div style={{ color: C.muted }}>Quand transferer : <span style={{ color: C.text }}>{clientTransferCasesSummary}</span></div>
            <div style={{ color: C.muted, marginTop: 4 }}>Horaires : <span style={{ color: C.text }}>{clientTransferHoursSummary}</span></div>
            <div style={{ color: C.muted, marginTop: 4 }}>
              Regles :{" "}
              <span style={{ color: C.text }}>
                {clientTransferAlwaysUrgent ? "Urgences meme hors horaires" : "Urgences seulement sur les horaires"}{" · "}
                {clientTransferNoConsultation ? "Pas de transfert pendant les consultations" : "Transfert possible pendant les consultations"}
              </span>
            </div>
          </div>

          {transferConfirmedDisplay ? (
            <div
              style={{
                marginTop: 14,
                padding: "12px 14px",
                borderRadius: 12,
                background: "rgba(0,229,160,0.1)",
                border: `1px solid ${C.accent}55`,
                color: C.text,
                fontSize: 12,
                lineHeight: 1.55,
              }}
            >
              <div style={{ color: C.accent, fontWeight: 800, marginBottom: 6 }}>✓ Configuration validee</div>
              <div>{transferConfirmationText}</div>
              {transferIsConfirmed && transferConfirmationDateLabel ? (
                <div style={{ color: C.muted, marginTop: 6 }}>Derniere validation : {transferConfirmationDateLabel}</div>
              ) : null}
            </div>
          ) : null}

          <button
            type="button"
            onClick={confirmTransferConfiguration}
            disabled={saving || Boolean(transferValidationMessage) || transferConfirmedDisplay}
            style={{
              marginTop: 14,
              width: "100%",
              padding: "12px 14px",
              borderRadius: 12,
              background: transferConfirmedDisplay ? `linear-gradient(135deg,${C.accent},${C.accentDim})` : `linear-gradient(135deg,${C.blue},#7fbcff)`,
              border: "none",
              color: C.bg,
              fontSize: 14,
              fontWeight: 800,
              cursor: saving || transferValidationMessage || transferConfirmedDisplay ? "not-allowed" : "pointer",
              fontFamily: "inherit",
              opacity: saving || transferValidationMessage || transferConfirmedDisplay ? 0.7 : 1,
              boxShadow: transferConfirmedDisplay ? "0 10px 24px rgba(0,229,160,0.22)" : "0 10px 24px rgba(91,168,255,0.22)",
            }}
          >
            {saving ? "…" : transferConfirmedDisplay ? "Transfert humain confirme" : "Confirmer le transfert humain"}
          </button>
        </div>

        <div style={{ marginTop: 24, borderTop: `1px solid ${C.border}`, paddingTop: 16 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: C.accent, marginBottom: 12 }}>📅 Agenda & Booking</div>

          <div style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 11, color: C.muted, marginBottom: 4, display: "block" }}>Provider agenda</div>
            <select
              value={params.calendar_provider || "none"}
              onChange={(e) => setParams((current) => ({ ...current, calendar_provider: e.target.value }))}
              style={{
                width: "100%",
                background: C.surface,
                border: `1px solid ${C.border}`,
                borderRadius: 8,
                padding: "8px 12px",
                color: C.text,
                fontSize: 13,
                fontFamily: "inherit",
                outline: "none",
              }}
            >
              <option value="none">Aucun (SQLite fallback)</option>
              <option value="google">Google Calendar</option>
            </select>
          </div>

          <label style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14, cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={mirrorGoogleBookings}
              disabled={!isGoogleProvider}
              onChange={(e) =>
                setParams((current) => ({
                  ...current,
                  mirror_google_bookings_to_internal: e.target.checked ? "true" : "false",
                }))}
            />
            <span style={{ fontSize: 12, color: isGoogleProvider ? C.text : C.muted }}>
              Conserver un miroir interne UWI quand le RDV est cree dans Google Calendar
            </span>
          </label>
          {!isGoogleProvider ? (
            <div style={{ fontSize: 11, color: C.muted, marginTop: -6, marginBottom: 14 }}>
              Active d'abord `Google Calendar` comme provider pour utiliser le mode double ecriture.
            </div>
          ) : null}

          <div style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 11, color: C.muted, marginBottom: 4, display: "block" }}>Duree RDV (minutes)</div>
            <input
              type="number"
              min={5}
              max={120}
              step={5}
              value={params.booking_duration_minutes ?? 15}
              onChange={(e) => setParams((current) => ({ ...current, booking_duration_minutes: parseInt(e.target.value, 10) || 15 }))}
              style={{
                width: "100%",
                background: C.surface,
                border: `1px solid ${C.border}`,
                borderRadius: 8,
                padding: "8px 12px",
                color: C.text,
                fontSize: 13,
                fontFamily: "inherit",
                outline: "none",
              }}
            />
          </div>

          <div style={{ display: "flex", gap: 12, marginBottom: 12 }}>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 11, color: C.muted, marginBottom: 4, display: "block" }}>Heure debut</div>
              <input
                type="number"
                min={6}
                max={12}
                value={params.booking_start_hour ?? 9}
                onChange={(e) => setParams((current) => ({ ...current, booking_start_hour: parseInt(e.target.value, 10) || 9 }))}
                style={{
                  width: "100%",
                  background: C.surface,
                  border: `1px solid ${C.border}`,
                  borderRadius: 8,
                  padding: "8px 12px",
                  color: C.text,
                  fontSize: 13,
                  fontFamily: "inherit",
                  outline: "none",
                }}
              />
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 11, color: C.muted, marginBottom: 4, display: "block" }}>Heure fin</div>
              <input
                type="number"
                min={14}
                max={22}
                value={params.booking_end_hour ?? 18}
                onChange={(e) => setParams((current) => ({ ...current, booking_end_hour: parseInt(e.target.value, 10) || 18 }))}
                style={{
                  width: "100%",
                  background: C.surface,
                  border: `1px solid ${C.border}`,
                  borderRadius: 8,
                  padding: "8px 12px",
                  color: C.text,
                  fontSize: 13,
                  fontFamily: "inherit",
                  outline: "none",
                }}
              />
            </div>
          </div>

          <div style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 11, color: C.muted, marginBottom: 4, display: "block" }}>Buffer entre RDV (minutes)</div>
            <input
              type="number"
              min={0}
              max={30}
              step={5}
              value={params.booking_buffer_minutes ?? 0}
              onChange={(e) => setParams((current) => ({ ...current, booking_buffer_minutes: parseInt(e.target.value, 10) || 0 }))}
              style={{
                width: "100%",
                background: C.surface,
                border: `1px solid ${C.border}`,
                borderRadius: 8,
                padding: "8px 12px",
                color: C.text,
                fontSize: 13,
                fontFamily: "inherit",
                outline: "none",
              }}
            />
          </div>

          <div style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 11, color: C.muted, marginBottom: 8, display: "block" }}>Jours de travail</div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {[
                ["L", 0],
                ["M", 1],
                ["Me", 2],
                ["J", 3],
                ["V", 4],
                ["S", 5],
                ["D", 6],
              ].map(([label, day]) => {
                const days = Array.isArray(params.booking_days) ? params.booking_days : [0, 1, 2, 3, 4];
                const active = days.includes(day);
                return (
                  <button
                    key={day}
                    type="button"
                    onClick={() => {
                      const next = active ? days.filter((item) => item !== day) : [...days, day].sort((a, b) => a - b);
                      setParams((current) => ({ ...current, booking_days: next }));
                    }}
                    style={{
                      width: 36,
                      height: 36,
                      borderRadius: 8,
                      fontSize: 12,
                      fontWeight: 500,
                      border: `1px solid ${active ? C.accent : C.border}`,
                      background: active ? C.accent : C.surface,
                      color: active ? C.bg : C.muted,
                      cursor: "pointer",
                      fontFamily: "inherit",
                      transition: "all 0.15s",
                    }}
                  >
                    {label}
                  </button>
                );
              })}
            </div>
          </div>

          <div
            style={{
              marginBottom: 12,
              padding: "10px 12px",
              borderRadius: 10,
              background: "rgba(0,229,160,0.08)",
              border: "1px solid rgba(0,229,160,0.18)",
              fontSize: 12,
              color: C.text,
            }}
          >
            <div style={{ color: C.accent, fontWeight: 700, marginBottom: 4 }}>Apercu live</div>
            <div>📅 {horairesPreview}</div>
            <div style={{ color: C.muted, marginTop: 4 }}>
              RDV de {bookingRules.booking_duration_minutes} min, buffer {bookingRules.booking_buffer_minutes} min
            </div>
          </div>

          <button
            type="button"
            onClick={saveHoraires}
            disabled={saving}
            style={{
              marginBottom: 12,
              width: "100%",
              padding: 10,
              borderRadius: 10,
              background: `linear-gradient(135deg,${C.accent},${C.accentDim})`,
              border: "none",
              color: C.bg,
              fontSize: 13,
              fontWeight: 700,
              cursor: "pointer",
              fontFamily: "inherit",
              opacity: saving ? 0.8 : 1,
            }}
          >
            {saving ? "…" : "Sauvegarder les horaires"}
          </button>
        </div>

        <button
          type="button"
          onClick={() => saveParams()}
          disabled={saving}
          style={{
            marginTop: 4,
            width: "100%",
            padding: 10,
            borderRadius: 10,
            background: C.surface,
            border: `1px solid ${C.border}`,
            color: C.text,
            fontSize: 13,
            fontWeight: 700,
            cursor: "pointer",
            fontFamily: "inherit",
          }}
        >
          {saving ? "…" : "Sauvegarder les autres parametres"}
        </button>

        <div style={{ marginTop: 16, paddingTop: 16, borderTop: `1px solid ${C.border}` }}>
          {onboardingEligible ? (
            <>
              <div style={{ fontSize: 13, fontWeight: 700, color: C.text, marginBottom: 8 }}>Onboarding client</div>
              <div style={{ fontSize: 12, color: C.muted, marginBottom: 10 }}>
                Envoie au client un lien vers le wizard pour qu&apos;il configure lui-meme son assistant.
              </div>
              <button
                type="button"
                onClick={() => setShowOnboardingModal(true)}
                style={{
                  width: "100%",
                  padding: 10,
                  borderRadius: 10,
                  background: "rgba(91,168,255,0.12)",
                  border: `1px solid ${C.blue}55`,
                  color: C.blue,
                  fontSize: 13,
                  fontWeight: 700,
                  cursor: "pointer",
                  fontFamily: "inherit",
                  marginBottom: 16,
                }}
              >
                📧 Envoyer lien onboarding
              </button>
            </>
          ) : null}

          <div style={{ fontSize: 13, fontWeight: 700, color: C.text, marginBottom: 8 }}>Paiement Stripe</div>
          <div style={{ fontSize: 12, color: C.muted, marginBottom: 10 }}>
            Envoie au client un lien Stripe pour ajouter sa carte pendant ou apres les 30 jours d&apos;essai.
          </div>
          <button
            type="button"
            onClick={handleSendPaymentLink}
            disabled={paymentLinkLoading}
            style={{
              width: "100%",
              padding: 10,
              borderRadius: 10,
              background: `linear-gradient(135deg,${C.accent},${C.accentDim})`,
              border: "none",
              color: C.bg,
              fontSize: 13,
              fontWeight: 700,
              cursor: "pointer",
              fontFamily: "inherit",
              opacity: paymentLinkLoading ? 0.7 : 1,
            }}
          >
            {paymentLinkLoading ? "Envoi..." : "Envoyer lien de paiement"}
          </button>
          {paymentLinkUrl ? (
            <div style={{ marginTop: 10, display: "grid", gap: 8 }}>
              <input
                readOnly
                value={paymentLinkUrl}
                style={{
                  width: "100%",
                  background: C.surface,
                  border: `1px solid ${C.border}`,
                  borderRadius: 8,
                  padding: "8px 12px",
                  color: C.text,
                  fontSize: 12,
                  fontFamily: "monospace",
                  outline: "none",
                }}
              />
              <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
                <button
                  type="button"
                  onClick={copyPaymentLink}
                  style={{
                    padding: "8px 12px",
                    borderRadius: 8,
                    background: C.surface,
                    border: `1px solid ${C.border}`,
                    color: C.text,
                    fontSize: 12,
                    fontWeight: 700,
                    cursor: "pointer",
                    fontFamily: "inherit",
                  }}
                >
                  Copier le lien
                </button>
                <a href={paymentLinkUrl} target="_blank" rel="noopener noreferrer" style={{ color: C.blue, fontSize: 12 }}>
                  Ouvrir le lien
                </a>
                {paymentLinkEmail ? <span style={{ fontSize: 12, color: C.muted }}>Envoye a {paymentLinkEmail}</span> : null}
              </div>
            </div>
          ) : null}
        </div>
      </div>

      <div
        style={{
          gridColumn: "1/3",
          background: "rgba(255,107,107,0.08)",
          border: `1px solid ${C.danger}40`,
          borderRadius: 16,
          padding: 22,
        }}
      >
        <div style={{ fontSize: 14, fontWeight: 800, color: "#FFD2D2", marginBottom: 10 }}>Zone dangereuse</div>
        <div style={{ fontSize: 12, color: C.text, marginBottom: 8 }}>
          Cette action effectue un soft delete : le compte client passe en <strong>inactive</strong> mais l&apos;historique reste conserve.
        </div>
        <div style={{ fontSize: 12, color: C.muted, marginBottom: 16 }}>
          Elle est reservee aux cas de doublon, erreur de provisioning ou compte a fermer. Les comptes systeme ne sont jamais supprimables.
        </div>
        {!canDelete ? (
          <div style={{ fontSize: 12, color: C.warning }}>
            {isSystemTenant
              ? "Suppression desactivee : ce compte est protege (systeme / DEFAULT)."
              : "Suppression desactivee : ce client est deja inactif."}
          </div>
        ) : (
          <button
            type="button"
            onClick={() => setDeleteModalOpen(true)}
            style={{
              padding: "10px 14px",
              borderRadius: 10,
              border: `1px solid ${C.danger}55`,
              background: "rgba(255,107,107,0.12)",
              color: "#FFD2D2",
              fontSize: 13,
              fontWeight: 800,
              cursor: "pointer",
              fontFamily: "inherit",
            }}
          >
            Supprimer le compte client
          </button>
        )}
      </div>

      {msg ? (
        <div
          style={{
            gridColumn: "1/3",
            background: msg.type === "success" ? "rgba(0,229,160,0.08)" : "rgba(255,107,107,0.08)",
            border: `1px solid ${msg.type === "success" ? `${C.accent}40` : `${C.danger}40`}`,
            borderRadius: 10,
            padding: "12px 16px",
            fontSize: 13,
            color: msg.type === "success" ? C.accent : C.danger,
          }}
        >
          {msg.text}
        </div>
      ) : null}

      {deleteModalOpen ? (
        <Suspense fallback={null}>
          <ConfirmDialog
            open={deleteModalOpen}
            title="Supprimer le compte client"
            message={
              <div style={{ display: "grid", gap: 10 }}>
                <p>
                  Pour continuer, tapez le nom exact du client : <strong>{normalizedTenantName || "(nom inconnu)"}</strong>
                </p>
                <input
                  type="text"
                  value={deleteName}
                  onChange={(e) => setDeleteName(e.target.value)}
                  placeholder="Nom exact du client"
                  style={{ width: "100%", borderRadius: 8, border: "1px solid #CBD5E1", padding: "10px 12px", fontSize: 13 }}
                />
                {deleteName && !deleteNameMatch ? <p style={{ color: "#DC2626", fontSize: 12 }}>Le nom du client ne correspond pas.</p> : null}
                <p>Tapez ensuite <strong>SUPPRIMER</strong> pour confirmer cette action dangereuse.</p>
                <input
                  type="text"
                  value={deletePhrase}
                  onChange={(e) => setDeletePhrase(e.target.value)}
                  placeholder="SUPPRIMER"
                  style={{ width: "100%", borderRadius: 8, border: "1px solid #CBD5E1", padding: "10px 12px", fontSize: 13 }}
                />
                {deletePhrase && !deletePhraseMatch ? <p style={{ color: "#DC2626", fontSize: 12 }}>Le mot de confirmation est incorrect.</p> : null}
              </div>
            }
            confirmLabel="Supprimer"
            cancelLabel="Annuler"
            danger
            loading={deleteLoading}
            confirmDisabled={!canConfirmDelete}
            onConfirm={handleDeleteTenant}
            onCancel={() => {
              setDeleteModalOpen(false);
              setDeleteName("");
              setDeletePhrase("");
            }}
          />
        </Suspense>
      ) : null}

      {showOnboardingModal ? (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(3, 10, 18, 0.75)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
            padding: 20,
          }}
          onClick={(e) => {
            if (e.target === e.currentTarget) setShowOnboardingModal(false);
          }}
        >
          <div style={{ width: "100%", maxWidth: 460, background: C.surface, border: `1px solid ${C.border}`, borderRadius: 18, padding: 22 }}>
            <div style={{ fontSize: 16, fontWeight: 800, color: C.text, marginBottom: 8 }}>Envoyer lien onboarding</div>
            <div style={{ fontSize: 12, color: C.muted, marginBottom: 16 }}>
              Le client recevra un lien vers `/creer-assistante` pour finaliser lui-meme la configuration.
            </div>
            <div style={{ fontSize: 11, color: C.muted, marginBottom: 6, textTransform: "uppercase", letterSpacing: 0.6 }}>
              Email du client
            </div>
            <input
              value={onboardingEmail}
              onChange={(e) => setOnboardingEmail(e.target.value)}
              placeholder="client@cabinet.fr"
              style={{
                width: "100%",
                background: C.card,
                border: `1px solid ${C.border}`,
                borderRadius: 10,
                padding: "10px 12px",
                color: C.text,
                fontSize: 13,
                fontFamily: "inherit",
                outline: "none",
              }}
            />
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 18 }}>
              <button
                type="button"
                onClick={() => setShowOnboardingModal(false)}
                style={{ padding: "9px 14px", borderRadius: 9, border: `1px solid ${C.border}`, background: "transparent", color: C.muted, cursor: "pointer", fontFamily: "inherit" }}
              >
                Annuler
              </button>
              <button
                type="button"
                onClick={handleSendOnboardingLink}
                disabled={onboardingLoading}
                style={{
                  padding: "9px 14px",
                  borderRadius: 9,
                  border: "none",
                  background: `linear-gradient(135deg,${C.accent},${C.accentDim})`,
                  color: C.bg,
                  cursor: "pointer",
                  fontWeight: 800,
                  fontFamily: "inherit",
                  opacity: onboardingLoading ? 0.7 : 1,
                }}
              >
                {onboardingLoading ? "Envoi..." : "Envoyer"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
