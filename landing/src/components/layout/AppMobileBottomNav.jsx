import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { scrollWindowToTop } from "../../lib/scrollToTop.js";

export default function AppMobileBottomNav({ navItems, demandBadge, colors }) {
  const location = useLocation();
  const navigate = useNavigate();

  function handleNavClick(event, item) {
    const onPatientList =
      item.to === "/app/patient-dashboard" &&
      location.pathname.startsWith("/app/patient-dashboard") &&
      location.search.includes("phone=");

    if (onPatientList) {
      event.preventDefault();
      scrollWindowToTop();
      navigate("/app/patient-dashboard", { replace: true });
      return;
    }

    const targetPath = item.to.split("?")[0];
    const isSamePath = location.pathname === targetPath || (item.end && location.pathname === item.to);
    if (!isSamePath) {
      scrollWindowToTop();
    }
  }

  return (
    <nav className="uwi-mobile-nav">
      {navItems.filter((item) => item.to !== "/app/profile").map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end}
          style={{ textDecoration: "none" }}
          onClick={(event) => handleNavClick(event, item)}
        >
          {({ isActive }) => (
            <div
              style={{
                position: "relative",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                gap: 2,
                borderRadius: 10,
                padding: "5px 1px",
                color: isActive ? colors.teal : "#64748B",
                background: isActive ? colors.tealSoft : "transparent",
                fontSize: 9,
                fontWeight: 700,
                lineHeight: 1.1,
                minWidth: 0,
                width: "100%",
              }}
            >
              <span style={{ fontSize: 14, lineHeight: 1 }}>{item.icon}</span>
              <span
                style={{
                  maxWidth: "100%",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {item.label}
              </span>
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
