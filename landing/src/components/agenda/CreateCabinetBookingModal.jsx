import { useEffect, useMemo, useState } from "react";
import { api } from "../../lib/api.js";
import {
  buildCabinetBookingStartIso,
  cabinetTimeChoicesFromHoraires,
  formatTimeChoiceFR,
  pickDefaultCabinetTime,
  todayISO,
  validateCabinetBookingPhone,
} from "../../lib/cabinetBooking.js";
import { isValidContactEmail, validateContactEmail } from "../../lib/contactValidation.js";
import {
  checkPatientDuplicates,
  hasBlockingPatientDuplicate,
} from "../../lib/patientDuplicateCheck.js";
import { normalizePhoneBusinessKey } from "../../lib/phoneNormalize";
import PatientDuplicateBanner from "../patients/PatientDuplicateBanner.jsx";

function normalizePhone(value) {
  return normalizePhoneBusinessKey(value);
}

const EMPTY_FORM = {
  patient_name: "",
  patient_phone: "",
  patient_email: "",
  motif: "Consultation",
  booking_date: "",
  booking_time: "",
};

/**
 * Modal création RDV cabinet (agenda ou fiche patient).
 * @param {{ open: boolean, onClose: () => void, onSuccess?: () => void, lockedPatient?: { patient_name?: string, patient_phone?: string, patient_email?: string } | null, excludePhoneForDuplicate?: string, introVariant?: 'agenda' | 'patient' }} props
 */
export default function CreateCabinetBookingModal({
  open,
  onClose,
  onSuccess,
  lockedPatient = null,
  excludePhoneForDuplicate = "",
  introVariant = "agenda",
}) {
  const locked = Boolean(lockedPatient);
  const [horaires, setHoraires] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [conflicts, setConflicts] = useState([]);
  const [suggestions, setSuggestions] = useState([]);
  const [suggestLoading, setSuggestLoading] = useState(false);

  const today = todayISO();
  const timeChoices = useMemo(() => cabinetTimeChoicesFromHoraires(horaires), [horaires]);

  useEffect(() => {
    if (!open) return;
    api.tenantGetHoraires().catch(() => null).then(setHoraires);
  }, [open]);

  useEffect(() => {
    if (!open) {
      setForm(EMPTY_FORM);
      setError("");
      setConflicts([]);
      setSuggestions([]);
      setSuggestLoading(false);
      return;
    }
    const defaultDate = today;
    const defaultTime = pickDefaultCabinetTime(
      cabinetTimeChoicesFromHoraires(horaires),
    );
    setForm({
      patient_name: String(lockedPatient?.patient_name || "").trim(),
      patient_phone: String(lockedPatient?.patient_phone || "").trim(),
      patient_email: String(lockedPatient?.patient_email || "").trim(),
      motif: "Consultation",
      booking_date: defaultDate,
      booking_time: defaultTime,
    });
    setError("");
  }, [open, lockedPatient?.patient_name, lockedPatient?.patient_phone, lockedPatient?.patient_email]);

  useEffect(() => {
    if (!open || !timeChoices.length) return;
    setForm((p) =>
      timeChoices.includes(p.booking_time)
        ? p
        : { ...p, booking_time: pickDefaultCabinetTime(timeChoices) },
    );
  }, [open, timeChoices]);

  useEffect(() => {
    if (!open) {
      setConflicts([]);
      return;
    }
    const phone = normalizePhone(form.patient_phone);
    const email = (form.patient_email || "").trim();
    if (!phone && !email) {
      setConflicts([]);
      return;
    }
    let cancelled = false;
    const ctrl = new AbortController();
    const tid = window.setTimeout(() => {
      checkPatientDuplicates({
        phone,
        email,
        excludePhone: excludePhoneForDuplicate || (locked ? form.patient_phone : ""),
        signal: ctrl.signal,
      })
        .then((res) => {
          if (!cancelled) {
            setConflicts(Array.isArray(res?.conflicts) ? res.conflicts : []);
          }
        })
        .catch(() => {
          if (!cancelled) setConflicts([]);
        });
    }, 320);
    return () => {
      cancelled = true;
      window.clearTimeout(tid);
      ctrl.abort();
    };
  }, [open, form.patient_phone, form.patient_email, excludePhoneForDuplicate, locked]);

  useEffect(() => {
    if (!open || locked) {
      setSuggestions([]);
      setSuggestLoading(false);
      return;
    }
    const composed = [form.patient_name, form.patient_phone, form.patient_email]
      .map((s) => (s || "").trim())
      .filter(Boolean)
      .join(" ")
      .trim();
    if (composed.length < 2) {
      setSuggestions([]);
      setSuggestLoading(false);
      return;
    }
    const ctrl = new AbortController();
    const tid = window.setTimeout(async () => {
      setSuggestLoading(true);
      try {
        const res = await api.tenantGetPatients(`?q=${encodeURIComponent(composed)}&limit=15`, {
          signal: ctrl.signal,
        });
        if (!ctrl.signal.aborted) {
          setSuggestions(Array.isArray(res?.items) ? res.items : []);
        }
      } catch (e) {
        if (!ctrl.signal.aborted && String(e?.name || "") !== "AbortError") {
          setSuggestions([]);
        }
      } finally {
        if (!ctrl.signal.aborted) setSuggestLoading(false);
      }
    }, 320);
    return () => {
      window.clearTimeout(tid);
      ctrl.abort();
    };
  }, [open, locked, form.patient_name, form.patient_phone, form.patient_email]);

  const phoneError = useMemo(() => {
    const raw = String(form.patient_phone || "").trim();
    if (!raw) return "";
    const check = validateCabinetBookingPhone(form.patient_phone);
    return check.ok ? "" : (check.message || "Numéro invalide.");
  }, [form.patient_phone]);

  const emailError = useMemo(() => {
    const raw = String(form.patient_email || "").trim();
    if (!raw) return "";
    const check = validateContactEmail(raw);
    return check.ok ? "" : (check.message || "Email invalide.");
  }, [form.patient_email]);

  const formValid = useMemo(() => {
    const name = (form.patient_name || "").trim();
    if (!name || name.length < 2) return false;
    if (!validateCabinetBookingPhone(form.patient_phone).ok) return false;
    const emailTrim = (form.patient_email || "").trim();
    if (emailTrim && !isValidContactEmail(emailTrim)) return false;
    if (!form.booking_date || !/^\d{4}-\d{2}-\d{2}$/.test(form.booking_date.trim())) return false;
    if (!form.booking_time || !/^\d{2}:\d{2}$/.test(form.booking_time.trim())) return false;
    const dt = new Date(`${form.booking_date.trim()}T${form.booking_time.trim()}:00`);
    return !Number.isNaN(dt.getTime());
  }, [form]);

  const submitHint = useMemo(() => {
    if (formValid) return "";
    const parts = [];
    const name = (form.patient_name || "").trim();
    if (!name || name.length < 2) parts.push("Indiquez le nom du patient (au moins 2 caractères).");
    if (phoneError) parts.push(phoneError);
    if (emailError) parts.push(emailError);
    if (hasBlockingPatientDuplicate(conflicts)) {
      parts.push("Ce numéro ou cet e-mail est déjà utilisé par une autre fiche patient.");
    }
    if (!form.booking_date || !form.booking_time) {
      parts.push("Choisissez une date et une heure valides.");
    }
    return parts.join(" ") || "Complétez les champs obligatoires pour enregistrer le rendez-vous.";
  }, [formValid, form, phoneError, emailError, conflicts]);

  function applySuggestion(p) {
    if (!p) return;
    const display = (p.display_name || p.validated_name || p.raw_name || "").trim();
    setForm((prev) => ({
      ...prev,
      patient_name: display || prev.patient_name,
      patient_phone: (p.phone || "").trim() || prev.patient_phone,
      patient_email: ((p.email || "").trim()) || prev.patient_email,
    }));
    setSuggestions([]);
  }

  async function handleSubmit() {
    const name = (form.patient_name || "").trim();
    const startIso = buildCabinetBookingStartIso(form.booking_date, form.booking_time);
    if (!startIso) {
      setError("Choisissez une date et une heure valides pour le RDV.");
      return;
    }
    const phoneCheck = validateCabinetBookingPhone(form.patient_phone);
    if (!phoneCheck.ok) {
      setError(phoneCheck.message || "Numéro de téléphone invalide.");
      return;
    }
    const emailTrim = (form.patient_email || "").trim();
    if (emailTrim && !isValidContactEmail(emailTrim)) {
      setError("L’adresse e-mail n’est pas valide.");
      return;
    }
    if (hasBlockingPatientDuplicate(conflicts)) {
      setError(
        "Cet e-mail ou ce numéro est déjà utilisé par une autre fiche patient. Corrigez avant de créer le RDV.",
      );
      return;
    }
    setLoading(true);
    setError("");
    try {
      await api.tenantCreateAgendaBooking({
        patient_name: name,
        patient_phone: normalizePhone(form.patient_phone || ""),
        patient_email: emailTrim,
        motif: (form.motif || "Consultation").trim(),
        start_iso: startIso,
      });
      onSuccess?.();
      onClose();
    } catch (e) {
      setError(e?.message || "Impossible de créer le rendez-vous.");
    } finally {
      setLoading(false);
    }
  }

  if (!open) return null;

  const intro =
    introVariant === "patient"
      ? "Ce rendez-vous sera créé uniquement pour ce patient. Choisissez la date et l’heure ; le nom, le téléphone et l’e-mail ne peuvent pas être modifiés ici."
      : "Ce RDV est enregistré depuis l’espace cabinet. En saisissant le nom, le numéro ou l’e-mail, une suggestion peut préremplir la fiche.";

  return (
    <div
      className="fixed inset-0 z-[120] flex items-end justify-center bg-[#0A1628]/45 p-0 sm:items-center sm:p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="create-cabinet-booking-title"
    >
      <div className="max-h-[92vh] w-full max-w-lg overflow-y-auto rounded-t-[24px] border border-[#E2EAF4] bg-white p-5 shadow-[0_24px_60px_rgba(10,22,40,0.18)] sm:rounded-[24px] sm:p-6">
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <h2 id="create-cabinet-booking-title" className="m-0 text-lg font-black text-[#0A1628]">
              Créer un rendez-vous
            </h2>
            {locked && form.patient_name ? (
              <p className="mt-1 text-sm font-bold text-[#009CA4]">Pour {form.patient_name}</p>
            ) : null}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="grid h-9 w-9 shrink-0 place-items-center rounded-lg border border-[#E2EAF4] text-[#64748B] hover:bg-[#F8FBFD]"
            aria-label="Fermer"
          >
            ✕
          </button>
        </div>
        <p className="mb-4 text-sm leading-relaxed text-[#61708B]">{intro}</p>

        {!locked && (suggestLoading || suggestions.length > 0) ? (
          <div className="mb-4 rounded-xl border border-[#E2EAF4] bg-[#F8FBFD] p-2">
            {suggestLoading ? (
              <p className="m-0 px-2 py-1 text-xs text-[#64748B]">Recherche des patients correspondants…</p>
            ) : null}
            {!suggestLoading && suggestions.length ? (
              <div>
                <p className="mb-1 px-2 text-[10px] font-black uppercase tracking-wide text-[#94A3B8]">
                  Patients correspondants
                </p>
                {suggestions.map((p, idx) => {
                  const label = (p.display_name || p.validated_name || p.raw_name || "Patient").trim();
                  const sub = [(p.phone || "").trim(), (p.email || "").trim()].filter(Boolean).join(" · ");
                  return (
                    <button
                      key={`${p.phone || label}-${idx}`}
                      type="button"
                      onMouseDown={(e) => {
                        e.preventDefault();
                        applySuggestion(p);
                      }}
                      className="flex w-full flex-col border-t border-[#EEF3F8] px-2 py-2.5 text-left first:border-t-0 hover:bg-white"
                    >
                      <span className="text-sm font-black text-[#0A1628]">{label}</span>
                      {sub ? <span className="text-xs text-[#64748B]">{sub}</span> : null}
                    </button>
                  );
                })}
              </div>
            ) : null}
          </div>
        ) : null}

        {locked ? (
          <div className="mb-4 space-y-2 rounded-xl border border-[#DDE7F1] bg-[#F8FBFD] p-3.5">
            <div>
              <div className="text-[10px] font-bold uppercase tracking-wide text-[#94A3B8]">Patient</div>
              <div className="mt-0.5 text-sm font-black text-[#0A1628]">{form.patient_name || "—"}</div>
            </div>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              <div>
                <div className="text-[10px] font-bold uppercase tracking-wide text-[#94A3B8]">Téléphone</div>
                <div className="mt-0.5 text-sm font-bold text-[#0A1628]">{form.patient_phone || "—"}</div>
              </div>
              <div>
                <div className="text-[10px] font-bold uppercase tracking-wide text-[#94A3B8]">E-mail</div>
                <div className="mt-0.5 break-all text-sm font-bold text-[#0A1628]">
                  {form.patient_email || "Non renseigné"}
                </div>
              </div>
            </div>
          </div>
        ) : (
          <>
            <label className="mb-3 block text-xs font-black text-[#0A1628]">
              Nom du patient *
              <input
                className="mt-1.5 box-border w-full rounded-xl border border-[#DDE7F1] px-3 py-2.5 text-sm font-semibold outline-none focus:border-[#009CA4] focus:ring-2 focus:ring-[#009CA4]/20"
                value={form.patient_name}
                onChange={(e) => setForm((p) => ({ ...p, patient_name: e.target.value }))}
                autoComplete="name"
              />
            </label>
            <label className="mb-3 block text-xs font-black text-[#0A1628]">
              Téléphone
              <input
                className={`mt-1.5 box-border w-full rounded-xl border px-3 py-2.5 text-sm font-semibold outline-none focus:ring-2 focus:ring-[#009CA4]/20 ${phoneError ? "border-red-300 focus:border-red-400" : "border-[#DDE7F1] focus:border-[#009CA4]"}`}
                value={form.patient_phone}
                onChange={(e) => setForm((p) => ({ ...p, patient_phone: e.target.value }))}
                autoComplete="tel"
                inputMode="tel"
                placeholder="06 12 34 56 78"
              />
              {phoneError ? <span className="mt-1 block text-xs font-semibold text-red-600">{phoneError}</span> : null}
            </label>
            <label className="mb-3 block text-xs font-black text-[#0A1628]">
              E-mail (optionnel)
              <input
                type="email"
                className={`mt-1.5 box-border w-full rounded-xl border px-3 py-2.5 text-sm font-semibold outline-none focus:ring-2 focus:ring-[#009CA4]/20 ${emailError ? "border-red-300 focus:border-red-400" : "border-[#DDE7F1] focus:border-[#009CA4]"}`}
                value={form.patient_email}
                onChange={(e) => setForm((p) => ({ ...p, patient_email: e.target.value }))}
                autoComplete="email"
              />
              {emailError ? <span className="mt-1 block text-xs font-semibold text-red-600">{emailError}</span> : null}
            </label>
          </>
        )}

        {conflicts.length ? (
          <div className="mb-3">
            <PatientDuplicateBanner conflicts={conflicts} />
          </div>
        ) : null}

        <label className="mb-3 block text-xs font-black text-[#0A1628]">
          Motif
          <input
            className="mt-1.5 box-border w-full rounded-xl border border-[#DDE7F1] px-3 py-2.5 text-sm font-semibold outline-none focus:border-[#009CA4] focus:ring-2 focus:ring-[#009CA4]/20"
            value={form.motif}
            onChange={(e) => setForm((p) => ({ ...p, motif: e.target.value }))}
          />
        </label>

        <div className="mb-3">
          <span className="text-xs font-black text-[#0A1628]">Date et horaire *</span>
          <div className="mt-2 grid grid-cols-1 gap-3 sm:grid-cols-2">
            <label className="block text-[11px] font-bold text-[#94A3B8]">
              Jour
              <input
                type="date"
                min={today}
                className="mt-1.5 box-border w-full rounded-xl border border-[#DDE7F1] px-3 py-2.5 text-sm font-semibold outline-none focus:border-[#009CA4]"
                value={form.booking_date}
                onChange={(e) => setForm((p) => ({ ...p, booking_date: e.target.value }))}
              />
            </label>
            <label className="block text-[11px] font-bold text-[#94A3B8]">
              Heure
              <select
                className="mt-1.5 box-border w-full rounded-xl border border-[#DDE7F1] px-3 py-2.5 text-sm font-semibold outline-none focus:border-[#009CA4]"
                value={
                  timeChoices.includes(form.booking_time)
                    ? form.booking_time
                    : (timeChoices[0] || "")
                }
                onChange={(e) => setForm((p) => ({ ...p, booking_time: e.target.value }))}
              >
                {timeChoices.map((t) => (
                  <option key={t} value={t}>
                    {formatTimeChoiceFR(t)}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>

        {!formValid && submitHint ? (
          <p className="mb-2 text-xs font-semibold text-[#64748B]" role="status">
            {submitHint}
          </p>
        ) : null}
        {error ? (
          <p className="mb-2 text-xs font-semibold text-red-600" role="alert">
            {error}
          </p>
        ) : null}

        <div className="mt-4 flex flex-col gap-2 sm:flex-row">
          <button
            type="button"
            disabled={loading || !formValid}
            onClick={() => void handleSubmit()}
            className="flex-1 rounded-xl bg-[#009CA4] px-4 py-3 text-sm font-black text-white shadow-[0_8px_20px_rgba(0,156,164,0.22)] hover:bg-[#008891] disabled:cursor-not-allowed disabled:opacity-55"
          >
            {loading ? "Enregistrement…" : "Enregistrer le rendez-vous"}
          </button>
          <button
            type="button"
            onClick={onClose}
            className="rounded-xl border border-[#DDE7F1] bg-white px-4 py-3 text-sm font-black text-[#475569] hover:bg-[#F8FBFD]"
          >
            Annuler
          </button>
        </div>
      </div>
    </div>
  );
}
