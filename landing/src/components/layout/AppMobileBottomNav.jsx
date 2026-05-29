import { NavLink, useLocation, useNavigate } from "react-router-dom";

export default function AppMobileBottomNav({ navItems, demandBadge, colors }) {
  const location = useLocation();
  const navigate = useNavigate();

  return (
    <nav className="uwi-mobile-nav">
      {navItems.filter((item) => item.to !== "/app/profile").map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end}
          style={{ textDecoration: "none" }}
          onClick={(event) => {
            if (
              item.to === "/app/patient-dashboard" &&
              location.pathname.startsWith("/app/patient-dashboard") &&
              location.search.includes("phone=")
            ) {
              event.preventDefault();
              navigate("/app/patient-dashboard", { replace: true });
            }
          }}
        >
          {({ isActive }) => (
            <div
              style={{
                position: "relative",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                gap: 3,
                borderRadius: 10,
                padding: "6px 4px",
                color: isActive ? colors.teal : "#64748B",
                background: isActive ? colors.tealSoft : "transparent",
                fontSize: 10,
                fontWeight: 700,
              }}
            >
              <span style={{ fontSize: 14 }}>{item.icon}</span>
              <span>{item.label}</span>
              {item.to === "/app/demandes" && demandBadge > 0 ? (
                <span
                  style={{
                    position: "absolute",
                    top: 2,
                    right: 8,
                    minWidth: 14,
                    height: 14,
                    borderRadius: 999,
                    background: colors.teal,
                    color: "#fff",
                    display: "inline-flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: 9,
                    fontWeight: 800,
                    padding: "0 3px",
                  }}
                >
                  {demandBadge}
                </span>
              ) : null}
            </div>
          )}
        </NavLink>
      ))}
    </nav>
  );
}
