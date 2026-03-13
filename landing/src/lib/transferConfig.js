const TRANSFER_CASE_ORDER = ["urgent", "unhappy", "complex", "insists", "other"];
const TRANSFER_DAY_ORDER = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"];

export function sanitizePhoneInput(value) {
  const raw = String(value || "");
  const cleaned = raw.replace(/[^\d+]/g, "");
  const hasPlus = cleaned.startsWith("+");
  const digits = cleaned.replace(/\+/g, "");
  return `${hasPlus ? "+" : ""}${digits.slice(0, 15)}`;
}

export function normalizeFrenchPhone(value) {
  const cleaned = sanitizePhoneInput(value);
  if (!cleaned) return "";
  if (cleaned.startsWith("+")) return `+${cleaned.slice(1).replace(/\D/g, "")}`;
  const digits = cleaned.replace(/\D/g, "");
  if (!digits) return "";
  if (digits.startsWith("00")) return `+${digits.slice(2)}`;
  if (digits.startsWith("33")) return `+${digits}`;
  if (digits.startsWith("0") && digits.length === 10) return `+33${digits.slice(1)}`;
  if (digits.length === 9) return `+33${digits}`;
  return digits;
}

export function parseTransferCases(value) {
  let items = [];
  if (Array.isArray(value)) {
    items = value;
  } else if (typeof value === "string") {
    try {
      const parsed = JSON.parse(value);
      items = Array.isArray(parsed) ? parsed : value.split(",");
    } catch {
      items = value.split(",");
    }
  }
  const cleaned = [...new Set(items.map((item) => String(item || "").trim()).filter(Boolean))];
  return cleaned.sort((a, b) => {
    const indexA = TRANSFER_CASE_ORDER.indexOf(a);
    const indexB = TRANSFER_CASE_ORDER.indexOf(b);
    if (indexA === -1 && indexB === -1) return a.localeCompare(b);
    if (indexA === -1) return 1;
    if (indexB === -1) return -1;
    return indexA - indexB;
  });
}

export function parseTransferHours(value) {
  if (value && typeof value === "object" && !Array.isArray(value)) return value;
  if (typeof value === "string") {
    try {
      const parsed = JSON.parse(value);
      return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
    } catch {
      return {};
    }
  }
  return {};
}

function normalizeBoolean(value, fallback = false) {
  if (value === undefined || value === null || value === "") return fallback;
  if (typeof value === "boolean") return value;
  return String(value).trim().toLowerCase() === "true";
}

function normalizeCallbackEnabled(value) {
  if (value === undefined || value === null || value === "") return true;
  if (typeof value === "boolean") return value;
  return String(value).trim().toLowerCase() !== "false";
}

function normalizeTransferHoursForSignature(value) {
  const hours = parseTransferHours(value);
  if (!hours || Object.keys(hours).length === 0) return {};
  const normalized = {};
  for (const day of TRANSFER_DAY_ORDER) {
    const slot = hours?.[day];
    if (!slot) continue;
    normalized[day] = {
      enabled: Boolean(slot.enabled),
      from: String(slot.from || ""),
      to: String(slot.to || ""),
    };
  }
  return normalized;
}

export function buildTransferConfigSignature(params) {
  const cabinetPhone = normalizeFrenchPhone(params?.phone_number ?? params?.phoneNumber ?? "");
  const assistantPhone = normalizeFrenchPhone(
    params?.transfer_number ?? params?.transferNumber ?? params?.phone_number ?? params?.phoneNumber ?? "",
  );
  const practitionerPhone = normalizeFrenchPhone(
    params?.transfer_practitioner_phone ?? params?.transferPractitionerPhone ?? "",
  );
  const liveEnabled = normalizeBoolean(params?.transfer_live_enabled ?? params?.transferLiveEnabled, false);
  const callbackEnabled = normalizeCallbackEnabled(params?.transfer_callback_enabled ?? params?.transferCallbackEnabled);
  const transferCases = parseTransferCases(params?.transfer_cases ?? params?.transferCases);
  const transferHours = normalizeTransferHoursForSignature(params?.transfer_hours ?? params?.transferHours);
  const alwaysUrgent = normalizeBoolean(params?.transfer_always_urgent ?? params?.transferAlwaysUrgent, false);
  const noConsultation = normalizeBoolean(params?.transfer_no_consultation ?? params?.transferNoConsultation, false);

  return JSON.stringify({
    cabinetPhone,
    assistantPhone,
    practitionerPhone,
    liveEnabled,
    callbackEnabled,
    transferCases,
    transferHours,
    alwaysUrgent,
    noConsultation,
  });
}

function buildLegacyAdminTransferConfigSignature(params) {
  const cabinetPhone = normalizeFrenchPhone(params?.phone_number ?? params?.phoneNumber ?? "");
  const assistantPhone = normalizeFrenchPhone(
    params?.transfer_number ?? params?.transferNumber ?? params?.phone_number ?? params?.phoneNumber ?? "",
  );
  const practitionerPhone = normalizeFrenchPhone(
    params?.transfer_practitioner_phone ?? params?.transferPractitionerPhone ?? "",
  );
  const liveEnabled = normalizeBoolean(params?.transfer_live_enabled ?? params?.transferLiveEnabled, false);
  const callbackEnabled = normalizeCallbackEnabled(params?.transfer_callback_enabled ?? params?.transferCallbackEnabled);

  return JSON.stringify({
    cabinetPhone,
    assistantPhone,
    practitionerPhone,
    liveEnabled,
    callbackEnabled,
  });
}

function buildLegacyClientTransferConfigSignature(params) {
  return buildLegacyAdminTransferConfigSignature({
    ...params,
    transfer_practitioner_phone: "",
    transferPractitionerPhone: "",
  });
}

export function isTransferConfigConfirmed(params) {
  const signature = String(
    params?.transfer_config_confirmed_signature ?? params?.transferConfigConfirmedSignature ?? "",
  ).trim();
  if (!signature) return false;
  return signature === buildTransferConfigSignature(params)
    || signature === buildLegacyAdminTransferConfigSignature(params)
    || signature === buildLegacyClientTransferConfigSignature(params);
}
