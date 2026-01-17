import React from "react";
import { Star, Quote } from "lucide-react";

export default function TestimonialsSection() {
  const testimonials = [
    {
      quote: "UWI a transformé notre accueil. Plus aucun appel manqué, et on a récupéré 30% de temps pour se concentrer sur notre métier.",
      author: "Dr. Marie Dupont",
      role: "Cabinet médical, Dijon",
      rating: 5,
    },
    {
      quote: "En tant qu'artisan, j'étais toujours débordé par les appels. Maintenant, UWI trie et qualifie, je ne perds plus de temps.",
      author: "Pierre Martin",
      role: "Plomberie Pro, Lyon",
      rating: 5,
    },
    {
      quote: "La prise de rendez-vous est devenue fluide. Nos clients sont ravis de la réactivité, et nous avons gagné en organisation.",
      author: "Sophie Bernard",
      role: "Consultante indépendante",
      rating: 5,
    },
  ];

  return (
    <section className="section-padding bg-white">
      <div className="container-custom">
        <div className="text-center mb-16 animate-slide-up">
          <h2 className="heading-lg mb-4">Ils nous font confiance</h2>
          <p className="text-xl text-gray-600 max-w-3xl mx-auto">
            Découvrez ce que nos clients disent de UWI
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-8 max-w-7xl mx-auto">
          {testimonials.map((testimonial, index) => (
            <div
              key={index}
              className="bg-gradient-to-br from-gray-50 to-white border border-gray-200 rounded-2xl p-8 shadow-soft hover:shadow-medium transition-all card-hover animate-slide-up"
              style={{ animationDelay: `${index * 0.1}s` }}
            >
              <Quote className="h-8 w-8 text-[#0066CC] mb-4 opacity-50" />
              
              <div className="flex mb-4">
                {[...Array(testimonial.rating)].map((_, i) => (
                  <Star key={i} className="h-5 w-5 text-yellow-400 fill-yellow-400" />
                ))}
              </div>

              <p className="text-gray-700 mb-6 leading-relaxed italic">
                "{testimonial.quote}"
              </p>

              <div>
                <div className="font-bold text-gray-900">{testimonial.author}</div>
                <div className="text-sm text-gray-600">{testimonial.role}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
