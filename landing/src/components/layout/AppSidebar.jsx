import { NavLink } from "react-router-dom";

function ShellItem({ to, icon, label, end = false, badge = null, onNavigate, colors }) {
  return (
    <NavLink to={to} end={end} onClick={onNavigate} style={{ textDecoration: "none" }}>
      {({ isActive }) => (
        <div
          className="uwi-shell-item"
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            borderRadius: 12,
            padding: "10px 12px",
            fontSize: 13,
            fontWeight: 700,
            color: isActive ? "#007C84" : colors.title,
            background: isActive ? colors.tealSoft : "transparent",
            border: isActive ? "1px solid #BFE9EC" : "1px solid transparent",
            transition: "all .15s ease",
          }}
        >
          <span style={{ fontSize: 14, width: 16, textAlign: "center" }}>{icon}</span>
          <span style={{ flex: 1 }}>{label}</span>
          {badge ? (
            <span
              style={{
                minWidth: 18,
                height: 18,
                borderRadius: 999,
                background: colors.teal,
                color: "#fff",
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 10,
                fontWeight: 800,
                padding: "0 6px",
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

export default function AppSidebar({
  navItems,
  demandBadge,
  sidebarOpen,
  layoutTopOffset,
  navigate,
  onClose,
  initials,
  tenantName,
  onLogout,
  styles,
  colors,
}) {
  const S = styles;
  return (
    <aside className={`uwi-sidebar ${sidebarOpen ? "open" : ""}`} style={{ top: layoutTopOffset }}>
      <button
        type="button"
        onClick={() => {
          navigate("/app");
          onClose();
        }}
        style={S.brandBtn}
      >
        <span style={S.brandName}>UWi.</span>
      </button>

      <nav style={S.navBlock}>
        {navItems.map((item) => (
          <ShellItem
            key={item.to}
            to={item.to}
            icon={item.icon}
            label={item.label}
            end={item.end}
            badge={item.to === "/app/demandes" ? demandBadge : null}
            onNavigate={onClose}
            colors={colors}
          />
        ))}
      </nav>

      <div style={S.sidebarFooter}>
        <div style={S.avatar}>{initials || "U"}</div>
        <div style={{ minWidth: 0 }}>
          <div style={S.footerName}>{tenantName || "Cabinet"}</div>
          <div style={S.footerSub}>Cabinet médical</div>
        </div>
        <button type="button" style={S.logoutButton} onClick={onLogout} title="Déconnexion" aria-label="Se déconnecter">
          ↪
        </button>
      </div>
    </aside>
  );
}
