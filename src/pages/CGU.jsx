import { Link } from "react-router-dom";
import LegalPageLayout from "../components/LegalPageLayout";

export default function CGU() {
  return (
    <LegalPageLayout title="Conditions générales d'utilisation">
      <p><strong>Dernière mise à jour :</strong> janvier 2025</p>

      <h2>1. Objet et acceptation</h2>
      <p>Les présentes Conditions Générales d'Utilisation (CGU) régissent l'accès et l'utilisation des services et du site proposés par UWi Medical. L'accès au site et à la plateforme constitue une acceptation sans réserve des présentes CGU.</p>

      <h2>2. Description du service</h2>
      <p>UWi Medical met à disposition une plateforme d'assistant vocal IA destinée aux professionnels de santé (cabinets, centres médicaux) pour la gestion des appels, des rendez-vous et des rappels patients, dans le respect des exigences HDS et RGPD.</p>

      <h2>3. Compte et accès</h2>
      <p>L'utilisateur doit créer un compte en fournissant des informations exactes. Il est responsable de la confidentialité de ses identifiants. Tout accès ou utilisation non autorisé doit être signalé immédiatement.</p>

      <h2>4. Utilisation acceptable</h2>
      <p>L'utilisateur s'engage à utiliser le service de manière licite, à ne pas contourner les dispositifs de sécurité, à ne pas exploiter des failles et à respecter les droits des tiers et la réglementation applicable (données de santé, secret médical).</p>

      <h2>5. Données et confidentialité</h2>
      <p>Le traitement des données personnelles et de santé est décrit dans la Politique de confidentialité et réalisé conformément au RGPD. Les données sont hébergées en France chez un hébergeur certifié HDS.</p>

      <h2>6. Propriété intellectuelle</h2>
      <p>L'ensemble des éléments du site et de la plateforme (textes, logiciels, marques, visuels) est protégé par le droit de la propriété intellectuelle. Aucune reproduction ou réutilisation n'est autorisée sans accord écrit du Prestataire.</p>

      <h2>7. Disponibilité</h2>
      <p>Le Prestataire s'efforce d'assurer une disponibilité optimale du service. Des opérations de maintenance peuvent entraîner des indisponibilités temporaires, signalées lorsque cela est possible.</p>

      <h2>8. Modifications</h2>
      <p>UWi Medical se réserve le droit de modifier les CGU. Les utilisateurs seront informés des changements substantiels ; la poursuite de l'utilisation vaut acceptation des nouvelles conditions.</p>

      <h2>9. Contact</h2>
      <p>Pour toute question sur les CGU : <Link to="/contact">page Contact</Link>.</p>
    </LegalPageLayout>
  );
}
