import { Link } from "react-router-dom";
import LegalPageLayout from "../components/LegalPageLayout";

export default function MentionsLegales() {
  return (
    <LegalPageLayout title="Mentions légales">
      <p><strong>Dernière mise à jour :</strong> janvier 2025</p>

      <h2>1. Éditeur du site</h2>
      <p>
        <strong>UWi Medical</strong><br />
        [Raison sociale / forme juridique]<br />
        [Siège social : adresse]<br />
        [SIRET]<br />
        [RCS]
      </p>
      <p><em>À compléter avec les informations légales de votre société.</em></p>

      <h2>2. Hébergeur</h2>
      <p>
        [Nom de l'hébergeur]<br />
        [Adresse]<br />
        [Contact]
      </p>
      <p><em>À compléter (ex. Vercel, OVH, etc.).</em></p>

      <h2>3. Directeur de la publication</h2>
      <p>Le directeur de la publication du site est [Nom du responsable].</p>

      <h2>4. Données personnelles et cookies</h2>
      <p>Les données collectées via le site et la plateforme sont traitées conformément au Règlement général sur la protection des données (RGPD) et à la loi « Informatique et Libertés ». Les données de santé font l'objet de mesures renforcées et d'un hébergement certifié HDS.</p>
      <p>Pour exercer vos droits (accès, rectification, effacement, opposition, portabilité) ou pour toute question : <Link to="/contact">page Contact</Link>.</p>

      <h2>5. Propriété intellectuelle</h2>
      <p>L'ensemble du contenu du site (textes, images, logos, logiciels) est protégé par le droit d'auteur et le droit des marques. Toute reproduction non autorisée peut constituer une contrefaçon.</p>

      <h2>6. Limitation de responsabilité</h2>
      <p>UWi Medical s'efforce d'assurer l'exactitude des informations publiées. Elle ne peut toutefois être tenue responsable des erreurs, omissions ou des dommages résultant de l'utilisation du site ou du service.</p>

      <h2>7. Liens hypertextes</h2>
      <p>Les liens vers des sites tiers ne engagent pas la responsabilité d'UWi Medical quant au contenu de ces sites.</p>

      <h2>8. Droit applicable</h2>
      <p>Le site et les présentes mentions sont régis par le droit français.</p>

      <h2>9. Contact</h2>
      <p>Pour toute demande relative aux mentions légales : <Link to="/contact">page Contact</Link>.</p>
    </LegalPageLayout>
  );
}
