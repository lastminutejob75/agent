// Layout commun pour pages légales (CGV, CGU, Mentions légales, Contact)
import { Link } from "react-router-dom";

export default function LegalPageLayout({ title, children }) {
  return (
    <div className="legal-page">
      <div className="legal-page__wrap">
        <Link to="/" className="legal-page__back">← Retour à l'accueil</Link>
        <h1 className="legal-page__title">{title}</h1>
        <div className="legal-page__content">
          {children}
        </div>
      </div>
      <style>{`
        .legal-page {
          min-height: 100vh;
          background: #0A1628;
          color: #e2e8f0;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
          padding: 24px 16px 48px;
        }
        .legal-page__wrap {
          max-width: 720px;
          margin: 0 auto;
        }
        .legal-page__back {
          display: inline-block;
          margin-bottom: 24px;
          font-size: 14px;
          font-weight: 600;
          color: #00D4AA;
          text-decoration: none;
        }
        .legal-page__back:hover { text-decoration: underline; }
        .legal-page__title {
          font-size: 28px;
          font-weight: 800;
          color: #fff;
          margin-bottom: 28px;
          letter-spacing: -0.02em;
        }
        .legal-page__content {
          font-size: 15px;
          line-height: 1.7;
          color: rgba(255,255,255,0.78);
        }
        .legal-page__content h2 {
          font-size: 18px;
          font-weight: 700;
          color: #fff;
          margin: 28px 0 10px;
        }
        .legal-page__content h2:first-of-type { margin-top: 0; }
        .legal-page__content p { margin-bottom: 12px; }
        .legal-page__content ul {
          margin: 12px 0;
          padding-left: 24px;
        }
        .legal-page__content li { margin-bottom: 6px; }
        .legal-page__content a {
          color: #00D4AA;
          text-decoration: none;
        }
        .legal-page__content a:hover { text-decoration: underline; }
      `}</style>
    </div>
  );
}
