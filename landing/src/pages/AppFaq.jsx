import FaqEditor from "../components/FaqEditor.jsx";
import { api } from "../lib/api.js";

export default function AppFaq() {
  return (
    <div className="page">
      <div className="dcard" style={{ maxWidth: 980 }}>
        <FaqEditor
          title="FAQ de votre cabinet"
          description="Ajoutez les réponses que votre assistante doit connaître. Chaque modification est sauvegardée dans votre configuration et réinjectée dans le prompt Vapi."
          loadFaq={() => api.tenantGetFaq()}
          saveFaq={(faq) => api.tenantUpdateFaq(faq)}
          resetFaq={() => api.tenantResetFaq()}
          variant="dark"
        />
      </div>
    </div>
  );
}
