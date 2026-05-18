import { Link } from "react-router-dom";
import LegalPageLayout from "../components/LegalPageLayout";

export default function Contact() {
  return (
    <LegalPageLayout title="Contact">
      <p>Pour toute question sur nos services, une démo ou un accompagnement, vous pouvez nous joindre par les moyens suivants.</p>

      <h2>Téléphone</h2>
      <p>
        <a href="tel:0939240575">09 39 24 05 75</a><br />
        <span style={{ color: "rgba(255,255,255,0.6)", fontSize: "14px" }}>Du lundi au vendredi, 9h–18h</span>
      </p>

      <h2>Email</h2>
      <p>
        <a href="mailto:contact@uwiapp.com">contact@uwiapp.com</a><br />
        <span style={{ color: "rgba(255,255,255,0.6)", fontSize: "14px" }}>Nous nous efforçons de répondre sous 24h ouvrées.</span>
      </p>

      <h2>Démo et essai gratuit</h2>
      <p>
        Vous pouvez créer votre assistant IA en quelques minutes et tester le service gratuitement pendant un mois, sans carte bancaire&nbsp;: <Link to="/creer-assistante?new=1">Créer mon assistant</Link>.
      </p>
    </LegalPageLayout>
  );
}
