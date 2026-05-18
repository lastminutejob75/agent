import { Link } from "react-router-dom";
import LegalPageLayout from "../components/LegalPageLayout";

export default function MentionsLegales() {
  return (
    <LegalPageLayout title="Mentions légales">
      <p><strong>Dernière mise à jour :</strong> mai 2026</p>

      <h2>1. Éditeur du site</h2>
      <p>
        <strong>TROOPER</strong>, société par actions simplifiée unipersonnelle (SASU)<br />
        Siège social : 60 rue François Ier, 75008 Paris, France<br />
        RCS Paris 990 375 149<br />
        Représentée par M. Heni Goutal, en sa qualité de Président<br />
        Email : <a href="mailto:contact@uwiapp.com">contact@uwiapp.com</a><br />
        Téléphone : <a href="tel:0939240575">09 39 24 05 75</a>
      </p>

      <h2>2. Hébergement</h2>
      <p>
        <strong>Hébergement du site web (front)</strong><br />
        Vercel Inc., 440 N Barranca Avenue #4133, Covina, CA 91723, États-Unis<br />
        <a href="https://vercel.com" target="_blank" rel="noopener noreferrer">vercel.com</a>
      </p>
      <p>
        <strong>Hébergement de l'API et du backend applicatif</strong><br />
        Railway Corp., 410 Townsend Street, Suite 220, San Francisco, CA 94107, États-Unis<br />
        <a href="https://railway.app" target="_blank" rel="noopener noreferrer">railway.app</a>
      </p>
      <p>
        <strong>Nom de domaine et services associés</strong><br />
        OVH SAS, 2 rue Kellermann, 59100 Roubaix, France<br />
        RCS Lille Métropole 424 761 419 — <a href="https://www.ovhcloud.com" target="_blank" rel="noopener noreferrer">ovhcloud.com</a>
      </p>

      <h2>3. Directeur de la publication</h2>
      <p>Le directeur de la publication du site est M. Heni Goutal, Président de TROOPER.</p>

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
