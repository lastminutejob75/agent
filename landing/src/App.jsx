import { Suspense, lazy } from "react";
import { Routes, Route, Navigate, Outlet } from "react-router-dom";
import SeoHead from "./components/SeoHead";
import AuthLayout from "./components/AuthLayout";

const publicPageModules = import.meta.glob([
  "./pages/CreerAssistante.jsx",
  "./pages/UwiLandingPage.jsx",
  "./pages/CGV.jsx",
  "./pages/CGU.jsx",
  "./pages/MentionsLegales.jsx",
  "./pages/Contact.jsx",
  "./pages/Demo.jsx",
  "./pages/SeoVerticalPage.jsx",
  "./pages/Login.jsx",
  "./pages/ForgotPassword.jsx",
  "./pages/ResetPassword.jsx",
  "./pages/AuthGoogleCallback.jsx",
  "./pages/EssaiGratuit.jsx",
  "./pages/DecouverteClient.jsx",
  "./pages/Checkout.jsx",
  "./pages/CheckoutReturn.jsx",
  "./pages/BillingPage.jsx",
  "./pages/NotFound.jsx",
]);
const publicPageModulesEager = import.meta.glob([
  "./pages/CreerAssistante.jsx",
  "./pages/UwiLandingPage.jsx",
  "./pages/CGV.jsx",
  "./pages/CGU.jsx",
  "./pages/MentionsLegales.jsx",
  "./pages/Contact.jsx",
  "./pages/Demo.jsx",
  "./pages/SeoVerticalPage.jsx",
  "./pages/Login.jsx",
  "./pages/ForgotPassword.jsx",
  "./pages/ResetPassword.jsx",
  "./pages/AuthGoogleCallback.jsx",
  "./pages/EssaiGratuit.jsx",
  "./pages/DecouverteClient.jsx",
  "./pages/Checkout.jsx",
  "./pages/CheckoutReturn.jsx",
  "./pages/BillingPage.jsx",
  "./pages/NotFound.jsx",
], {
  eager: true,
});

function resolvePublicPage(modulePath) {
  const modOrLoader = import.meta.env.SSR ? publicPageModulesEager[modulePath] : publicPageModules[modulePath];
  if (!modOrLoader) {
    throw new Error(`Public page module not found: ${modulePath}`);
  }
  return import.meta.env.SSR ? modOrLoader.default : lazy(modOrLoader);
}

const CreerAssistante = resolvePublicPage("./pages/CreerAssistante.jsx");
const UwiLandingPage = resolvePublicPage("./pages/UwiLandingPage.jsx");
const CGV = resolvePublicPage("./pages/CGV.jsx");
const CGU = resolvePublicPage("./pages/CGU.jsx");
const MentionsLegales = resolvePublicPage("./pages/MentionsLegales.jsx");
const Contact = resolvePublicPage("./pages/Contact.jsx");
const Demo = resolvePublicPage("./pages/Demo.jsx");
const SeoVerticalPage = resolvePublicPage("./pages/SeoVerticalPage.jsx");
const Login = resolvePublicPage("./pages/Login.jsx");
const ForgotPassword = resolvePublicPage("./pages/ForgotPassword.jsx");
const ResetPassword = resolvePublicPage("./pages/ResetPassword.jsx");
const AuthGoogleCallback = resolvePublicPage("./pages/AuthGoogleCallback.jsx");
const EssaiGratuit = resolvePublicPage("./pages/EssaiGratuit.jsx");
const DecouverteClient = resolvePublicPage("./pages/DecouverteClient.jsx");
const Checkout = resolvePublicPage("./pages/Checkout.jsx");
const CheckoutReturn = resolvePublicPage("./pages/CheckoutReturn.jsx");
const BillingPage = resolvePublicPage("./pages/BillingPage.jsx");
const NotFound = resolvePublicPage("./pages/NotFound.jsx");

/** Layout neutre pour /app : rend uniquement les routes enfants (impersonate ou AppLayout). */
function AppShell() {
  return <Outlet />;
}

const AppLayout = lazy(() => import("./pages/AppLayout"));
const AppFirstOnboarding = lazy(() => import("./pages/AppFirstOnboarding"));
const AppDashboard = lazy(() => import("./pages/AppDashboard"));
const AppCalls = lazy(() => import("./pages/AppCalls"));
const AppAgenda = lazy(() => import("./pages/AppAgenda"));
const AppHoraires = lazy(() => import("./pages/AppHoraires"));
const AppFaq = lazy(() => import("./pages/AppFaq"));
const AppActions = lazy(() => import("./pages/AppActions"));
const AppFacturation = lazy(() => import("./pages/AppFacturation"));
const AppProfil = lazy(() => import("./pages/AppProfil"));
const AppConfig = lazy(() => import("./pages/AppConfig"));
const AppStatus = lazy(() => import("./pages/AppStatus"));
const AppSettings = lazy(() => import("./pages/AppSettings"));
const AppRgpd = lazy(() => import("./pages/AppRgpd"));
const ImpersonatePage = lazy(() => import("./pages/Impersonate"));

const AdminAuthProvider = lazy(() =>
  import("./admin/AdminAuthProvider").then((module) => ({ default: module.AdminAuthProvider })),
);
const ProtectedRoute = lazy(() => import("./admin/ProtectedRoute"));
const AdminLayout = lazy(() => import("./admin/AdminLayout"));
const AdminLogin = lazy(() => import("./admin/AdminLogin"));
const AdminDashboard = lazy(() => import("./admin/pages/AdminDashboard"));
const AdminTenantsList = lazy(() => import("./admin/pages/AdminTenantsList"));
const AdminTenantNew = lazy(() => import("./admin/pages/AdminTenantNew"));
const AdminTenantPage = lazy(() => import("./admin/pages/AdminTenantPage"));
const AdminTenantDashboard = lazy(() => import("./admin/pages/AdminTenantDashboard"));
const AdminCalls = lazy(() => import("./admin/pages/AdminCalls"));
const AdminMonitoring = lazy(() => import("./admin/pages/AdminMonitoring"));
const AdminAuditLog = lazy(() => import("./admin/pages/AdminAuditLog"));
const AdminOperations = lazy(() => import("./admin/pages/AdminOperations"));
const AdminQuality = lazy(() => import("./admin/pages/AdminQuality"));
const AdminLeadsList = lazy(() => import("./admin/pages/AdminLeadsList"));
const AdminLeadDetail = lazy(() => import("./admin/pages/AdminLeadDetail"));
const AdminNotFound = lazy(() => import("./admin/pages/AdminNotFound"));

function RouteLoader() {
  return <div style={{ minHeight: "30vh" }} />;
}

function LazyElement({ Component, ...props }) {
  return (
    <Suspense fallback={<RouteLoader />}>
      <Component {...props} />
    </Suspense>
  );
}

export default function App() {
  return (
    <>
      <SeoHead />
      <Routes>
      <Route path="/" element={<LazyElement Component={UwiLandingPage} />} />
      <Route path="/onboarding" element={<Navigate to="/creer-assistante?new=1" replace />} />
      <Route path="/creer-assistante" element={<LazyElement Component={CreerAssistante} />} />
      <Route path="/cgv" element={<LazyElement Component={CGV} />} />
      <Route path="/cgu" element={<LazyElement Component={CGU} />} />
      <Route path="/mentions-legales" element={<LazyElement Component={MentionsLegales} />} />
      <Route path="/contact" element={<LazyElement Component={Contact} />} />
      <Route path="/demo" element={<LazyElement Component={Demo} />} />
      <Route path="/secretaire-medicale-augmentee" element={<LazyElement Component={SeoVerticalPage} pageKey="/secretaire-medicale-augmentee" />} />
      <Route path="/secretaire-medicale-augmentee-medecin" element={<LazyElement Component={SeoVerticalPage} pageKey="/secretaire-medicale-augmentee-medecin" />} />
      <Route path="/agent-accueil-ia-medical" element={<Navigate to="/secretaire-medicale-augmentee" replace />} />
      <Route path="/assistant-telephone-ia-medecin" element={<Navigate to="/secretaire-medicale-augmentee-medecin" replace />} />
      <Route path="/assistant-telephone-ia-dentiste" element={<LazyElement Component={SeoVerticalPage} pageKey="/assistant-telephone-ia-dentiste" />} />
      <Route path="/assistant-telephone-ia-kine" element={<LazyElement Component={SeoVerticalPage} pageKey="/assistant-telephone-ia-kine" />} />
      <Route path="/assistant-telephone-ia-sage-femme" element={<LazyElement Component={SeoVerticalPage} pageKey="/assistant-telephone-ia-sage-femme" />} />
      <Route path="/assistant-telephone-ia-dermatologue" element={<LazyElement Component={SeoVerticalPage} pageKey="/assistant-telephone-ia-dermatologue" />} />
      <Route path="/assistant-telephone-ia-orthophoniste" element={<LazyElement Component={SeoVerticalPage} pageKey="/assistant-telephone-ia-orthophoniste" />} />
      <Route path="/standard-telephonique-cabinet-medical" element={<LazyElement Component={SeoVerticalPage} pageKey="/standard-telephonique-cabinet-medical" />} />
      <Route path="/checkout" element={<LazyElement Component={Checkout} />} />
      <Route path="/checkout/return" element={<LazyElement Component={CheckoutReturn} />} />
      <Route path="/billing" element={<LazyElement Component={BillingPage} />} />
      <Route element={<AuthLayout />}>
        <Route path="login" element={<LazyElement Component={Login} />} />
        <Route path="forgot-password" element={<LazyElement Component={ForgotPassword} />} />
        <Route path="reset-password" element={<LazyElement Component={ResetPassword} />} />
        <Route path="essai-gratuit" element={<LazyElement Component={EssaiGratuit} />} />
        <Route path="decouverte" element={<LazyElement Component={DecouverteClient} />} />
        <Route path="auth/google/callback" element={<LazyElement Component={AuthGoogleCallback} />} />
      </Route>
      <Route path="/app" element={<AppShell />}>
        <Route path="impersonate" element={<LazyElement Component={ImpersonatePage} />} />
        <Route path="onboarding" element={<LazyElement Component={AppFirstOnboarding} />} />
        <Route element={<LazyElement Component={AppLayout} />}>
          <Route index element={<LazyElement Component={AppDashboard} />} />
          <Route path="appels" element={<LazyElement Component={AppCalls} />} />
          <Route path="agenda" element={<LazyElement Component={AppAgenda} />} />
          <Route path="horaires" element={<LazyElement Component={AppHoraires} />} />
          <Route path="faq" element={<LazyElement Component={AppFaq} />} />
          <Route path="actions" element={<LazyElement Component={AppActions} />} />
          <Route path="facturation" element={<LazyElement Component={AppFacturation} />} />
          <Route path="profil" element={<LazyElement Component={AppProfil} />} />
          <Route path="config" element={<LazyElement Component={AppConfig} />} />
          <Route path="status" element={<LazyElement Component={AppStatus} />} />
          <Route path="settings" element={<LazyElement Component={AppSettings} />} />
          <Route path="rgpd" element={<LazyElement Component={AppRgpd} />} />
        </Route>
      </Route>

      <Route
        path="/admin"
        element={
          <LazyElement Component={AdminAuthProvider}>
            <Outlet />
          </LazyElement>
        }
      >
        <Route path="login" element={<LazyElement Component={AdminLogin} />} />
        <Route element={<LazyElement Component={ProtectedRoute} />}>
          <Route element={<LazyElement Component={AdminLayout} />}>
            <Route index element={<LazyElement Component={AdminDashboard} />} />
            <Route path="tenants/new" element={<LazyElement Component={AdminTenantNew} />} />
            <Route path="tenants" element={<LazyElement Component={AdminTenantsList} />} />
            <Route path="tenants/:id" element={<LazyElement Component={AdminTenantPage} />} />
            <Route path="tenants/:id/dashboard" element={<LazyElement Component={AdminTenantDashboard} />} />
            <Route path="tenants/:id/calls" element={<LazyElement Component={AdminCalls} />} />
            <Route path="calls" element={<LazyElement Component={AdminCalls} />} />
            <Route path="monitoring" element={<LazyElement Component={AdminMonitoring} />} />
            <Route path="operations" element={<LazyElement Component={AdminOperations} />} />
            <Route path="quality" element={<LazyElement Component={AdminQuality} />} />
            <Route path="leads" element={<LazyElement Component={AdminLeadsList} />} />
            <Route path="leads/:id" element={<LazyElement Component={AdminLeadDetail} />} />
            <Route path="audit" element={<LazyElement Component={AdminAuditLog} />} />
            <Route path="*" element={<LazyElement Component={AdminNotFound} />} />
          </Route>
        </Route>
      </Route>

      <Route path="*" element={<LazyElement Component={NotFound} />} />
    </Routes>
    </>
  );
}
