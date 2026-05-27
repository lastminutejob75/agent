import { createContext, useContext, useEffect, useState } from "react";

/**
 * Provider qui detecte le mode demo backend (GET /api/admin/_meta).
 *
 * Expose :
 *  - isDemoMode    : boolean
 *  - dataset_label : string (ex. "Dataset factice (8 cabinets, ...)")
 *  - tenants_count : number
 *
 * Pas d'auth requise (endpoint public). Utiliser le hook useDemoMode() pour
 * desactiver les boutons d'action en mode demo.
 */
const DemoCtx = createContext({ isDemoMode: false });

export function DemoModeProvider({ children }) {
  const [meta, setMeta] = useState({ isDemoMode: false });

  useEffect(() => {
    const base = (import.meta.env.VITE_UWI_API_BASE_URL || "").replace(/\/$/, "");
    if (!base) return;
    fetch(`${base}/api/admin/_meta`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (d) {
          setMeta({
            isDemoMode: !!d.demo_mode,
            datasetLabel: d.dataset_label || null,
            tenantsCount: d.tenants_count ?? null,
          });
        }
      })
      .catch(() => {});
  }, []);

  return <DemoCtx.Provider value={meta}>{children}</DemoCtx.Provider>;
}

export function useDemoMode() {
  return useContext(DemoCtx);
}

/**
 * Helper : retourne props (disabled + title) a appliquer a un bouton write
 * en mode demo. A spreader sur le composant Button :
 *   <Button {...demoDisabled(isDemoMode, "Suspendre un client")} onClick={...}>
 */
export function demoDisabled(isDemoMode, actionLabel = "Cette action") {
  if (!isDemoMode) return {};
  return {
    disabled: true,
    title: `${actionLabel} : desactivee en mode demo`,
  };
}
