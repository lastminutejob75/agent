import { useEffect, useMemo, useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { api, clearTenantToken, isTenantUnauthorized } from "../lib/api.js";
import { getImpersonation, setImpersonation } from "./Impersonate";
import AppSidebar from "../components/layout/AppSidebar.jsx";
import AppTopbar from "../components/layout/AppTopbar.jsx";
import AppMobileBottomNav from "../components/layout/AppMobileBottomNav.jsx";
import { COLORS, NAV_ITEMS, ROUTES } from "../components/layout/layout.constants.js";
import { createLayoutStyles, createShellCss } from "../components/layout/layout.styles.js";

const S = createLayoutStyles(COLORS);
const SHELL_CSS = createShellCss(COLORS);

export default function AppLayout() {
  const [me, setMe] = useState(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);
  const [dashboard, setDashboard] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [notificationsItems, setNotificationsItems] = useState([]);
  const [notificationsLoading, setNotificationsLoading] = useState(false);
  const [claraRulesSummary, setClaraRulesSummary] = useState({ configured: 0, total: 4 });

  const navigate = useNavigate();
  const location = useLocation();

  const impersonation = getImpersonation();
  const path = location.pathname;
  const isPatientDetail = path.startsWith("/app/patients/") && path !== "/app/patients";
  const hideTopbar = path.startsWith("/app/patient-dashboard");
  const demandBadge = dashboard?.counters_7d?.transfers ?? 0;
  const hideToProcessStrip =
    hideTopbar ||
    path.startsWith("/app/demandes") ||
    path.startsWith("/app/onboarding") ||
    path.startsWith("/app/impersonate");
  const initials = (me?.tenant_name || "U")
    .split(/\s+/)
    .map((w) => w[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);
  const showWelcomeSecurityBanner = new URLSearchParams(location.search).get("welcome") === "1";
  const routeMeta = ROUTES[path] || null;
  const isClaraPage = path.startsWith("/app/clara");

  useEffect(() => {
    function readSummary() {
      try {
        const raw = window.localStorage.getItem("uwi_clara_rules_summary");
        if (!raw) return;
        const parsed = JSON.parse(raw);
        const configured = Number(parsed?.configured);
        const total = Number(parsed?.total);
        if (Number.isFinite(configured) && Number.isFinite(total) && total > 0) {
          setClaraRulesSummary({ configured, total });
        }
      } catch {
        // no-op
      }
    }
    readSummary();
    function onCustom(event) {
      const configured = Number(event?.detail?.configured);
      const total = Number(event?.detail?.total);
      if (Number.isFinite(configured) && Number.isFinite(total) && total > 0) {
        setClaraRulesSummary({ configured, total });
      }
    }
    function onStorage(e) {
      if (e.key === "uwi_clara_rules_summary") readSummary();
    }
    window.addEventListener("uwi:clara-rules-summary", onCustom);
    window.addEventListener("storage", onStorage);
    return () => {
      window.removeEventListener("uwi:clara-rules-summary", onCustom);
      window.removeEventListener("storage", onStorage);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    api
      .tenantMe()
      .then((data) => {
        if (cancelled) return;
        setMe(data);
        setLoading(false);
      })
      .catch((e) => {
        if (cancelled) return;
        if (isTenantUnauthorized(e)) {
          setImpersonation(null);
          clearTenantToken();
          const nextPath = `${location.pathname || "/app"}${location.search || ""}`;
          navigate(`/login?next=${encodeURIComponent(nextPath)}`, { replace: true });
          return;
        }
        setErr(e?.message || e?.data?.detail || "Chargement impossible.");
        setLoading(false);
      });

    api
      .tenantDashboard()
      .then((data) => {
        if (!cancelled) setDashboard(data);
      })
      .catch(() => {
        if (!cancelled) setDashboard(null);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (loading || !me) return;
    if (!getImpersonation() && location.pathname === "/app/onboarding" && me?.client_onboarding_completed) {
      navigate(`/app${location.search || ""}`, { replace: true });
    }
  }, [loading, me, location.pathname, location.search, navigate]);

  const handleLogout = () => {
    setImpersonation(null);
    clearTenantToken();
    window.location.href = "/";
  };

  const navigateFromTopbar = (to) => {
    setSidebarOpen(false);
    setNotificationsOpen(false);
    navigate(to);
  };

  const openNotifications = async () => {
    setSidebarOpen(false);
    setNotificationsOpen((prev) => !prev);
    if (!notificationsOpen) {
      setNotificationsLoading(true);
      try {
        const data = await api.tenantGetHandoffs("?limit=10&days=30");
        const items = Array.isArray(data?.items) ? data.items : [];
        setNotificationsItems(
          items
            .filter((h) => {
              const s = String(h?.status || "").toLowerCase();
              return s !== "processed" && s !== "cancelled";
            })
            .slice(0, 8),
        );
      } catch {
        setNotificationsItems([]);
      } finally {
        setNotificationsLoading(false);
      }
    }
  };

  const layoutTopOffset = impersonation ? 46 : 0;

  if (err && !me) {
    return (
      <div style={{ minHeight: "100vh", background: COLORS.bg, padding: 24 }}>
        <div
          style={{
            maxWidth: 560,
            margin: "0 auto",
            background: "#fff",
            border: `1px solid ${COLORS.border}`,
            borderRadius: 14,
            padding: 22,
          }}
        >
          <h2 style={{ margin: 0, color: COLORS.title, fontSize: 18 }}>Chargement échoué</h2>
          <p style={{ margin: "8px 0 0", color: COLORS.text, fontSize: 14 }}>{err}</p>
          <div style={{ marginTop: 14, display: "flex", gap: 10 }}>
            <button type="button" onClick={() => window.location.reload()} style={S.primaryBtn}>
              Réessayer
            </button>
            <button type="button" onClick={handleLogout} style={S.secondaryBtn}>
              Se déconnecter
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ minHeight: "100vh", background: COLORS.bg, color: COLORS.title }}>
      <style>{SHELL_CSS}</style>

      {impersonation ? (
        <div style={S.adminBanner}>
          Mode admin - vous visualisez le compte de <strong>{impersonation.tenant_name}</strong>
        </div>
      ) : null}

      <AppSidebar
        navItems={NAV_ITEMS}
        demandBadge={demandBadge}
        sidebarOpen={sidebarOpen}
        layoutTopOffset={layoutTopOffset}
        navigate={navigate}
        onClose={() => setSidebarOpen(false)}
        initials={initials}
        tenantName={me?.tenant_name}
        onLogout={handleLogout}
        styles={S}
        colors={COLORS}
      />

      <div
        className={`uwi-overlay ${sidebarOpen ? "open" : ""}`}
        onClick={() => setSidebarOpen(false)}
        aria-hidden="true"
      />

      <div className="uwi-main" style={{ paddingTop: layoutTopOffset }}>
        {!hideTopbar ? (
          <AppTopbar
            routeMeta={routeMeta}
            isClaraPage={isClaraPage}
            claraRulesSummary={claraRulesSummary}
            onOpenNotifications={openNotifications}
            onOpenProfile={() => navigateFromTopbar("/app/profile")}
            onOpenMenu={() => setSidebarOpen(true)}
            notificationsCount={demandBadge}
            styles={S}
          />
        ) : null}

        {notificationsOpen ? (
          <>
            <div
              role="button"
              tabIndex={-1}
              aria-label="Fermer les notifications"
              onClick={() => setNotificationsOpen(false)}
              style={{ position: "fixed", inset: 0, background: "rgba(7,26,51,0.18)", zIndex: 90 }}
            />
            <div
              role="dialog"
              aria-label="Notifications"
              style={{
                position: "fixed",
                top: 60,
                right: 14,
                width: "min(360px, calc(100vw - 28px))",
                maxHeight: "70vh",
                overflowY: "auto",
                background: "#fff",
                border: `1px solid ${COLORS.border}`,
                borderRadius: 18,
                boxShadow: "0 24px 60px rgba(7,26,51,0.18)",
                zIndex: 100,
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "12px 14px",
                  borderBottom: `1px solid ${COLORS.border}`,
                }}
              >
                <strong style={{ fontSize: 14, color: COLORS.title }}>Notifications</strong>
                <button
                  type="button"
                  onClick={() => setNotificationsOpen(false)}
                  aria-label="Fermer"
                  style={{ border: 0, background: "transparent", fontSize: 18, cursor: "pointer", color: COLORS.title }}
                >
                  ×
                </button>
              </div>
              {notificationsLoading ? (
                <div style={{ padding: 16, color: COLORS.text, fontSize: 13 }}>Chargement…</div>
              ) : notificationsItems.length === 0 ? (
                <div style={{ padding: 16, color: COLORS.text, fontSize: 13 }}>Aucune notification pour le moment.</div>
              ) : (
                <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
                  {notificationsItems.map((item) => {
                    const id = item?.id ?? Math.random();
                    const title = String(item?.summary || item?.reason || item?.label || "Nouvelle demande patient");
                    const dt = new Date(String(item?.created_at || ""));
                    const when = Number.isNaN(dt.getTime())
                      ? ""
                      : dt.toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
                    const urgent = String(item?.priority || "").toLowerCase().includes("urgent");
                    return (
                      <li key={id} style={{ borderBottom: `1px solid ${COLORS.border}` }}>
                        <button
                          type="button"
                          onClick={() => navigateFromTopbar("/app/demandes")}
                          style={{
                            display: "flex",
                            width: "100%",
                            gap: 10,
                            alignItems: "flex-start",
                            border: 0,
                            background: "transparent",
                            padding: "12px 14px",
                            textAlign: "left",
                            cursor: "pointer",
                            fontFamily: "inherit",
                          }}
                        >
                          <span
                            aria-hidden="true"
                            style={{
                              width: 8,
                              height: 8,
                              marginTop: 6,
                              borderRadius: 999,
                              background: urgent ? "#EF4444" : "#F59E0B",
                              flexShrink: 0,
                            }}
                          />
                          <span style={{ display: "flex", flexDirection: "column", gap: 2, minWidth: 0 }}>
                            <span style={{ fontSize: 13, fontWeight: 700, color: COLORS.title, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                              {title}
                            </span>
                            {when ? (
                              <span style={{ fontSize: 12, color: COLORS.text }}>{when}</span>
                            ) : null}
                          </span>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
              <div style={{ padding: 10, borderTop: `1px solid ${COLORS.border}`, display: "flex", justifyContent: "flex-end" }}>
                <button
                  type="button"
                  onClick={() => navigateFromTopbar("/app/demandes")}
                  style={{ border: 0, background: "transparent", color: COLORS.title, fontWeight: 700, cursor: "pointer", fontFamily: "inherit", fontSize: 13 }}
                >
                  Tout voir →
                </button>
              </div>
            </div>
          </>
        ) : null}

        {!hideToProcessStrip ? (
          <button
            type="button"
            onClick={() => navigateFromTopbar("/app/demandes?status=%C3%80%20traiter&priority=Urgence")}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 12,
              width: "calc(100% - 32px)",
              margin: "8px 16px 0",
              padding: "10px 14px",
              borderRadius: 14,
              border: "1px solid #FED7AA",
              background: demandBadge > 0 ? "#FFF7ED" : "#F8FAFC",
              color: demandBadge > 0 ? "#9A3412" : "#475569",
              fontWeight: 800,
              fontSize: 14,
              cursor: "pointer",
              fontFamily: "inherit",
              boxShadow: "0 4px 14px rgba(7,26,51,.05)",
            }}
          >
            <span style={{ display: "inline-flex", alignItems: "center", gap: 10 }}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" />
                <path d="M12 9v4M12 17h.01" />
              </svg>
              {demandBadge > 0
                ? `A traiter (${demandBadge})`
                : "A traiter"}
            </span>
            <span aria-hidden="true" style={{ fontSize: 16, opacity: 0.7 }}>›</span>
          </button>
        ) : null}

        <main style={S.content}>
          {showWelcomeSecurityBanner ? (
            <div style={S.securityBanner}>
              <span>Votre compte utilise un mot de passe temporaire.</span>
              <button
                type="button"
                onClick={() => navigate("/app/settings#security")}
                style={{ ...S.secondaryBtn, padding: "7px 10px", fontSize: 12 }}
              >
                Changer mon mot de passe
              </button>
            </div>
          ) : null}
          <Outlet context={{ me, dashboard, meLoading: loading }} />
        </main>
      </div>

      <AppMobileBottomNav navItems={NAV_ITEMS} demandBadge={demandBadge} colors={COLORS} />
    </div>
  );
}
