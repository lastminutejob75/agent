import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  CONSENT_CHANGE_EVENT,
  getCookieConsent,
  hasConsentDecision,
  OPEN_BANNER_EVENT,
  setCookieConsent,
} from "../lib/cookieConsent";

/** Bannière CNIL : traceurs analytics/pub uniquement après consentement explicite. */
export default function CookieConsentBanner() {
  const [visible, setVisible] = useState(() => typeof window !== "undefined" && !hasConsentDecision());
  const [forceOpen, setForceOpen] = useState(false);

  const hideIfDecided = useCallback(() => {
    if (hasConsentDecision() && !forceOpen) setVisible(false);
  }, [forceOpen]);

  useEffect(() => {
    hideIfDecided();
    const onConsent = () => hideIfDecided();
    const onOpen = () => {
      setForceOpen(true);
      setVisible(true);
    };
    window.addEventListener(CONSENT_CHANGE_EVENT, onConsent);
    window.addEventListener(OPEN_BANNER_EVENT, onOpen);
    return () => {
      window.removeEventListener(CONSENT_CHANGE_EVENT, onConsent);
      window.removeEventListener(OPEN_BANNER_EVENT, onOpen);
    };
  }, [hideIfDecided]);

  const accept = () => {
    setCookieConsent(true);
    setForceOpen(false);
    setVisible(false);
  };

  const refuse = () => {
    setCookieConsent(false);
    setForceOpen(false);
    setVisible(false);
  };

  if (!visible) return null;

  const current = getCookieConsent();

  return (
    <div
      className="fixed inset-x-0 bottom-0 z-[200] p-3 sm:p-4"
      role="dialog"
      aria-live="polite"
      aria-label="Consentement cookies"
    >
      <div className="mx-auto flex max-w-4xl flex-col gap-4 rounded-2xl border border-[#CBD5E1] bg-white p-4 shadow-2xl sm:flex-row sm:items-end sm:justify-between sm:p-5">
        <div className="min-w-0 flex-1 text-sm leading-relaxed text-[#334155]">
          <strong className="block text-base font-black text-[#0B1628]">Cookies et traceurs</strong>
          <p className="mt-1">
            Nous utilisons des cookies strictement nécessaires au fonctionnement du site (session, sécurité).
            Avec votre accord, nous pouvons aussi mesurer l&apos;audience (Google Analytics) et la performance
            de nos campagnes (Meta Pixel).
          </p>
          <p className="mt-2 text-xs text-[#64748B]">
            <Link to="/politique-cookies" className="font-semibold text-[#007F88] hover:underline">
              Politique cookies
            </Link>
            {" · "}
            <Link to="/politique-de-confidentialite" className="font-semibold text-[#007F88] hover:underline">
              Politique de confidentialité
            </Link>
            {current ? (
              <span>
                {" · "}
                Préférence actuelle : {current.analytics ? "analytics acceptés" : "analytics refusés"}
              </span>
            ) : null}
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          <button
            type="button"
            onClick={refuse}
            className="rounded-xl border border-[#CBD5E1] bg-white px-4 py-2.5 text-sm font-black text-[#475569] hover:bg-[#F8FAFC]"
          >
            Tout refuser
          </button>
          <button
            type="button"
            onClick={accept}
            className="rounded-xl bg-[#0B1628] px-4 py-2.5 text-sm font-black text-white hover:bg-[#1E293B]"
          >
            Tout accepter
          </button>
        </div>
      </div>
    </div>
  );
}
