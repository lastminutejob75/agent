import { useState } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
import { sanitizePhoneInput } from "../../lib/transferConfig.js";
import NoteDictateButton from "../notes/NoteDictateButton.jsx";

function fieldInputClass(hasError) {
  return `rounded-xl border px-3 py-2 text-sm outline-none focus:border-[#009CA4] ${
    hasError ? "border-red-400 bg-red-50/40" : "border-[#E2E8F0]"
  }`;
}

export default function CreatePatientFromCallModal({
  open,
  loading,
  form,
  onChange,
  onClose,
  onSubmit,
  subtitleLine,
  embedded = false,
  onBack,
  phoneError = "",
  emailError = "",
  birthDateError = "",
  physicianNameError = "",
  physicianCityError = "",
  submitDisabled = false,
  showEmail = false,
  emailRequired = false,
  extendedProfile = false,
}) {
  const [noteDictError, setNoteDictError] = useState("");
  if (!open) return null;
  if (!embedded && typeof document === "undefined") return null;

  const handlePhoneChange = (event) => {
    onChange("phone", sanitizePhoneInput(event.target.value));
  };

  const footerClass = embedded
    ? "mt-5 flex items-center justify-end gap-2"
    : "sticky bottom-0 -mx-5 -mb-5 mt-5 flex items-center justify-end gap-2 border-t border-[#E2E8F0] bg-white px-5 py-3";

  const panel = (
    <div className={embedded ? "px-4 pb-4" : "flex max-h-[88dvh] w-full max-w-[560px] flex-col overflow-y-auto rounded-2xl border border-[#E2E8F0] bg-white p-5 shadow-2xl"}>
      <div className="mb-4 flex items-center justify-between">
        <h3 id="create-patient-from-call-heading" className="text-lg font-black text-[#0A1628]">
          Créer une fiche patient
        </h3>
        <button
          type="button"
          onClick={onBack || onClose}
          aria-label={embedded ? "Retour au rendez-vous" : "Fermer la modale"}
          className="rounded-full p-2 text-[#64748B] hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#009CA4] focus-visible:ring-offset-1"
        >
          <X size={16} />
        </button>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <label className="flex flex-col gap-1 text-sm font-semibold text-[#334155]">
          Nom
          <input
            value={form.lastName}
            onChange={(event) => onChange("lastName", event.target.value)}
            className={fieldInputClass(false)}
          />
        </label>
        <label className="flex flex-col gap-1 text-sm font-semibold text-[#334155]">
          Prénom
          <input
            value={form.firstName}
            onChange={(event) => onChange("firstName", event.target.value)}
            className={fieldInputClass(false)}
          />
        </label>
      </div>

      <label className="mt-3 flex flex-col gap-1 text-sm font-semibold text-[#334155]">
        Téléphone
        <input
          type="tel"
          inputMode="tel"
          autoComplete="tel"
          value={form.phone}
          onChange={handlePhoneChange}
          placeholder="06 12 34 56 78"
          aria-invalid={phoneError ? "true" : undefined}
          className={fieldInputClass(Boolean(phoneError))}
        />
        {phoneError ? (
          <span className="text-xs font-semibold text-red-600">{phoneError}</span>
        ) : (
          <span className="text-xs font-normal text-[#64748B]">Format : 06 12 34 56 78 ou +33 6 12 34 56 78</span>
        )}
      </label>

      {showEmail ? (
        <label className="mt-3 flex flex-col gap-1 text-sm font-semibold text-[#334155]">
          {emailRequired ? "E-mail" : "E-mail (facultatif)"}
          <input
            type="email"
            inputMode="email"
            autoComplete="email"
            value={form.email || ""}
            onChange={(event) => onChange("email", event.target.value)}
            placeholder="prenom@exemple.fr"
            aria-invalid={emailError ? "true" : undefined}
            className={fieldInputClass(Boolean(emailError))}
          />
          {emailError ? <span className="text-xs font-semibold text-red-600">{emailError}</span> : null}
        </label>
      ) : null}

      {extendedProfile ? (
        <>
          <label className="mt-3 flex flex-col gap-1 text-sm font-semibold text-[#334155]">
            Date de naissance
            <input
              type="date"
              value={form.birthDate || ""}
              onChange={(event) => onChange("birthDate", event.target.value)}
              aria-invalid={birthDateError ? "true" : undefined}
              className={fieldInputClass(Boolean(birthDateError))}
            />
            {birthDateError ? (
              <span className="text-xs font-semibold text-red-600">{birthDateError}</span>
            ) : (
              <span className="text-xs font-normal text-[#64748B]">Format : AAAA-MM-JJ</span>
            )}
          </label>

          <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
            <label className="flex flex-col gap-1 text-sm font-semibold text-[#334155]">
              Médecin traitant
              <input
                value={form.treatingPhysicianName || ""}
                onChange={(event) => onChange("treatingPhysicianName", event.target.value)}
                placeholder="Dr Martin"
                aria-invalid={physicianNameError ? "true" : undefined}
                className={fieldInputClass(Boolean(physicianNameError))}
              />
              {physicianNameError ? (
                <span className="text-xs font-semibold text-red-600">{physicianNameError}</span>
              ) : null}
            </label>
            <label className="flex flex-col gap-1 text-sm font-semibold text-[#334155]">
              Ville du médecin traitant
              <input
                value={form.treatingPhysicianCity || ""}
                onChange={(event) => onChange("treatingPhysicianCity", event.target.value)}
                placeholder="Paris"
                aria-invalid={physicianCityError ? "true" : undefined}
                className={fieldInputClass(Boolean(physicianCityError))}
              />
              {physicianCityError ? (
                <span className="text-xs font-semibold text-red-600">{physicianCityError}</span>
              ) : null}
            </label>
          </div>
        </>
      ) : null}

      <label className="mt-3 flex flex-col gap-1 text-sm font-semibold text-[#334155]">
        <span className="flex items-center justify-between gap-2">
          Note initiale
          <NoteDictateButton
            value={form.initialNote}
            onChange={(next) => { setNoteDictError(""); onChange("initialNote", next); }}
            onError={(msg) => setNoteDictError(msg || "")}
            className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-[#6941C6] bg-white px-2.5 py-1 text-xs font-black text-[#5B34B0] transition hover:bg-[#F4F3FF] disabled:opacity-60"
          />
        </span>
        <textarea
          value={form.initialNote}
          onChange={(event) => onChange("initialNote", event.target.value)}
          placeholder="Écrivez ou dictez la note..."
          className="h-24 resize-none rounded-xl border border-[#E2E8F0] px-3 py-2 text-sm outline-none focus:border-[#009CA4]"
        />
        {noteDictError ? <span className="text-xs font-semibold text-red-600">{noteDictError}</span> : null}
      </label>

      <div className="mt-2 text-xs text-[#64748B]">{subtitleLine}</div>

      <div className={footerClass}>
        <button
          type="button"
          onClick={onClose}
          className="rounded-xl border border-[#E2E8F0] px-4 py-2 text-sm font-bold text-[#334155] hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#009CA4] focus-visible:ring-offset-1"
        >
          Annuler
        </button>
        <button
          type="button"
          onClick={onSubmit}
          disabled={loading || submitDisabled}
          className="rounded-xl bg-[#009CA4] px-4 py-2 text-sm font-extrabold text-white hover:bg-[#007F87] disabled:cursor-not-allowed disabled:opacity-70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#009CA4] focus-visible:ring-offset-1"
        >
          {loading ? "Création..." : "Créer la fiche"}
        </button>
      </div>
    </div>
  );

  if (embedded) return panel;

  return createPortal(
    <div
      className="fixed inset-0 z-[110] flex items-center justify-center overflow-y-auto bg-[#0A1628]/60 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="create-patient-from-call-heading"
    >
      {panel}
    </div>,
    document.body,
  );
}
