import { useEffect, useState } from "react";
import { useNavigate, useLocation, Outlet } from "react-router-dom";
import {
  LayoutDashboard,
  Users,
  UserPlus,
  AlertTriangle,
  CreditCard,
  LogOut,
  Activity,
  FileSearch,
  Menu,
  X,
} from "lucide-react";
import { useAdminAuth } from "./AdminAuthProvider";
import { adminApi } from "../lib/adminApi.js";
import { T, font, keyframes, radius } from "./theme.js";

/**
 * Sidebar admin light mode (CdC v1.0).
 *  - Section PILOTAGE   : Dashboard / Clients / Leads
 *  - Section EXPLOITATION : Billing / Operations / Quality / Monitoring / Audit log
 *
 * Design align sur le dashboard client (sidebar 214px, fond blanc, accent teal).
 * "Demandes patients" appartient au dashboard client (/app/demandes), pas a l'admin.
 * AdminTenantNew (route /admin/tenants/new) reste accessible depuis le bouton
 * "Creer un client" de la liste tenants, mais n'apparait pas dans la sidebar.
 */

const NAV_GROUPS = [
  {
    label: "Pilotage",
    items: [
      { icon: LayoutDashboard, label: "Tableau de bord", path: "/admin", end: true },
      { icon: Users, label: "Clients", path: "/admin/tenants" },
      { icon: UserPlus, label: "Prospects", path: "/admin/leads", badgeKey: "newLeads" },
    ],
  },
  {
    label: "Exploitation",
    items: [
      { icon: CreditCard, label: "Facturation", path: "/admin/billing" },
      { icon: AlertTriangle, label: "Opérations", path: "/admin/operations" },
      { icon: FileSearch, label: "Journal d’audit", path: "/admin/audit-log" },
    ],
  },
];

const SIDEBAR_WIDTH = 232;

// ── Sous-composants ─────────────────────────────────────────────────────────

function SidebarHeader() {
  return (
    <div style={{ padding: "0 20px 20px", borderBottom: `1px solid ${T.border}` }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <div
          style={{
            width: 34,
            height: 34,
            borderRadius: radius.md,
            background: `linear-gradient(135deg, ${T.teal}, ${T.tealDark})`,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 13,
            fontWeight: 800,
            color: "#FFFFFF",
            fontFamily: font.display,
            letterSpacing: -0.3,
          }}
        >
          UWi
        </div>
        <div style={{ minWidth: 0 }}>
          <div
            style={{
              fontSize: 14,
              fontWeight: 700,
              color: T.text,
            }}
          >
            UWi Admin
          </div>
          <div style={{ fontSize: 11, color: T.textMuted }}>Pilotage et exploitation</div>
        </div>
      </div>
    </div>
  );
}

function NavItem({ item, badgeValue, isActive, onClick }) {
  const Icon = item.icon;
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
        padding: "8px 10px",
        width: "100%",
        borderRadius: radius.md,
        marginBottom: 2,
        cursor: "pointer",
        background: isActive ? T.tealLight : "transparent",
        border: `1px solid ${isActive ? "rgba(0,156,164,0.2)" : "transparent"}`,
        color: isActive ? T.teal : T.textSecondary,
        transition: "background 0.15s, color 0.15s",
        fontFamily: font.body,
        fontSize: 13,
        fontWeight: isActive ? 600 : 500,
        textAlign: "left",
      }}
      onMouseEnter={(e) => {
        if (!isActive) {
          e.currentTarget.style.background = T.bgCardHover;
          e.currentTarget.style.color = T.text;
        }
      }}
      onMouseLeave={(e) => {
        if (!isActive) {
          e.currentTarget.style.background = "transparent";
          e.currentTarget.style.color = T.textSecondary;
        }
      }}
    >
      <Icon size={16} strokeWidth={isActive ? 2.4 : 2} style={{ flexShrink: 0 }} />
      <span style={{ flex: 1 }}>{item.label}</span>
      {badgeValue > 0 ? (
        <span
          style={{
            background: T.red,
            color: "#FFFFFF",
            fontSize: 10,
            fontWeight: 700,
            minWidth: 18,
            height: 18,
            borderRadius: 9,
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            padding: "0 5px",
          }}
        >
          {badgeValue > 99 ? "99+" : badgeValue}
        </span>
      ) : null}
    </button>
  );
}

function NavGroup({ group, badges, currentPath, onNavigate }) {
  return (
    <div style={{ marginBottom: 18 }}>
      <div
        style={{
          fontSize: 10,
          color: T.textMuted,
          fontWeight: 700,
          letterSpacing: "0.08em",
          textTransform: "uppercase",
          padding: "0 10px 8px",
        }}
      >
        {group.label}
      </div>
      {group.items.map((item) => {
        const isActive = item.end
          ? currentPath === item.path
          : currentPath === item.path || currentPath.startsWith(item.path + "/");
        const badgeValue = item.badgeKey ? badges[item.badgeKey] : 0;
        return (
          <NavItem
            key={item.label}
            item={item}
            badgeValue={badgeValue}
            isActive={isActive}
            onClick={() => onNavigate(item.path)}
          />
        );
      })}
    </div>
  );
}

function SidebarFooter({ email, onLogout, onNavigate }) {
  return (
    <div style={{ padding: "16px 20px", borderTop: `1px solid ${T.border}` }}>
      <button
        type="button"
        onClick={() => onNavigate("/admin/tenants/new")}
        style={{
          width: "100%",
          marginBottom: 12,
          padding: "10px 12px",
          border: "none",
          borderRadius: radius.md,
          background: T.teal,
          color: "#fff",
          cursor: "pointer",
          fontFamily: font.body,
          fontSize: 12,
          fontWeight: 800,
        }}
      >
        + Créer un client
      </button>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          fontSize: 11,
          color: T.textSecondary,
          marginBottom: 12,
        }}
      >
        <Activity size={12} color={T.green} />
        Système opérationnel
      </div>
      <div
        style={{
          background: T.bgSubtle,
          borderRadius: radius.md,
          padding: "8px 12px",
          marginBottom: 8,
          border: `1px solid ${T.border}`,
        }}
      >
        <div style={{ fontSize: 10, color: T.textMuted, marginBottom: 2 }}>Connecté</div>
        <div
          style={{
            fontSize: 12,
            fontWeight: 600,
            color: T.text,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {email || "—"}
        </div>
      </div>
      <button
        type="button"
        onClick={onLogout}
        style={{
          width: "100%",
          padding: "8px 12px",
          fontSize: 12,
          fontWeight: 600,
          background: T.bgCard,
          border: `1px solid ${T.borderDark}`,
          borderRadius: radius.md,
          color: T.textSecondary,
          cursor: "pointer",
          fontFamily: font.body,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 6,
          transition: "background 0.15s",
        }}
        onMouseEnter={(e) => (e.currentTarget.style.background = T.bgCardHover)}
        onMouseLeave={(e) => (e.currentTarget.style.background = T.bgCard)}
      >
        <LogOut size={13} />
        Déconnexion
      </button>
    </div>
  );
}

function SidebarContent({ currentPath, badges, onNavigate, email, onLogout }) {
  return (
    <>
      <SidebarHeader />
      <nav style={{ padding: "16px 12px", flex: 1, overflowY: "auto" }}>
        {NAV_GROUPS.map((group) => (
          <NavGroup
            key={group.label}
            group={group}
            badges={badges}
            currentPath={currentPath}
            onNavigate={onNavigate}
          />
        ))}
      </nav>
      <SidebarFooter email={email} onLogout={onLogout} onNavigate={onNavigate} />
    </>
  );
}

// ── Layout principal ────────────────────────────────────────────────────────

export default function AdminLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const { logout, me } = useAdminAuth();
  const [newLeadsCount, setNewLeadsCount] = useState(0);
  const [isMobile, setIsMobile] = useState(() => {
    if (typeof window === "undefined") return false;
    return window.innerWidth <= 1024;
  });
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  useEffect(() => {
    const refreshLeadCount = () => {
      adminApi
        .leadsCountNew()
        .then((r) => setNewLeadsCount(r?.count ?? 0))
        .catch(() => {});
    };
    refreshLeadCount();
    window.addEventListener("focus", refreshLeadCount);
    const timer = window.setInterval(refreshLeadCount, 5 * 60 * 1000);
    return () => {
      window.removeEventListener("focus", refreshLeadCount);
      window.clearInterval(timer);
    };
  }, [location.pathname]);

  useEffect(() => {
    if (typeof window === "undefined") return undefined;
    const onResize = () => setIsMobile(window.innerWidth <= 1024);
    onResize();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  useEffect(() => {
    setMobileNavOpen(false);
  }, [location.pathname]);

  const badges = { newLeads: newLeadsCount };

  const goTo = (path) => {
    navigate(path);
    setMobileNavOpen(false);
  };

  return (
    <div
      style={{
        display: "flex",
        flexDirection: isMobile ? "column" : "row",
        minHeight: "100vh",
        width: "100%",
        maxWidth: "100vw",
        overflowX: "hidden",
        background: T.bgPage,
        fontFamily: font.body,
        color: T.text,
      }}
    >
      <style>{`
        ${keyframes}
        * { box-sizing: border-box; }
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-thumb { background: ${T.borderDark}; border-radius: 3px; }
        ::-webkit-scrollbar-track { background: transparent; }
      `}</style>

      {isMobile ? (
        <>
          <div
            style={{
              position: "sticky",
              top: 0,
              zIndex: 40,
              height: 56,
              display: "flex",
              alignItems: "center",
              gap: 10,
              padding: "0 12px",
              borderBottom: `1px solid ${T.border}`,
              background: T.bgCard,
            }}
          >
            <button
              type="button"
              onClick={() => setMobileNavOpen((v) => !v)}
              aria-label={mobileNavOpen ? "Fermer le menu" : "Ouvrir le menu"}
              style={{
                width: 36,
                height: 36,
                borderRadius: 10,
                border: `1px solid ${T.border}`,
                background: "#fff",
                color: T.text,
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                cursor: "pointer",
              }}
            >
              {mobileNavOpen ? <X size={18} /> : <Menu size={18} />}
            </button>
            <div style={{ minWidth: 0 }}>
              <div style={{ fontSize: 15, fontWeight: 700, color: T.text, lineHeight: 1.1 }}>UWi Admin</div>
              <div style={{ fontSize: 11, color: T.textMuted, marginTop: 2 }}>Pilotage et exploitation</div>
            </div>
          </div>

          <main style={{ flex: 1, overflowY: "auto", minWidth: 0, background: T.bgPage }}>
            <Outlet />
          </main>

          {mobileNavOpen ? (
            <button
              type="button"
              aria-label="Fermer le menu"
              onClick={() => setMobileNavOpen(false)}
              style={{
                position: "fixed",
                inset: 0,
                border: "none",
                background: "rgba(7,26,51,0.45)",
                zIndex: 49,
                cursor: "pointer",
              }}
            />
          ) : null}

          <aside
            style={{
              width: "min(86vw, 320px)",
              maxWidth: 320,
              background: T.bgCard,
              borderRight: `1px solid ${T.border}`,
              display: "flex",
              flexDirection: "column",
              padding: "16px 0 10px",
              position: "fixed",
              top: 0,
              left: 0,
              height: "100vh",
              zIndex: 50,
              boxShadow: "0 20px 40px rgba(0,0,0,0.18)",
              transform: mobileNavOpen ? "translateX(0)" : "translateX(-105%)",
              transition: "transform 180ms ease",
            }}
          >
            <SidebarContent
              currentPath={location.pathname}
              badges={badges}
              onNavigate={goTo}
              email={me?.email}
              onLogout={() => {
                setMobileNavOpen(false);
                logout();
              }}
            />
          </aside>
        </>
      ) : (
        <>
          <aside
            style={{
              width: SIDEBAR_WIDTH,
              flexShrink: 0,
              background: T.bgCard,
              borderRight: `1px solid ${T.border}`,
              display: "flex",
              flexDirection: "column",
              padding: "20px 0",
              position: "sticky",
              top: 0,
              height: "100vh",
            }}
          >
            <SidebarContent
              currentPath={location.pathname}
              badges={badges}
              onNavigate={navigate}
              email={me?.email}
              onLogout={logout}
            />
          </aside>

          <main style={{ flex: 1, overflowY: "auto", minWidth: 0, background: T.bgPage }}>
            <Outlet />
          </main>
        </>
      )}
    </div>
  );
}
