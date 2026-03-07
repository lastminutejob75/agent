import { useState, useEffect } from "react";
import { Outlet, NavLink, useLocation, useNavigate } from "react-router-dom";
import { api, clearTenantToken, isTenantUnauthorized } from "../lib/api.js";
import { getImpersonation, setImpersonation } from "./Impersonate";
import "./ClientDashboard.css";

const TEAL = "#00d4a0";
const TEALX = "#00b389";
const NAVY = "#0d1b2e";

const ROUTES = {
  "/app": { title: "Vue d'ensemble", sub: "" },
  "/app/appels": { title: "Journal des appels", sub: "" },
  "/app/agenda": { title: "Mon agenda", sub: "" },
  "/app/horaires": { title: "Mes horaires", sub: "" },
  "/app/actions": { title: "Actions en attente", sub: "" },
  "/app/facturation": { title: "Facturation", sub: "" },
  "/app/profil": { title: "Mon profil", sub: "" },
  "/app/config": { title: "Configuration IA", sub: "" },
  "/app/status": { title: "Statut", sub: "" },
  "/app/settings": { title: "Paramètres", sub: "" },
  "/app/rgpd": { title: "RGPD", sub: "" },
};

const PRIMARY_NAV = [
  { to: "/app", label: "Vue d'ensemble", icon: "⊞", end: true },
  { to: "/app/appels", label: "Appels", icon: "◎" },
  { to: "/app/agenda", label: "Agenda", icon: "▦" },
  { to: "/app/actions", label: "Actions", icon: "◈" },
];

const SECONDARY_NAV = [
  { to: "/app/facturation", label: "Facturation", icon: "◇" },
  { to: "/app/profil", label: "Mon profil", icon: "○" },
  { to: "/app/config", label: "Config IA", icon: "◆" },
  { to: "/app/status", label: "Statut", icon: "◉" },
  { to: "/app/rgpd", label: "RGPD", icon: "⊙" },
  { to: "/app/settings", label: "Paramètres", icon: "⚙" },
];

function Dot({ color = TEAL, size = 8 }) {
  return (
    <span
      style={{
        position: "relative",
        display: "inline-flex",
        width: size,
        height: size,
        borderRadius: "50%",
        background: color,
        flexShrink: 0,
      }}
    />
  );
}

function ShellNavItem({ to, icon, label, end = false, closeSidebar, muted = false, badge = null }) {
  return (
    <NavLink to={to} end={end} onClick={closeSidebar} style={{ textDecoration: "none" }}>
      {({ isActive }) => (
        <div
          className={`client-shell-nav-item ${isActive ? "on" : ""} ${muted ? "muted" : ""}`}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 9,
            padding: muted ? "7px 10px" : "8px 10px",
            borderRadius: 7,
            fontSize: muted ? 12 : 13,
            cursor: "pointer",
            fontWeight: isActive && !muted ? 700 : muted ? 500 : 500,
            color: muted ? "#94a3b8" : isActive ? NAVY : "#64748b",
            background: isActive && !muted ? "rgba(0,212,160,.09)" : "transparent",
            border: isActive && !muted ? "1px solid rgba(0,212,160,.15)" : "1px solid transparent",
            transition: "all .15s ease",
          }}
        >
          <span>{icon}</span>
          <span>{label}</span>
          {badge != null && badge > 0 ? (
            <span
              style={{
                marginLeft: "auto",
                minWidth: 18,
                height: 18,
                padding: "0 6px",
                borderRadius: 999,
                background: "#dc2626",
                color: "#fff",
                fontSize: 10,
                fontWeight: 800,
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              {badge}
            </span>
          ) : null}
        </div>
      )}
    </NavLink>
  );
}

export default function AppLayout() {
  const [me, setMe] = useState(null);
  const [err, setErr] = useState(null);
  const [loading, setLoading] = useState(true);
  const [dashboard, setDashboard] = useState(null);
  const [clock, setClock] = useState(new Date());
  const [sbOpen, setSbOpen] = useState(false);
  const [imgErr, setImgErr] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    api
      .tenantMe()
      .then((m) => {
        setMe(m);
        return api.tenantDashboard().catch(() => null);
      })
      .then((dash) => {
        setDashboard(dash);
      })
      .catch((e) => {
        if (isTenantUnauthorized(e)) {
          setImpersonation(null);
          clearTenantToken();
          window.location.href = "/";
          return;
        }
        setErr(e?.message || e?.data?.detail || "Chargement impossible. Réessayez ou déconnectez-vous.");
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (loading || !me) return;
    if (!getImpersonation() && location.pathname.startsWith("/app") && !me?.client_onboarding_completed) {
      navigate(`/app/onboarding${location.search || ""}`, { replace: true });
    }
  }, [loading, me, location.pathname, location.search, navigate]);

  useEffect(() => {
    const timer = window.setInterval(() => setClock(new Date()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  const handleLogout = () => {
    setImpersonation(null);
    clearTenantToken();
    window.location.href = "/";
  };

  const closeSidebar = () => setSbOpen(false);

  if (loading) {
    return (
      <div className="dash" style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "#f0f4f8" }}>
        <p style={{ color: "#64748b", fontFamily: "'DM Sans', sans-serif" }}>Chargement...</p>
      </div>
    );
  }

  if (err) {
    const errMsg = typeof err === "string" ? err : (err?.message || err?.data?.detail || "Erreur");
    return (
      <div className="dash" style={{ minHeight: "100vh", padding: "2rem", background: "#f0f4f8", fontFamily: "'DM Sans', sans-serif" }}>
        <div style={{ maxWidth: 560, margin: "0 auto", background: "#fff", border: "1px solid #e2e8f0", borderRadius: 14, padding: 24, color: "#dc2626" }}>
          <p><strong>Chargement échoué</strong></p>
          <p style={{ marginTop: "0.5rem", fontSize: "0.95rem", color: "#475569" }}>{errMsg}</p>
          <div style={{ marginTop: "1rem", display: "flex", gap: 10 }}>
            <button
              type="button"
              onClick={() => {
                setErr(null);
                setLoading(true);
                window.location.reload();
              }}
              style={{ borderRadius: 10, border: "1px solid #cbd5e1", background: "#0f172a", color: "#fff", padding: "10px 14px", fontSize: 13, cursor: "pointer" }}
            >
              Réessayer
            </button>
            <button
              type="button"
              onClick={handleLogout}
              style={{ borderRadius: 10, border: "1px solid #cbd5e1", background: "#fff", color: "#334155", padding: "10px 14px", fontSize: 13, cursor: "pointer" }}
            >
              Se déconnecter
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (!me) return null;

  const impersonation = getImpersonation();
  const path = location.pathname;
  const routeInfo = ROUTES[path] || { title: "Mon Cabinet", sub: "" };
  const showWelcomeSecurityBanner = new URLSearchParams(location.search).get("welcome") === "1";
  const sub = routeInfo.sub || (path === "/app" ? new Date().toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long", year: "numeric" }) : "");
  const assistantName = (me?.assistant_name || "Sophie").replace(/^./, (s) => s.toUpperCase());
  const planLabel = (me?.plan_key || "growth").replace(/^./, (s) => s.toUpperCase());
  const clockLabel = clock.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  const callsBadge = dashboard?.counters_7d?.calls_total ?? 0;
  const urgentBadge = dashboard?.counters_7d?.transfers ?? 0;
  const initials = (me.tenant_name || "U")
    .split(/\s+/)
    .map((w) => w[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);

  return (
    <div className="dash" style={S.root}>
      <style>{SHELL_CSS}</style>

      {impersonation && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            zIndex: 60,
            background: "#fff0f3",
            borderBottom: "1px solid #fecdd3",
            padding: "10px 20px",
            fontSize: 13,
            fontWeight: 600,
            color: "#dc2626",
          }}
          role="alert"
        >
          Mode admin – vous visualisez le compte de <strong>{impersonation.tenant_name}</strong>
        </div>
      )}

      <aside className={`client-shell-sidebar ${sbOpen ? "open" : ""}`} style={{ ...S.sidebar, top: impersonation ? 44 : 0 }}>
        <div style={S.brand}>
          <div style={S.brandIcon}>
            <span style={{ fontSize: 11, fontWeight: 800, color: NAVY }}>UW</span>
          </div>
          <div>
            <div style={S.brandName}>UWI Medical</div>
            <div style={S.brandSub}>IA SECRÉTARIAT</div>
          </div>
        </div>

        <div style={S.navWrap}>
          {PRIMARY_NAV.map((item) => (
            <ShellNavItem
              key={item.to}
              to={item.to}
              icon={item.icon}
              label={item.label}
              end={item.end}
              closeSidebar={closeSidebar}
              badge={item.to === "/app/appels" ? (callsBadge > 0 ? callsBadge : null) : null}
            />
          ))}
        </div>

        <div style={S.paramTitle}>PARAMÈTRES</div>
        <div style={S.navWrapSecondary}>
          {SECONDARY_NAV.map((item) => (
            <ShellNavItem
              key={item.to}
              to={item.to}
              icon={item.icon}
              label={item.label}
              closeSidebar={closeSidebar}
              muted
            />
          ))}
        </div>

        <div style={S.assistantCard}>
          <div style={S.assistantTag}>VOTRE ASSISTANTE</div>
          <div style={S.assistantInner}>
            <div style={{ position: "relative", flexShrink: 0 }}>
              {!imgErr ? (
                <img
                  src="https://randomuser.me/api/portraits/women/44.jpg"
                  alt={assistantName}
                  onError={() => setImgErr(true)}
                  style={S.assistantAvatar}
                />
              ) : (
                <div style={S.assistantFallback}>{assistantName.slice(0, 1)}</div>
              )}
              <div style={S.assistantOnline} />
            </div>
            <div>
              <div style={S.assistantName}>{assistantName}</div>
              <div style={S.assistantMeta}>🎧 Calme · pro</div>
              <div style={S.assistantStatus}>
                <Dot color={TEAL} size={6} />
                <span>En ligne</span>
              </div>
            </div>
          </div>
        </div>

        <div style={S.sidebarFooter}>
          <div style={S.footerAvatar}>{initials || "U"}</div>
          <div>
            <div style={S.footerName}>{me.tenant_name || "Cabinet"}</div>
            <div style={S.footerPlan}>{planLabel} · 149€/mois</div>
          </div>
        </div>
      </aside>

      <div
        className={`client-shell-overlay ${sbOpen ? "open" : ""}`}
        onClick={closeSidebar}
        aria-hidden="true"
      />

      <div className="client-shell-main" style={{ ...S.main, paddingTop: impersonation ? 44 : 0 }}>
        <header style={S.topbar}>
          <div>
            <h1 style={S.title}>{routeInfo.title}</h1>
            <p style={S.subtitle}>{sub}</p>
          </div>
          <div style={S.topbarRight}>
            <div style={S.liveBadge}>
              <Dot color={TEAL} size={8} />
              <span style={{ fontSize: 11, color: TEALX, fontWeight: 700 }}>IA ACTIVE</span>
            </div>
            <div style={S.clockBox}>{clockLabel}</div>
            <div style={S.bellBtn}>
              <span style={{ fontSize: 14 }}>🔔</span>
              {urgentBadge > 0 && <div style={S.bellDot} />}
            </div>
            <button type="button" className="client-shell-hamburger" style={S.hamburger} onClick={() => setSbOpen(true)} aria-label="Menu">
              ☰
            </button>
          </div>
        </header>

        <div style={S.content}>
          {showWelcomeSecurityBanner && (
            <div
              style={{
                margin: "0 24px",
                borderRadius: 12,
                border: "1px solid #fcd34d",
                background: "#fffbeb",
                padding: "12px 16px",
                fontSize: 14,
                color: "#92400e",
              }}
              role="alert"
            >
              Votre compte utilise un mot de passe temporaire. Changez-le dès maintenant dans <code>Paramètres</code> pour sécuriser l'accès à votre espace.
            </div>
          )}

          <div style={S.outletWrap}>
            <Outlet context={{ me, dashboard }} />
          </div>
        </div>
      </div>
    </div>
  );
}

const S = {
  root: {
    display: "flex",
    minHeight: "100vh",
    background: "#f0f4f8",
    color: NAVY,
    fontFamily: "'DM Sans', sans-serif",
  },
  sidebar: {
    width: 220,
    minWidth: 220,
    background: "#fff",
    borderRight: "1px solid #e2e8f0",
    display: "flex",
    flexDirection: "column",
    position: "fixed",
    left: 0,
    bottom: 0,
    zIndex: 40,
  },
  brand: {
    display: "flex",
    alignItems: "center",
    gap: 10,
    padding: "18px 16px",
    borderBottom: "1px solid #f1f5f9",
  },
  brandIcon: {
    width: 32,
    height: 32,
    borderRadius: 8,
    background: "linear-gradient(135deg,#00d4a0,#00a87d)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
  },
  brandName: { fontSize: 13, fontWeight: 700, color: NAVY },
  brandSub: { fontSize: 9, color: TEALX, fontWeight: 700, letterSpacing: 1.5 },
  navWrap: { padding: "8px 8px", display: "flex", flexDirection: "column", gap: 1 },
  navWrapSecondary: { padding: "0 8px", display: "flex", flexDirection: "column", gap: 1 },
  paramTitle: { fontSize: 9, color: "#cbd5e1", letterSpacing: 1.8, fontWeight: 700, padding: "12px 18px 4px" },
  assistantCard: {
    margin: "auto 10px 10px",
    background: "linear-gradient(135deg,rgba(0,212,160,.07),rgba(0,212,160,.02))",
    border: "1px solid rgba(0,212,160,.2)",
    borderRadius: 11,
    padding: "11px 12px",
  },
  assistantTag: { fontSize: 9, color: TEALX, letterSpacing: 1.5, fontWeight: 700, marginBottom: 9 },
  assistantInner: { display: "flex", alignItems: "center", gap: 10 },
  assistantAvatar: {
    width: 44,
    height: 44,
    borderRadius: "50%",
    objectFit: "cover",
    border: "2px solid #00d4a0",
    display: "block",
  },
  assistantFallback: {
    width: 44,
    height: 44,
    borderRadius: "50%",
    background: "linear-gradient(135deg,#00d4a0,#60a5fa)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: 16,
    fontWeight: 800,
    color: NAVY,
    border: "2px solid #00d4a0",
    textTransform: "uppercase",
  },
  assistantOnline: {
    position: "absolute",
    bottom: 1,
    right: 1,
    width: 10,
    height: 10,
    borderRadius: "50%",
    background: "#00d4a0",
    border: "2px solid #fff",
  },
  assistantName: { fontSize: 14, fontWeight: 800, color: NAVY },
  assistantMeta: { fontSize: 10, color: "#64748b", marginTop: 2 },
  assistantStatus: { display: "flex", alignItems: "center", gap: 4, marginTop: 4, fontSize: 10, color: TEALX, fontWeight: 600 },
  sidebarFooter: {
    padding: "12px 16px",
    borderTop: "1px solid #f1f5f9",
    display: "flex",
    alignItems: "center",
    gap: 9,
  },
  footerAvatar: {
    width: 28,
    height: 28,
    borderRadius: "50%",
    background: "linear-gradient(135deg,#00d4a0,#60a5fa)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: 11,
    fontWeight: 800,
    color: NAVY,
    textTransform: "uppercase",
  },
  footerName: { fontSize: 12, fontWeight: 700, color: NAVY },
  footerPlan: { fontSize: 10, color: TEALX, fontWeight: 700 },
  main: {
    marginLeft: 220,
    width: "calc(100% - 220px)",
    minHeight: "100vh",
    display: "flex",
    flexDirection: "column",
    minWidth: 0,
    flex: 1,
  },
  topbar: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "14px 24px",
    background: "#fff",
    borderBottom: "1px solid #f1f5f9",
    flexShrink: 0,
    position: "sticky",
    top: 0,
    zIndex: 20,
  },
  title: { fontSize: 18, fontWeight: 700, color: NAVY, margin: 0 },
  subtitle: { fontSize: 11, color: "#94a3b8", margin: "1px 0 0" },
  topbarRight: { display: "flex", alignItems: "center", gap: 10 },
  liveBadge: {
    display: "flex",
    alignItems: "center",
    gap: 6,
    background: "rgba(0,212,160,.08)",
    border: "1px solid rgba(0,212,160,.2)",
    borderRadius: 20,
    padding: "5px 11px",
  },
  clockBox: {
    background: "#f8fafc",
    border: "1px solid #e2e8f0",
    borderRadius: 7,
    padding: "5px 10px",
    fontSize: 12,
    fontFamily: "monospace",
    fontWeight: 700,
    color: NAVY,
  },
  bellBtn: {
    position: "relative",
    width: 32,
    height: 32,
    borderRadius: 7,
    background: "#fff",
    border: "1px solid #e2e8f0",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    cursor: "pointer",
  },
  bellDot: {
    position: "absolute",
    top: 4,
    right: 4,
    width: 6,
    height: 6,
    borderRadius: "50%",
    background: "#dc2626",
    border: "2px solid #fff",
  },
  hamburger: {
    display: "none",
    width: 32,
    height: 32,
    borderRadius: 7,
    border: "1px solid #e2e8f0",
    background: "#fff",
    alignItems: "center",
    justifyContent: "center",
    cursor: "pointer",
    color: NAVY,
    fontSize: 14,
  },
  content: {
    flex: 1,
    minHeight: 0,
    display: "flex",
    flexDirection: "column",
    overflow: "hidden",
    background: "#f0f4f8",
  },
  outletWrap: {
    flex: 1,
    minHeight: 0,
    display: "flex",
    flexDirection: "column",
    overflow: "hidden",
  },
};

const SHELL_CSS = `
  @media (max-width: 1024px) {
    .client-shell-sidebar {
      transform: translateX(-100%);
      transition: transform .22s ease;
      box-shadow: 0 20px 50px rgba(13,27,46,.16);
    }
    .client-shell-sidebar.open {
      transform: translateX(0);
    }
    .client-shell-main {
      margin-left: 0 !important;
      width: 100% !important;
    }
    .client-shell-overlay {
      position: fixed;
      inset: 0;
      background: rgba(15,23,42,.35);
      z-index: 30;
      opacity: 0;
      pointer-events: none;
      transition: opacity .2s ease;
    }
    .client-shell-overlay.open {
      opacity: 1;
      pointer-events: auto;
    }
    .client-shell-hamburger {
      display: flex !important;
    }
  }

  @media (min-width: 1025px) {
    .client-shell-overlay {
      display: none;
    }
  }

  .client-shell-nav-item:hover {
    background: #f8fafc !important;
    color: ${NAVY} !important;
  }
`;
