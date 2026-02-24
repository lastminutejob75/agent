import { useState, useEffect } from "react";
import { Outlet, NavLink, useLocation } from "react-router-dom";
import { api, getTenantToken, clearTenantToken, isTenantUnauthorized } from "../lib/api.js";
import { getImpersonation, setImpersonation } from "./Impersonate";
import "./ClientDashboard.css";

const ROUTES = {
  "/app": { title: "Vue d'ensemble", sub: "" },
  "/app/appels": { title: "Journal des appels", sub: "" },
  "/app/agenda": { title: "Mon agenda", sub: "" },
  "/app/actions": { title: "Actions en attente", sub: "" },
  "/app/facturation": { title: "Facturation", sub: "" },
  "/app/profil": { title: "Mon profil", sub: "" },
  "/app/config": { title: "Configuration IA", sub: "" },
  "/app/status": { title: "Statut", sub: "" },
  "/app/settings": { title: "Paramètres", sub: "" },
  "/app/rgpd": { title: "RGPD", sub: "" },
};

function NavItem({ to, children, badge }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) => `sb-a ${isActive ? "on" : ""}`}
      end={to === "/app"}
    >
      {children}
      {badge != null && badge > 0 && (
        <span className={`sb-badge ${to === "/app/actions" ? "b-ora" : "b-red"}`}>
          {badge}
        </span>
      )}
    </NavLink>
  );
}

export default function AppLayout() {
  const [me, setMe] = useState(null);
  const [err, setErr] = useState(null);
  const [loading, setLoading] = useState(true);
  const [dashboard, setDashboard] = useState(null);
  const location = useLocation();
  const [sbOpen, setSbOpen] = useState(false);

  useEffect(() => {
    api
      .tenantMe()
      .then((m) => {
        setMe(m);
        return api.tenantDashboard().then(setDashboard).catch(() => setDashboard(null));
      })
      .catch((e) => {
        if (isTenantUnauthorized(e)) {
          setImpersonation(null);
          clearTenantToken();
          window.location.href = "/";
          return;
        }
        setErr(e.message || "Erreur");
      })
      .finally(() => setLoading(false));
  }, []);

  const handleLogout = () => {
    setImpersonation(null);
    clearTenantToken();
    window.location.href = "/";
  };

  const closeSb = () => setSbOpen(false);

  if (loading) {
    return (
      <div className="dash" style={{ display: "flex", minHeight: "100vh", alignItems: "center", justifyContent: "center" }}>
        <p style={{ color: "var(--muted)" }}>Chargement...</p>
      </div>
    );
  }
  if (err) {
    return (
      <div className="dash" style={{ padding: "2rem", color: "var(--red)" }}>
        {err}
      </div>
    );
  }
  if (!me) return null;

  const path = location.pathname;
  const routeInfo = ROUTES[path] || { title: "Mon Cabinet", sub: "" };
  const sub = routeInfo.sub || (path === "/app" ? new Date().toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long", year: "numeric" }) : "");
  const initials = (me.tenant_name || "U")
    .split(/\s+/)
    .map((w) => w[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);
  const actionsCount = 0;
  const callsBadge = dashboard?.counters_7d?.calls_total ?? 0;

  return (
    <div className="dash">
      {getImpersonation() && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            zIndex: 60,
            background: "var(--red-lt)",
            borderBottom: "1px solid var(--red-brd)",
            padding: "10px 20px",
            fontSize: "13px",
            fontWeight: 600,
            color: "var(--red)",
          }}
          role="alert"
        >
          Mode admin – vous visualisez le compte de <strong>{getImpersonation().tenant_name}</strong>
        </div>
      )}

      <aside className={`sb ${sbOpen ? "open" : ""}`} id="cd-sb">
        <div className="sb-logo">
          <div className="sb-gem">
            <svg viewBox="0 0 24 24" width="20" height="20" stroke="#fff" fill="none" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M4 8h16M4 12h10" />
              <circle cx="17" cy="15" r="4" />
              <path d="M15.5 15h1.5" />
            </svg>
          </div>
          <div>
            <div className="sb-name">UWi Medical</div>
            <div className="sb-tag">IA Secrétariat</div>
          </div>
        </div>
        <nav className="sb-nav">
          <NavItem to="/app">Vue d'ensemble</NavItem>
          <NavItem to="/app/appels" badge={callsBadge > 0 ? callsBadge : null}>Appels</NavItem>
          <NavItem to="/app/agenda">Agenda</NavItem>
          <NavItem to="/app/actions" badge={actionsCount}>Actions</NavItem>
          <div className="sb-cat">Paramètres</div>
          <NavItem to="/app/facturation">Facturation</NavItem>
          <NavItem to="/app/profil">Mon profil</NavItem>
          <NavItem to="/app/config">Config IA</NavItem>
          <NavLink to="/app/status" className={({ isActive }) => `sb-a ${isActive ? "on" : ""}`}>Statut</NavLink>
          <NavLink to="/app/rgpd" className={({ isActive }) => `sb-a ${isActive ? "on" : ""}`}>RGPD</NavLink>
          <NavLink to="/app/settings" className={({ isActive }) => `sb-a ${isActive ? "on" : ""}`}>Paramètres</NavLink>
          <button type="button" className="sb-a" onClick={handleLogout} style={{ width: "100%", textAlign: "left", border: "none", background: "none", font: "inherit" }}>Déconnexion</button>
        </nav>
        <div className="sb-foot">
          <div className="doc-pill">
            <div className="doc-av">{initials}</div>
            <div>
              <div className="doc-nm">{me.tenant_name || "Mon Cabinet"}</div>
              <div className="doc-pl">Growth · 149€/mois</div>
            </div>
            <svg width="13" height="13" viewBox="0 0 24 24" stroke="rgba(255,255,255,.2)" fill="none" strokeWidth="2.5" strokeLinecap="round">
              <polyline points="9 18 15 12 9 6" />
            </svg>
          </div>
        </div>
      </aside>

      <div className={`sb-ov ${sbOpen ? "open" : ""}`} onClick={closeSb} aria-hidden="true" />

      <main className="main">
        <header className="topbar">
          <div>
            <div className="tb-title" id="cd-tb-title">{routeInfo.title}</div>
            <div className="tb-sub" id="cd-tb-sub">{sub}</div>
          </div>
          <div className="tb-right">
            <div className="tb-btn" style={{ position: "relative" }}>
              <svg viewBox="0 0 24 24" width="16" height="16" stroke="var(--body)" fill="none" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9" />
                <path d="M13.73 21a2 2 0 01-3.46 0" />
              </svg>
              <div className="notif-dot" />
            </div>
            <button type="button" className="tb-btn tb-ham" onClick={() => setSbOpen(true)} aria-label="Menu">
              <svg viewBox="0 0 24 24" width="16" height="16" stroke="var(--body)" fill="none" strokeWidth="2">
                <line x1="3" y1="6" x2="21" y2="6" />
                <line x1="3" y1="12" x2="21" y2="12" />
                <line x1="3" y1="18" x2="21" y2="18" />
              </svg>
            </button>
          </div>
        </header>

        <Outlet context={{ me, dashboard }} />
      </main>

      <nav className="bnav">
        <div className="bnav-in">
          <NavLink to="/app" className={({ isActive }) => `bn ${isActive ? "on" : ""}`} onClick={closeSb}>
            <svg viewBox="0 0 24 24" width="22" height="22" stroke="currentColor" fill="none" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z" />
              <polyline points="9 22 9 12 15 12 15 22" />
            </svg>
            <span className="bn-lbl">Accueil</span>
          </NavLink>
          <NavLink to="/app/appels" className={({ isActive }) => `bn ${isActive ? "on" : ""}`} style={{ position: "relative" }} onClick={closeSb}>
            <svg viewBox="0 0 24 24" width="22" height="22" stroke="currentColor" fill="none" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07A19.5 19.5 0 013.07 9.8 19.79 19.79 0 01.22 1.18 2 2 0 012.22 0h3a2 2 0 012 1.72c.127.96.361 1.903.7 2.81a2 2 0 01-.45 2.11L6.91 7.91a16 16 0 006.16 6.16l1.27-.72a2 2 0 012.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0122 16.92z" />
            </svg>
            <span className="bn-lbl">Appels</span>
            {callsBadge > 0 && <div className="bn-dot" />}
          </NavLink>
          <NavLink to="/app/agenda" className={({ isActive }) => `bn ${isActive ? "on" : ""}`} onClick={closeSb}>
            <svg viewBox="0 0 24 24" width="22" height="22" stroke="currentColor" fill="none" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="4" width="18" height="18" rx="2" />
              <line x1="16" y1="2" x2="16" y2="6" />
              <line x1="8" y1="2" x2="8" y2="6" />
              <line x1="3" y1="10" x2="21" y2="10" />
            </svg>
            <span className="bn-lbl">Agenda</span>
          </NavLink>
          <NavLink to="/app/profil" className={({ isActive }) => `bn ${isActive ? "on" : ""}`} onClick={closeSb}>
            <svg viewBox="0 0 24 24" width="22" height="22" stroke="currentColor" fill="none" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="8" r="4" />
              <path d="M4 20c0-4 3.6-7 8-7s8 3 8 7" />
            </svg>
            <span className="bn-lbl">Profil</span>
          </NavLink>
        </div>
      </nav>
    </div>
  );
}
