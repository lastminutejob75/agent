export function canCreatePatientFromCall(call) {
  if (!call) return false;
  const isMasked = Boolean(call?.patient?.masked);
  const isKnown = Boolean(call?.patient?.known);
  return !isMasked && !isKnown;
}

function requiresAction(call) {
  return call?.status === "à traiter" || call?.status === "manqué";
}

function isAppointmentLike(call) {
  return call?.type === "rendez-vous" || call?.type === "annulation" || call?.type === "deplacement";
}

function matchesQuery(call, query) {
  const q = String(query || "").trim().toLowerCase();
  if (!q) return true;
  const haystack = [
    call?.patient?.name,
    call?.phone,
    call?.summary,
    call?.claraResume,
    call?.type,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return haystack.includes(q);
}

export function filterCalls(calls, activeTab, query) {
  const source = Array.isArray(calls) ? calls : [];
  return source
    .filter((call) => {
      if (activeTab === "a-traiter") return requiresAction(call);
      if (activeTab === "rendez-vous") return isAppointmentLike(call);
      if (activeTab === "sans-fiche") return !call?.patient?.known;
      if (activeTab === "historique") return call?.status === "traité" || call?.status === "résolu";
      return true;
    })
    .filter((call) => matchesQuery(call, query));
}

export function getCallCounts(calls) {
  const source = Array.isArray(calls) ? calls : [];
  const total = source.length;
  const appointmentsTaken = source.filter(
    (call) => call?.type === "rendez-vous" && (call?.status === "traité" || call?.status === "résolu"),
  ).length;
  const toProcess = source.filter((call) => requiresAction(call)).length;
  const unknownWithPhone = source.filter((call) => canCreatePatientFromCall(call)).length;
  return {
    total,
    appointmentsTaken,
    toProcess,
    unknownWithPhone,
  };
}

export function isAppointmentType(type) {
  return type === "rendez-vous" || type === "annulation" || type === "deplacement";
}
