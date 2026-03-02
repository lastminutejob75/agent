// Layout commun pour pages légales (CGV, CGU, Mentions légales, Contact)
import { Link } from "react-router-dom";

export default function LegalPageLayout({ title, tagline, children }) {
  return (
    <div className="legal-page">
      <div className="legal-page__wrap">
        <Link to="/" className="legal-page__back">← Retour à l'accueil</Link>
        {title ? <h1 className="legal-page__title">{title}</h1> : null}
        {tagline ? <p className="legal-page__tagline">{tagline}</p> : null}
        <div className="legal-page__content">
          {children}
        </div>
      </div>
      <style>{`
        .legal-page {
          min-height: 100vh;
          background: #0D1120;
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
          color: #00F0B5;
          text-decoration: none;
        }
        .legal-page__back:hover { text-decoration: underline; }
        .legal-page__title {
          font-size: 28px;
          font-weight: 800;
          color: #fff;
          margin-bottom: 8px;
          letter-spacing: -0.02em;
        }
        .legal-page__tagline {
          font-size: 16px;
          color: rgba(255,255,255,0.75);
          margin-bottom: 28px;
          font-weight: 500;
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
          color: #00F0B5;
          text-decoration: none;
        }
        .legal-page__content a:hover { text-decoration: underline; }
        .legal-page__hero {
          margin-bottom: 36px;
        }
        .legal-page__hero-title {
          font-size: 26px;
          font-weight: 800;
          color: #fff;
          line-height: 1.25;
          margin: 0 0 16px;
          letter-spacing: -0.02em;
        }
        .legal-page__hero-subtitle {
          font-size: 16px;
          color: rgba(255,255,255,0.85);
          line-height: 1.6;
          margin: 0 0 20px;
        }
        .legal-page__hero-bullets {
          list-style: none;
          padding: 0;
          margin: 0 0 24px;
        }
        .legal-page__hero-bullets li {
          display: flex;
          align-items: center;
          gap: 10px;
          margin-bottom: 10px;
          font-size: 15px;
          color: rgba(255,255,255,0.9);
        }
        .legal-page__hero-check {
          color: #00F0B5;
          font-weight: 700;
        }
        .legal-page__hero-cta {
          display: inline-block;
          background: #00F0B5;
          color: #0D1120;
          font-weight: 700;
          font-size: 16px;
          padding: 14px 24px;
          border-radius: 8px;
          text-decoration: none;
          transition: opacity 0.2s;
        }
        .legal-page__hero-cta:hover {
          opacity: 0.9;
        }
        .legal-page__cta-final {
          margin: 32px 0;
          padding-top: 24px;
          border-top: 1px solid rgba(255,255,255,0.15);
        }
      `}</style>
    </div>
  );
}
