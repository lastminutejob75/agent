import { Link } from "react-router-dom";
import LegalPageLayout from "../components/LegalPageLayout";

export default function PolitiqueConfidentialite() {
  return (
    <LegalPageLayout title="Politique de confidentialité">
      <p>
        <strong>Dernière mise à jour :</strong> mai 2026
      </p>
      <p>
        La présente politique décrit comment <strong>TROOPER</strong> (marque UWi Medical) traite les données
        personnelles dans le cadre du site <strong>uwiapp.com</strong> et de la plateforme UWi destinée aux
        professionnels de santé.
      </p>

      <h2>1. Responsable du traitement</h2>
      <p>
        TROOPER, SASU — 60 rue François Ier, 75008 Paris — RCS Paris 990 375 149.
        <br />
        Contact : <a href="mailto:contact@uwiapp.com">contact@uwiapp.com</a>
      </p>

      <h2>2. Données collectées</h2>
      <ul>
        <li>
          <strong>Visiteurs du site :</strong> données techniques (logs, adresse IP, navigateur), préférences
          cookies, pages consultées si vous acceptez les traceurs analytics.
        </li>
        <li>
          <strong>Prospects / essai gratuit :</strong> identité professionnelle, email, téléphone, informations
          de cabinet saisies dans le wizard « Créer mon assistant ».
        </li>
        <li>
          <strong>Clients (cabinets) :</strong> compte utilisateur, configuration cabinet, journaux d&apos;appels,
          fiches patients, rendez-vous, documents et notes saisis dans l&apos;espace client.
        </li>
        <li>
          <strong>Patients (formulaires publics) :</strong> réponses aux questionnaires administratifs ou
          médicaux, pièces jointes, consentements associés.
        </li>
        <li>
          <strong>Appels téléphoniques :</strong> métadonnées d&apos;appel, transcriptions ou résumés selon
          configuration, enregistrements le cas échéant avec information préalable.
        </li>
      </ul>

      <h2>3. Finalités et bases légales</h2>
      <ul>
        <li>Fourniture du service et exécution du contrat (compte, assistant vocal, agenda).</li>
        <li>Prospection et suivi commercial pour les demandes d&apos;essai (consentement ou intérêt légitime).</li>
        <li>Mesure d&apos;audience et optimisation marketing (consentement cookies).</li>
        <li>Sécurité, prévention de la fraude et amélioration du service.</li>
        <li>Respect des obligations légales (facturation, conservation probatoire).</li>
        <li>
          Données de santé : uniquement pour les fonctionnalités médicales activées (questionnaires HDS,
          documents cliniques), sur instruction du cabinet et avec les garanties renforcées applicables.
        </li>
      </ul>

      <h2>4. Destinataires et sous-traitants</h2>
      <p>Les données peuvent être traitées par des prestataires agissant pour notre compte, notamment :</p>
      <ul>
        <li>Hébergement front : Vercel Inc. (États-Unis, clauses contractuelles appropriées).</li>
        <li>API / backend : Railway Corp. (États-Unis).</li>
        <li>Base de données : PostgreSQL hébergée via Railway.</li>
        <li>Email transactionnel : Postmark / SMTP selon configuration.</li>
        <li>Paiement : Stripe.</li>
        <li>Agenda : Google Calendar (si connecté par le cabinet).</li>
        <li>IA vocale / LLM : prestataires contractuellement tenus de ne pas réutiliser vos données pour entraîner leurs modèles.</li>
        <li>Analytics / publicité (si consentement) : Google Analytics, Meta.</li>
      </ul>
      <p>
        La liste nominative complète et le contrat de sous-traitance (DPA) sont disponibles sur demande à{" "}
        <a href="mailto:contact@uwiapp.com">contact@uwiapp.com</a> ou via la page{" "}
        <Link to="/securite">Sécurité</Link>.
      </p>

      <h2>5. Durées de conservation</h2>
      <ul>
        <li>Compte client actif : durée du contrat + archivage légal limité.</li>
        <li>Prospects non convertis : jusqu&apos;à 3 ans après le dernier contact.</li>
        <li>Logs techniques : durée limitée selon besoins de sécurité (généralement 12 mois maximum).</li>
        <li>Données patients d&apos;un cabinet : selon paramètres du cabinet et obligations légales ; suppression possible via les outils RGPD de la plateforme.</li>
        <li>Cookies : voir la <Link to="/politique-cookies">politique cookies</Link>.</li>
      </ul>

      <h2>6. Données de santé et HDS</h2>
      <p>
        Les fonctionnalités médicales (questionnaires santé, documents cliniques) ne sont accessibles que
        lorsque l&apos;HDS est activé pour le cabinet concerné. Les mesures de sécurité renforcées (chiffrement,
        journalisation des accès, hébergement certifié HDS pour les données de santé) sont déployées selon
        la feuille de route produit. Le site vitrine et l&apos;API peuvent être hébergés hors HDS ; seules les
        données de santé relèvent du cadre HDS.
      </p>

      <h2>7. Vos droits</h2>
      <p>
        Conformément au RGPD, vous disposez des droits d&apos;accès, rectification, effacement, limitation,
        opposition, portabilité et retrait du consentement. Pour les exercer :{" "}
        <Link to="/contact">page Contact</Link> ou <a href="mailto:contact@uwiapp.com">contact@uwiapp.com</a>.
        Vous pouvez introduire une réclamation auprès de la CNIL (
        <a href="https://www.cnil.fr" target="_blank" rel="noopener noreferrer">
          cnil.fr
        </a>
        ).
      </p>

      <h2>8. Transferts hors UE</h2>
      <p>
        Certains sous-traitants (Vercel, Railway, Stripe, Google, Meta) peuvent traiter des données hors Union
        européenne. Ces transferts sont encadrés par des clauses contractuelles types ou mécanismes reconnus
        par la Commission européenne.
      </p>

      <h2>9. Sécurité</h2>
      <p>
        Nous mettons en œuvre des mesures techniques et organisationnelles adaptées : chiffrement en transit
        (HTTPS), authentification, séparation des environnements, contrôle d&apos;accès, sauvegardes. Détails
        sur <Link to="/securite">la page Sécurité</Link>.
      </p>

      <h2>10. Modifications</h2>
      <p>
        Cette politique peut être mise à jour. La date en tête de page sera révisée en cas de changement
        substantiel.
      </p>
    </LegalPageLayout>
  );
}
