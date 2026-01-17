import React, { useState } from "react";
import { ChevronDown } from "lucide-react";

export default function FAQSection() {
  const [openIndex, setOpenIndex] = useState<number | null>(0);

  const faqs = [
    {
      question: "UWI est-il uniquement vocal ?",
      answer: "Non. UWI est multicanal par nature. La voix est le premier canal activé, puis chat, avatar (optionnel) et email selon vos besoins.",
    },
    {
      question: "Et si la demande est complexe ?",
      answer: "UWI qualifie puis transfère à un humain si nécessaire. Objectif : ne jamais perdre la demande et accélérer le traitement.",
    },
    {
      question: "Puis-je contrôler ce que UWI répond ?",
      answer: "Oui. Vous définissez le périmètre, les règles et les réponses autorisées. UWI reste dans un cadre maîtrisé.",
    },
    {
      question: "Quelle est la promesse principale ?",
      answer: "Transformer une demande entrante en action : réponse, rendez-vous, ou transfert humain.",
    },
    {
      question: "Combien de temps prend la configuration ?",
      answer: "Notre équipe configure votre IA personnalisée en moins de 30 minutes. Démarrage immédiat garanti.",
    },
    {
      question: "Y a-t-il un engagement ?",
      answer: "Non. Vous pouvez annuler quand vous voulez en 1 clic. Pas de frais cachés, pas de piège contractuel.",
    },
    {
      question: "UWI fonctionne avec mon agenda ?",
      answer: "Oui. UWI s'intègre avec Google Calendar, Outlook, Calendly et la plupart des solutions d'agenda.",
    },
  ];

  return (
    <section id="faq" className="section-padding bg-gray-50">
      <div className="container-custom">
        <div className="text-center mb-16 animate-slide-up">
          <h2 className="heading-lg mb-4">Questions fréquentes</h2>
          <p className="text-xl text-gray-600 max-w-3xl mx-auto">
            Tout ce que vous devez savoir sur UWI
          </p>
        </div>

        <div className="max-w-4xl mx-auto space-y-4">
          {faqs.map((faq, index) => (
            <div
              key={index}
              className="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-soft hover:shadow-medium transition-all"
            >
              <button
                onClick={() => setOpenIndex(openIndex === index ? null : index)}
                className="w-full flex items-center justify-between p-6 text-left hover:bg-gray-50 transition-colors"
              >
                <span className="text-lg font-semibold text-gray-900 pr-4">{faq.question}</span>
                <ChevronDown
                  className={`h-5 w-5 text-gray-500 flex-shrink-0 transition-transform ${
                    openIndex === index ? "rotate-180" : ""
                  }`}
                />
              </button>
              {openIndex === index && (
                <div className="px-6 pb-6 text-gray-600 leading-relaxed animate-slide-up">
                  {faq.answer}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
