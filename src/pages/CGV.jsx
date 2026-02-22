import { Link } from "react-router-dom";
import LegalPageLayout from "../components/LegalPageLayout";

export default function CGV() {
  return (
    <LegalPageLayout title="Conditions générales de vente">
      <p><strong>Dernière mise à jour :</strong> janvier 2025</p>

      <h2>1. Objet</h2>
      <p>Les présentes Conditions Générales de Vente (CGV) régissent les ventes de services proposés par UWi Medical (ci-après « le Prestataire ») à ses clients (ci-après « le Client »), notamment l'accès à la plateforme d'assistant vocal IA pour cabinets médicaux et professionnels de santé.</p>

      <h2>2. Services</h2>
      <p>Le Prestataire propose un service d'assistant vocal intelligent (IA) permettant la prise de rendez-vous, le triage des appels et la gestion des rappels patients. Les fonctionnalités détaillées sont décrites sur le site et dans l'offre souscrite.</p>

      <h2>3. Tarifs et facturation</h2>
      <p>Les tarifs sont indiqués en euros TTC. Une période d'essai gratuite peut être proposée ; à l'issue de celle-ci, l'abonnement est facturé selon l'offre choisie. Les factures sont envoyées par email et sont payables à réception.</p>

      <h2>4. Paiement</h2>
      <p>Le paiement est effectué par prélèvement ou carte bancaire selon les modalités communiquées. En cas de défaut de paiement, le Prestataire se réserve le droit de suspendre l'accès au service après mise en demeure restée infructueuse.</p>

      <h2>5. Durée et résiliation</h2>
      <p>L'abonnement est souscrit pour la durée indiquée à la commande. Le Client peut résilier à tout moment ; la résiliation prend effet en fin de période en cours. Aucun remboursement partiel ne sera effectué pour la période déjà facturée.</p>

      <h2>6. Obligations du Client</h2>
      <p>Le Client s'engage à fournir des informations exactes, à utiliser le service conformément à son objet et dans le respect des lois en vigueur (notamment RGPD et réglementation des données de santé).</p>

      <h2>7. Limitation de responsabilité</h2>
      <p>Le Prestataire s'engage à mettre en œuvre les moyens nécessaires au bon fonctionnement du service. Sa responsabilité ne pourra être engagée au-delà des montants effectivement versés par le Client sur les douze derniers mois.</p>

      <h2>8. Droit applicable</h2>
      <p>Les présentes CGV sont soumises au droit français. Tout litige sera de la compétence des tribunaux français.</p>

      <h2>9. Contact</h2>
      <p>Pour toute question : <Link to="/contact">page Contact</Link> ou par email à l'adresse indiquée dans les mentions légales.</p>
    </LegalPageLayout>
  );
}
