export function applySearchParamsUpdates(current, updates = {}) {
  const params = new URLSearchParams(current);
  Object.entries(updates).forEach(([key, value]) => {
    if (value == null || value === "") params.delete(key);
    else params.set(key, String(value));
  });
  return params;
}

export function kpiQueryUpdates(kpiId) {
  if (kpiId === "new") return { status: "new", page: 1 };
  if (kpiId === "to_contact") return { status: "to_contact", page: 1 };
  if (kpiId === "demo") return { status: "demo", page: 1 };
  if (kpiId === "trial") return { status: "trial", page: 1 };
  if (kpiId === "reset") return { status: null, search: null, page: 1, follow_up: null };
  return { page: 1 };
}
