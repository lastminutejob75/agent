import { Routes, Route, Navigate, Outlet } from "react-router-dom";
import SeoHead from "./components/SeoHead";
import UwiLanding from "./components/UwiLanding";
import AuthLayout from "./components/AuthLayout";
import Login from "./pages/Login";
import ForgotPassword from "./pages/ForgotPassword";
import ResetPassword from "./pages/ResetPassword";
import AuthGoogleCallback from "./pages/AuthGoogleCallback";
import EssaiGratuit from "./pages/EssaiGratuit";
import DecouverteClient from "./pages/DecouverteClient";
import CreerAssistante from "./pages/CreerAssistante";
import AppLayout from "./pages/AppLayout";
import AppFirstOnboarding from "./pages/AppFirstOnboarding";
import AppDashboard from "./pages/AppDashboard";
import AppCalls from "./pages/AppCalls";
import AppAgenda from "./pages/AppAgenda";
import AppHoraires from "./pages/AppHoraires";
import AppActions from "./pages/AppActions";
import AppFacturation from "./pages/AppFacturation";
import AppProfil from "./pages/AppProfil";
import AppConfig from "./pages/AppConfig";
import AppStatus from "./pages/AppStatus";
import AppSettings from "./pages/AppSettings";
import AppRgpd from "./pages/AppRgpd";
import ImpersonatePage from "./pages/Impersonate";
import CGV from "./pages/CGV";
import CGU from "./pages/CGU";
import MentionsLegales from "./pages/MentionsLegales";
import Contact from "./pages/Contact";
import Demo from "./pages/Demo";
import SeoVerticalPage from "./pages/SeoVerticalPage";
import Checkout from "./pages/Checkout";
import CheckoutReturn from "./pages/CheckoutReturn";
import BillingPage from "./pages/BillingPage";
import NotFound from "./pages/NotFound";

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
import AdminTenantPage from "./admin/pages/AdminTenantPage";
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
    <>
      <SeoHead />
      <Routes>
      <Route path="/" element={<UwiLanding />} />
      <Route path="/onboarding" element={<Navigate to="/creer-assistante?new=1" replace />} />
      <Route path="/creer-assistante" element={<CreerAssistante />} />
      <Route path="/cgv" element={<CGV />} />
      <Route path="/cgu" element={<CGU />} />
      <Route path="/mentions-legales" element={<MentionsLegales />} />
      <Route path="/contact" element={<Contact />} />
      <Route path="/demo" element={<Demo />} />
      <Route path="/secretaire-medicale-augmentee" element={<SeoVerticalPage pageKey="/secretaire-medicale-augmentee" />} />
      <Route path="/secretaire-medicale-augmentee-medecin" element={<SeoVerticalPage pageKey="/secretaire-medicale-augmentee-medecin" />} />
      <Route path="/agent-accueil-ia-medical" element={<Navigate to="/secretaire-medicale-augmentee" replace />} />
      <Route path="/assistant-telephone-ia-medecin" element={<Navigate to="/secretaire-medicale-augmentee-medecin" replace />} />
      <Route path="/assistant-telephone-ia-dentiste" element={<SeoVerticalPage pageKey="/assistant-telephone-ia-dentiste" />} />
      <Route path="/assistant-telephone-ia-kine" element={<SeoVerticalPage pageKey="/assistant-telephone-ia-kine" />} />
      <Route path="/assistant-telephone-ia-sage-femme" element={<SeoVerticalPage pageKey="/assistant-telephone-ia-sage-femme" />} />
      <Route path="/assistant-telephone-ia-dermatologue" element={<SeoVerticalPage pageKey="/assistant-telephone-ia-dermatologue" />} />
      <Route path="/assistant-telephone-ia-orthophoniste" element={<SeoVerticalPage pageKey="/assistant-telephone-ia-orthophoniste" />} />
      <Route path="/standard-telephonique-cabinet-medical" element={<SeoVerticalPage pageKey="/standard-telephonique-cabinet-medical" />} />
      <Route path="/checkout" element={<Checkout />} />
      <Route path="/checkout/return" element={<CheckoutReturn />} />
      <Route path="/billing" element={<BillingPage />} />
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
        <Route path="onboarding" element={<AppFirstOnboarding />} />
        <Route element={<AppLayout />}>
          <Route index element={<AppDashboard />} />
          <Route path="appels" element={<AppCalls />} />
          <Route path="agenda" element={<AppAgenda />} />
          <Route path="horaires" element={<AppHoraires />} />
          <Route path="actions" element={<AppActions />} />
          <Route path="facturation" element={<AppFacturation />} />
          <Route path="profil" element={<AppProfil />} />
          <Route path="config" element={<AppConfig />} />
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
            <Route path="tenants/:id" element={<AdminTenantPage />} />
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

      <Route path="*" element={<NotFound />} />
    </Routes>
    </>
  );
}
