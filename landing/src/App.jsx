import { Routes, Route, Navigate } from "react-router-dom";
import UwiLanding from "./components/UwiLanding";
import Onboarding from "./pages/Onboarding";
import Admin from "./pages/Admin";
import AdminTenant from "./pages/AdminTenant";
import AdminTenantDashboard from "./pages/AdminTenantDashboard";
import Login from "./pages/Login";
import AuthCallback from "./pages/AuthCallback";
import AppLayout from "./pages/AppLayout";
import AppDashboard from "./pages/AppDashboard";
import AppStatus from "./pages/AppStatus";
import AppSettings from "./pages/AppSettings";
import AppRgpd from "./pages/AppRgpd";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<UwiLanding />} />
      <Route path="/onboarding" element={<Onboarding />} />
      <Route path="/login" element={<Login />} />
      <Route path="/auth/callback" element={<AuthCallback />} />
      <Route path="/app" element={<AppLayout />}>
        <Route index element={<AppDashboard />} />
        <Route path="status" element={<AppStatus />} />
        <Route path="settings" element={<AppSettings />} />
        <Route path="rgpd" element={<AppRgpd />} />
      </Route>
      <Route path="/admin" element={<Admin />} />
      <Route path="/admin/tenants/:tenantId" element={<AdminTenant />} />
      <Route path="/admin/tenants/:tenantId/dashboard" element={<AdminTenantDashboard />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
