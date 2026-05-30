/** Gestion du consentement cookies (CNIL) — traceurs chargés uniquement si analytics=true. */

export const STORAGE_KEY = "uwi_cookie_consent_v1";
export const CONSENT_CHANGE_EVENT = "uwi:cookie-consent";
export const OPEN_BANNER_EVENT = "uwi:open-cookie-banner";

const META_PIXEL_ID = "313018958342365";

export function getCookieConsent() {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (typeof parsed?.analytics !== "boolean") return null;
    return parsed;
  } catch {
    return null;
  }
}

export function hasConsentDecision() {
  return getCookieConsent() !== null;
}

function ensureGtagStub() {
  if (typeof window === "undefined") return;
  window.dataLayer = window.dataLayer || [];
  window.gtag = window.gtag || function gtag() {
    window.dataLayer.push(arguments);
  };
}

export function loadGoogleAnalytics() {
  if (typeof document === "undefined" || window.__uwiGaLoaded) return;
  const gaId = (import.meta.env.VITE_GA_MEASUREMENT_ID || "").trim();
  if (!gaId) return;

  ensureGtagStub();
  const script = document.createElement("script");
  script.async = true;
  script.src = `https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(gaId)}`;
  script.onload = () => {
    window.gtag("js", new Date());
    window.gtag("config", gaId, { anonymize_ip: true });
  };
  document.head.appendChild(script);
  window.__uwiGaLoaded = true;
}

export function loadMetaPixel() {
  if (typeof window === "undefined" || window.__uwiMetaLoaded) return;

  if (typeof window.fbq === "function") {
    window.fbq("track", "PageView");
    window.__uwiMetaLoaded = true;
    return;
  }

  /* Meta Pixel — chargé uniquement après consentement analytics. */
  /* eslint-disable */
  !(function (f, b, e, v, n, t, s) {
    if (f.fbq) return;
    n = f.fbq = function () {
      n.callMethod ? n.callMethod.apply(n, arguments) : n.queue.push(arguments);
    };
    if (!f._fbq) f._fbq = n;
    n.push = n;
    n.loaded = !0;
    n.version = "2.0";
    n.queue = [];
    t = b.createElement(e);
    t.async = !0;
    t.src = v;
    s = b.getElementsByTagName(e)[0];
    s.parentNode.insertBefore(t, s);
  })(window, document, "script", "https://connect.facebook.net/en_US/fbevents.js");
  /* eslint-enable */

  window.fbq("init", META_PIXEL_ID);
  window.fbq("track", "PageView");
  window.__uwiMetaLoaded = true;
}

export function applyConsent(consent) {
  if (!consent?.analytics) return;
  loadGoogleAnalytics();
  loadMetaPixel();
}

export function setCookieConsent(analytics) {
  const value = {
    analytics: Boolean(analytics),
    decidedAt: new Date().toISOString(),
  };
  if (typeof window !== "undefined") {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(value));
    window.dispatchEvent(new CustomEvent(CONSENT_CHANGE_EVENT, { detail: value }));
    applyConsent(value);
  }
  return value;
}

export function initCookieConsent() {
  if (typeof window === "undefined") return;
  ensureGtagStub();
  const existing = getCookieConsent();
  if (existing) applyConsent(existing);
}

export function openCookiePreferences() {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(OPEN_BANNER_EVENT));
}
