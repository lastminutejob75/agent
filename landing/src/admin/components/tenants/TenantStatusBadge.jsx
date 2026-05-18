import { T } from "../../theme.js";

const STYLE = {
  base: {
    display: "inline-flex",
    alignItems: "center",
    padding: "2px 10px",
    borderRadius: 999,
    fontSize: 11,
    fontWeight: 800,
    border: "1px solid transparent",
  },
};

export default function TenantStatusBadge({ status }) {
  const st = String(status || "active").toLowerCase();
  let bg = "#F2F4F7";
  let color = T.textMuted;
  let border = `${T.border}`;
  if (st === "active") {
    bg = "#EAF8F0";
    color = T.green;
    border = `${T.green}33`;
  } else if (st === "suspended") {
    bg = T.redLight;
    color = T.red;
    border = `${T.red}44`;
  } else if (st === "pending_payment" || st === "inactive") {
    bg = T.orangeLight;
    color = T.orange;
    border = `${T.orange}44`;
  }
  return (
    <span style={{ ...STYLE.base, background: bg, color, border }}>
      {status || "—"}
    </span>
  );
}
