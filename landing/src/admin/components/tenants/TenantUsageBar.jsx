import { T } from "../../theme.js";

export default function TenantUsageBar({ used, included }) {
  const u = Number(used);
  const i = Number(included);
  const pct = i > 0 && Number.isFinite(u) ? Math.min(100, Math.round((u / i) * 100)) : null;
  const bar =
    pct == null ? T.teal : pct >= 90 ? T.red : pct >= 75 ? T.orange : T.teal;
  return (
    <div style={{ minWidth: 0 }}>
      <div style={{ fontSize: 11, fontWeight: 700, color: T.textMuted, marginBottom: 4 }}>
        {pct != null ? (
          <>
            {Math.round(u)} / {i} min · {pct}%
          </>
        ) : (
          <>Quota N/A</>
        )}
      </div>
      <div style={{ height: 8, borderRadius: 999, background: "#EAF0F6", overflow: "hidden" }}>
        <div style={{ height: "100%", width: pct != null ? `${pct}%` : 0, background: bar, borderRadius: 999 }} />
      </div>
    </div>
  );
}
