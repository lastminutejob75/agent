import { Fragment } from "react";
import { Link } from "react-router-dom";
import { Helmet } from "react-helmet-async";
import LegalPageLayout from "../components/LegalPageLayout";
import {
  SEO_VERTICAL_PAGES,
  SEO_VERTICAL_PATHS,
  PILLAR_PATH,
  SEO_VERTICAL_LABELS,
} from "../config/seoVerticalPages.config";

export default function SeoVerticalPage({ pageKey }) {
  const page = SEO_VERTICAL_PAGES[pageKey];
  if (!page) return null;

  const faqJsonLd = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: page.faq.map(({ q, a }) => ({
      "@type": "Question",
      name: q,
      acceptedAnswer: { "@type": "Answer", text: a },
    })),
  };

  const otherPaths = SEO_VERTICAL_PATHS.filter((p) => p !== pageKey);

  return (
    <>
      <Helmet>
        <script type="application/ld+json">{JSON.stringify(faqJsonLd)}</script>
      </Helmet>
      <LegalPageLayout
        title={page.hero ? undefined : page.h1}
        tagline={page.hero ? undefined : page.tagline}
      >
        {page.hero ? (
          <div className="legal-page__hero">
            <h1 className="legal-page__hero-title">{page.hero.h1}</h1>
            <p className="legal-page__hero-subtitle">{page.hero.subtitle}</p>
            <ul className="legal-page__hero-bullets">
              {page.hero.bullets.map((item, j) => (
                <li key={j}>
                  <span className="legal-page__hero-check">✔</span> {item}
                </li>
              ))}
            </ul>
            <Link to="/creer-assistante?new=1" className="legal-page__hero-cta">
              {page.hero.cta}
            </Link>
          </div>
        ) : null}
        {!page.hero && page.intro?.length ? (
          <div style={{ marginBottom: 24 }}>
            {page.intro.map((paragraph, i) => (
              <Fragment key={i}>
                <p style={{ marginBottom: 12 }}>{paragraph}</p>
                {i === 1 && page.introListItems?.length ? (
                  <ul style={{ marginTop: 8, marginBottom: 12, paddingLeft: 24 }}>
                    {page.introListItems.map((item, j) => (
                      <li key={j}>{item}</li>
                    ))}
                  </ul>
                ) : null}
              </Fragment>
            ))}
          </div>
        ) : null}
        {page.sections.map((section, i) => (
          <section key={i}>
            {section.h2 ? <h2>{section.h2}</h2> : null}
            {section.content ? <p>{section.content}</p> : null}
            {section.listItems?.length ? (
              <ul style={{ marginTop: 8, marginBottom: 0, paddingLeft: 24 }}>
                {section.listItems.map((item, j) => (
                  <li key={j}>{item}</li>
                ))}
              </ul>
            ) : null}
            {section.subContent ? <p style={{ marginTop: 12 }}>{section.subContent}</p> : null}
            {section.subListItems?.length ? (
              <ul style={{ marginTop: 8, marginBottom: 0, paddingLeft: 24 }}>
                {section.subListItems.map((item, j) => (
                  <li key={j}>{item}</li>
                ))}
              </ul>
            ) : null}
          </section>
        ))}
        {page.ctaFinal ? (
          <div className="legal-page__cta-final">
            <Link to="/creer-assistante?new=1" className="legal-page__hero-cta">
              {page.ctaFinal}
            </Link>
          </div>
        ) : null}
        <h2>FAQ</h2>
        {page.faq.map((item, i) => (
          <div key={i} style={{ marginBottom: 20 }}>
            <strong>{item.q}</strong>
            <p style={{ marginTop: 6, marginBottom: 0 }}>{item.a}</p>
          </div>
        ))}
        <div style={{ marginTop: 32, paddingTop: 24, borderTop: "1px solid rgba(255,255,255,0.15)" }}>
          <p style={{ marginBottom: 12, fontWeight: 600, color: "#fff" }}>
            Maillage interne — UWi Medical
          </p>
          {pageKey !== PILLAR_PATH && (
            <p style={{ marginBottom: 8 }}>
              Page pilier : <Link to={PILLAR_PATH}>{SEO_VERTICAL_LABELS[PILLAR_PATH]}</Link>
            </p>
          )}
          <p style={{ marginBottom: 8 }}>
            Par spécialité :{" "}
            {otherPaths.map((path, i) => (
              <span key={path}>
                {i > 0 && " · "}
                <Link to={path}>{SEO_VERTICAL_LABELS[path] || path}</Link>
              </span>
            ))}
          </p>
          <p style={{ marginBottom: 0 }}>
            <Link to="/creer-assistante?new=1">{page.ctaPrimary || "Créer mon assistant"}</Link> ·{" "}
            <Link to="/contact">Contact</Link>
          </p>
        </div>
      </LegalPageLayout>
    </>
  );
}
