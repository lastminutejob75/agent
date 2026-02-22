import { Routes, Route, Navigate, Outlet } from "react-router-dom";
import UwiLanding from "./components/UwiLanding";
import AuthLayout from "./components/AuthLayout";
import Onboarding from "./pages/Onboarding";
import Login from "./pages/Login";
import ForgotPassword from "./pages/ForgotPassword";
import ResetPassword from "./pages/ResetPassword";
import AuthGoogleCallback from "./pages/AuthGoogleCallback";
import EssaiGratuit from "./pages/EssaiGratuit";
import DecouverteClient from "./pages/DecouverteClient";
import CreerAssistante from "./pages/CreerAssistante";
import AppLayout from "./pages/AppLayout";
import AppDashboard from "./pages/AppDashboard";
import AppStatus from "./pages/AppStatus";
import AppSettings from "./pages/AppSettings";
import AppRgpd from "./pages/AppRgpd";
import ImpersonatePage from "./pages/Impersonate";
import CGV from "./pages/CGV";
import CGU from "./pages/CGU";
import MentionsLegales from "./pages/MentionsLegales";
import Contact from "./pages/Contact";

/** Layout neutre pour /app : rend uniquement les routes enfants (impersonate ou AppLayout). */
function AppShell() {
  return <Outlet />;
}

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
import AdminLeadsList from "./admin/pages/AdminLeadsList";
import AdminLeadDetail from "./admin/pages/AdminLeadDetail";
import AdminNotFound from "./admin/pages/AdminNotFound";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<UwiLanding />} />
      <Route path="/onboarding" element={<Onboarding />} />
      <Route path="/creer-assistante" element={<CreerAssistante />} />
      <Route path="/cgv" element={<CGV />} />
      <Route path="/cgu" element={<CGU />} />
      <Route path="/mentions-legales" element={<MentionsLegales />} />
      <Route path="/contact" element={<Contact />} />
      <Route element={<AuthLayout />}>
        <Route path="login" element={<Login />} />
        <Route path="forgot-password" element={<ForgotPassword />} />
        <Route path="reset-password" element={<ResetPassword />} />
        <Route path="essai-gratuit" element={<EssaiGratuit />} />
        <Route path="decouverte" element={<DecouverteClient />} />
        <Route path="auth/google/callback" element={<AuthGoogleCallback />} />
      </Route>
      <Route path="/app" element={<AppShell />}>
        <Route path="impersonate" element={<ImpersonatePage />} />
        <Route element={<AppLayout />}>
          <Route index element={<AppDashboard />} />
          <Route path="status" element={<AppStatus />} />
          <Route path="settings" element={<AppSettings />} />
          <Route path="rgpd" element={<AppRgpd />} />
        </Route>
      </Route>

      <Route path="/admin" element={<AdminAuthProvider><Outlet /></AdminAuthProvider>}>
        <Route path="login" element={<AdminLogin />} />
        <Route element={<ProtectedRoute />}>
          <Route element={<AdminLayout />}>
            <Route index element={<AdminDashboard />} />
            <Route path="tenants/new" element={<AdminTenantNew />} />
            <Route path="tenants" element={<AdminTenantsList />} />
            <Route path="tenants/:id" element={<AdminTenantDetail />} />
            <Route path="tenants/:id/dashboard" element={<AdminTenantDashboard />} />
            <Route path="tenants/:id/calls" element={<AdminCalls />} />
            <Route path="calls" element={<AdminCalls />} />
            <Route path="monitoring" element={<AdminMonitoring />} />
            <Route path="operations" element={<AdminOperations />} />
            <Route path="quality" element={<AdminQuality />} />
            <Route path="leads" element={<AdminLeadsList />} />
            <Route path="leads/:id" element={<AdminLeadDetail />} />
            <Route path="audit" element={<AdminAuditLog />} />
            <Route path="*" element={<AdminNotFound />} />
          </Route>
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
