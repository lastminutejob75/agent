import { Link } from "react-router-dom";
import LegalPageLayout from "../components/LegalPageLayout";
import { openCookiePreferences } from "../lib/cookieConsent";

export default function PolitiqueCookies() {
  return (
    <LegalPageLayout title="Politique cookies">
      <p>
        <strong>Dernière mise à jour :</strong> mai 2026
      </p>
      <p>
        Cette page décrit les traceurs utilisés sur <strong>uwiapp.com</strong> et la manière de gérer vos
        préférences. Pour le traitement des données personnelles plus largement, voir la{" "}
        <Link to="/politique-de-confidentialite">politique de confidentialité</Link>.
      </p>

      <h2>1. Qu&apos;est-ce qu&apos;un cookie ?</h2>
      <p>
        Un cookie est un petit fichier déposé sur votre terminal. Nous utilisons aussi le stockage local du
        navigateur (<code>localStorage</code>) pour mémoriser votre choix de consentement.
      </p>

      <h2>2. Cookies strictement nécessaires</h2>
      <p>Ces traceurs ne nécessitent pas votre consentement :</p>
      <ul>
        <li>
          <strong>uwi_session / uwi_admin_session</strong> (cookie HttpOnly, domaine API) — maintien de la
          session connectée, sécurité.
        </li>
        <li>
          <strong>uwi_cookie_consent_v1</strong> (localStorage) — mémorise votre choix Accepter / Refuser pour
          les traceurs optionnels.
        </li>
        <li>
          <strong>Cookies Stripe</strong> (pages paiement / checkout) — prévention de la fraude et traitement
          du paiement.
        </li>
      </ul>

      <h2>3. Traceurs soumis à consentement</h2>
      <p>Ces traceurs ne sont chargés que si vous cliquez sur « Tout accepter » :</p>
      <ul>
        <li>
          <strong>Google Analytics (GA4)</strong> — mesure d&apos;audience, pages vues, événements marketing.
          Durée typique : 14 mois max. Éditeur : Google Ireland Limited.
        </li>
        <li>
          <strong>Meta Pixel (Facebook)</strong> — mesure des campagnes publicitaires et conversions.
          Durée typique : 90 jours à 13 mois selon cookies. Éditeur : Meta Platforms Ireland Limited.
        </li>
      </ul>

      <h2>4. Gérer vos préférences</h2>
      <p>
        Vous pouvez à tout moment modifier votre choix :
      </p>
      <p>
        <button
          type="button"
          onClick={openCookiePreferences}
          className="rounded-lg border border-[#00F0B5] bg-transparent px-4 py-2 text-sm font-bold text-[#00F0B5] hover:bg-[#00F0B5]/10"
        >
          Rouvrir le bandeau cookies
        </button>
      </p>
      <p>
        Vous pouvez aussi configurer votre navigateur pour bloquer les cookies ou supprimer ceux déjà déposés.
        Le refus des cookies optionnels n&apos;empêche pas l&apos;utilisation du site.
      </p>

      <h2>5. Durées</h2>
      <ul>
        <li>Consentement cookies : 13 mois maximum avant redemande.</li>
        <li>Session : jusqu&apos;à fermeture du navigateur ou expiration configurée côté serveur.</li>
      </ul>

      <h2>6. Contact</h2>
      <p>
        Questions : <Link to="/contact">Contact</Link> ou{" "}
        <a href="mailto:contact@uwiapp.com">contact@uwiapp.com</a>.
      </p>
    </LegalPageLayout>
  );
}
