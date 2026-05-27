import UWIDashboard from "./UWIDashboard";
import LogsPanel from "../components/dashboard/LogsPanel.jsx";
import MetricsPanel from "../components/dashboard/MetricsPanel.jsx";
import AuditLogPanel from "../components/dashboard/AuditLogPanel.jsx";
import SystemInfoPanel from "../components/dashboard/SystemInfoPanel.jsx";
import { T } from "../theme.js";

export default function AdminMonitoring() {
  return (
    <div style={{ background: T.bgPage, minHeight: "100vh", paddingBottom: 32 }}>
      <UWIDashboard title="Monitoring" showCreateButton={false} darkTheme />
      <div
        style={{
          maxWidth: 1280,
          margin: "0 auto",
          padding: "0 24px",
          marginTop: -16,
          display: "flex",
          flexDirection: "column",
          gap: 16,
        }}
      >
        <MetricsPanel />
        <SystemInfoPanel />
        <AuditLogPanel defaultLimit={100} />
        <LogsPanel defaultLimit={100} />
      </div>
    </div>
  );
}
