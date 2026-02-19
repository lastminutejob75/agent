import { Routes, Route, Navigate } from "react-router-dom";
import UwiLanding from "./components/UwiLanding";
import Onboarding from "./pages/Onboarding";
import Login from "./pages/Login";
import AuthCallback from "./pages/AuthCallback";
import AppLayout from "./pages/AppLayout";
import AppDashboard from "./pages/AppDashboard";
import AppStatus from "./pages/AppStatus";
import AppSettings from "./pages/AppSettings";
import AppRgpd from "./pages/AppRgpd";

import { AdminAuthProvider } from "./admin/AdminAuthProvider";
import ProtectedRoute from "./admin/ProtectedRoute";
import AdminLayout from "./admin/AdminLayout";
import AdminLogin from "./admin/AdminLogin";
import AdminDashboard from "./admin/pages/AdminDashboard";
import AdminTenantsList from "./admin/pages/AdminTenantsList";
import AdminTenantNew from "./admin/pages/AdminTenantNew";
import AdminTenantDetail from "./admin/pages/AdminTenantDetail";
import AdminTenantDashboard from "./admin/pages/AdminTenantDashboard";
import AdminCalls from "./admin/pages/AdminCalls";
import AdminMonitoring from "./admin/pages/AdminMonitoring";
import AdminAuditLog from "./admin/pages/AdminAuditLog";
import AdminOperations from "./admin/pages/AdminOperations";
import AdminQuality from "./admin/pages/AdminQuality";
import AdminNotFound from "./admin/pages/AdminNotFound";

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

      <Route
        path="/admin/*"
        element={
          <AdminAuthProvider>
            <Routes>
              <Route path="/admin/login" element={<AdminLogin />} />
              <Route element={<ProtectedRoute />}>
                <Route element={<AdminLayout />}>
                  <Route path="/admin" element={<AdminDashboard />} />
                  <Route path="/admin/tenants/new" element={<AdminTenantNew />} />
                  <Route path="/admin/tenants" element={<AdminTenantsList />} />
                  <Route path="/admin/tenants/:id" element={<AdminTenantDetail />} />
                  <Route path="/admin/tenants/:id/dashboard" element={<AdminTenantDashboard />} />
                  <Route path="/admin/tenants/:id/calls" element={<AdminCalls />} />
                  <Route path="/admin/calls" element={<AdminCalls />} />
                  <Route path="/admin/monitoring" element={<AdminMonitoring />} />
                  <Route path="/admin/operations" element={<AdminOperations />} />
                  <Route path="/admin/quality" element={<AdminQuality />} />
                  <Route path="/admin/audit" element={<AdminAuditLog />} />
                  <Route path="/admin/*" element={<AdminNotFound />} />
                </Route>
              </Route>
            </Routes>
          </AdminAuthProvider>
        }
      />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
