import { useState, useEffect } from "react";
import { useNavigate, useLocation, Outlet } from "react-router-dom";
import { useAdminAuth } from "./AdminAuthProvider";
import { adminApi } from "../lib/adminApi.js";

const C = {
  bg: "#0A1828",
  surface: "#0F2236",
  card: "#132840",
  border: "#1E3D56",
  accent: "#00E5A0",
  accentDim: "#00b87c",
  text: "#FFFFFF",
  muted: "#6B90A8",
};

const NAV_ITEMS = [
  { icon: "⬛", label: "Dashboard", path: "/admin" },
  { icon: "👥", label: "Clients", path: "/admin/tenants" },
  { icon: "🎯", label: "Leads", path: "/admin/leads" },
  { icon: "📞", label: "Appels", path: "/admin/calls" },
  { icon: "📡", label: "Monitoring", path: "/admin/monitoring" },
  { icon: "⚙️", label: "Operations", path: "/admin/operations" },
  { icon: "⭐", label: "Quality", path: "/admin/quality" },
  { icon: "📋", label: "Audit log", path: "/admin/audit" },
];

export default function AdminLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const { logout, me } = useAdminAuth();
  const [newLeadsCount, setNewLeadsCount] = useState(0);

  useEffect(() => {
    adminApi.leadsCountNew().then((r) => setNewLeadsCount(r?.count ?? 0)).catch(() => {});
  }, []);

  return (
    <div style={{ display: "flex", minHeight: "100vh", background: C.bg, fontFamily: "'DM Sans', sans-serif" }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&display=swap');
        * { box-sizing:border-box; }
        @keyframes uwi-pulse { 0%,100%{opacity:1} 50%{opacity:.4} }
        ::-webkit-scrollbar{width:4px} ::-webkit-scrollbar-thumb{background:${C.border};border-radius:2px}
      `}</style>

      {/* ── Sidebar unique ── */}
      <aside
        style={{
          width: 200,
          flexShrink: 0,
          background: C.surface,
          borderRight: `1px solid ${C.border}`,
          display: "flex",
          flexDirection: "column",
          padding: "20px 0",
          position: "sticky",
          top: 0,
          height: "100vh",
        }}
      >
        {/* Logo */}
        <div style={{ padding: "0 20px 24px", borderBottom: `1px solid ${C.border}` }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div
              style={{
                width: 32,
                height: 32,
                borderRadius: 8,
                background: `linear-gradient(135deg,${C.accent},${C.accentDim})`,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 13,
                fontWeight: 800,
                color: C.bg,
              }}
            >
              UWi
            </div>
            <div>
              <div style={{ fontSize: 13, fontWeight: 700, color: C.text }}>UWi Admin</div>
              <div style={{ fontSize: 10, color: C.muted }}>Pilotage & facturation</div>
            </div>
          </div>
        </div>

        {/* Nav */}
        <nav style={{ padding: "16px 10px", flex: 1 }}>
          <div
            style={{
              fontSize: 9,
              color: C.muted,
              fontWeight: 700,
              letterSpacing: 1.5,
              textTransform: "uppercase",
              padding: "0 10px",
              marginBottom: 10,
            }}
          >
            Navigation
          </div>
          {NAV_ITEMS.map((item) => {
            const isActive =
              location.pathname === item.path ||
              (item.path !== "/admin" && location.pathname.startsWith(item.path));
            return (
              <div
                key={item.label}
                onClick={() => navigate(item.path)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  padding: "9px 10px",
                  borderRadius: 10,
                  marginBottom: 2,
                  cursor: "pointer",
                  background: isActive ? "rgba(0,229,160,0.1)" : "transparent",
                  border: `1px solid ${isActive ? "rgba(0,229,160,0.2)" : "transparent"}`,
                  transition: "all 0.15s",
                }}
              >
                <span style={{ fontSize: 14, opacity: isActive ? 1 : 0.6 }}>{item.icon}</span>
                <span
                  style={{
                    fontSize: 13,
                    fontWeight: isActive ? 700 : 500,
                    color: isActive ? C.accent : C.muted,
                  }}
                >
                  {item.label}
                </span>
                {item.label === "Leads" && newLeadsCount > 0 && (
                  <span
                    style={{
                      marginLeft: "auto",
                      background: "#FFB347",
                      color: C.bg,
                      fontSize: 10,
                      fontWeight: 700,
                      minWidth: 18,
                      height: 18,
                      borderRadius: 9,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      padding: "0 4px",
                    }}
                  >
                    {newLeadsCount > 99 ? "99+" : newLeadsCount}
                  </span>
                )}
                {isActive && (
                  <div
                    style={{
                      marginLeft: item.label === "Leads" && newLeadsCount > 0 ? 4 : "auto",
                      width: 4,
                      height: 4,
                      borderRadius: "50%",
                      background: C.accent,
                    }}
                  />
                )}
              </div>
            );
          })}
        </nav>

        {/* Status + Compte */}
        <div style={{ padding: "16px 20px", borderTop: `1px solid ${C.border}` }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 11, color: C.muted, marginBottom: 12 }}>
            <div
              style={{
                width: 6,
                height: 6,
                borderRadius: "50%",
                background: C.accent,
                animation: "uwi-pulse 2s ease infinite",
              }}
            />
            Système opérationnel
          </div>
          <div
            style={{
              background: "rgba(107,144,168,0.1)",
              borderRadius: 8,
              padding: "8px 12px",
              marginBottom: 8,
            }}
          >
            <div style={{ fontSize: 10, color: C.muted }}>Connecté</div>
            <div
              style={{
                fontSize: 12,
                fontWeight: 600,
                color: C.text,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {me?.email || "—"}
            </div>
          </div>
          <button
            type="button"
            onClick={logout}
            style={{
              width: "100%",
              padding: "8px 12px",
              fontSize: 12,
              fontWeight: 600,
              background: "transparent",
              border: `1px solid ${C.border}`,
              borderRadius: 8,
              color: C.muted,
              cursor: "pointer",
              fontFamily: "inherit",
            }}
          >
            Déconnexion
          </button>
        </div>
      </aside>

      {/* ── Contenu des pages (injecté via Outlet) ── */}
      <main style={{ flex: 1, overflowY: "auto", minWidth: 0, background: C.bg }}>
        <Outlet />
      </main>
    </div>
  );
}
