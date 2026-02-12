import React from "react";
import Header from "./Header";
import Hero from "./Hero";
import SocialProof from "./SocialProof";
import ComparisonSection from "./ComparisonSection";
import WorkflowArtisanSection from "./WorkflowArtisanSection";
import CancellationManagementSection from "./CancellationManagementSection";
import SolutionsGridSection from "./SolutionsGridSection";
import UseCasesSection from "./UseCasesSection";
import FeaturesSection from "./FeaturesSection";
import MultiChannelSection from "./MultiChannelSection";
import ROICalculator from "./ROICalculator";
import CTASection from "./CTASection";
import PricingSection from "./PricingSection";
import TestimonialsSection from "./TestimonialsSection";
import TrustSection from "./TrustSection";
import FAQSection from "./FAQSection";
import ContactForm from "./ContactForm";
import Footer from "./Footer";

export default function UwiLanding() {
  return (
    <>
      <Header />
      <main>
        <Hero
          title="Votre IA d'accueil prend vos RDV pendant que vous travaillez"
          subtitle="UWI répond à vos appels 24/7, gère votre agenda automatiquement, et ne manque jamais un client. Sans formation, sans matériel."
        />
        <SocialProof />
        <ComparisonSection />
        <WorkflowArtisanSection />
        <CancellationManagementSection />
        <SolutionsGridSection />
        <UseCasesSection />
        <FeaturesSection />
        <MultiChannelSection />
        <ROICalculator />
        <CTASection />
        <PricingSection />
        <TestimonialsSection />
        <TrustSection />
        <FAQSection />
        <ContactForm />
      </main>
      <Footer />
    </>
  );
}
