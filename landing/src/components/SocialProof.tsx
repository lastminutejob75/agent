"use client";

import { TrendingUp, Users, Phone, Star } from "lucide-react";
import { useEffect, useState, useRef } from "react";

export default function SocialProof() {
  const stats = [
    { value: 500, suffix: "+", label: "PME clientes", icon: Users },
    { value: 50000, suffix: "+", label: "RDV gérés/mois", icon: Phone },
    { value: 4.9, suffix: "/5", label: "Note moyenne", icon: Star, decimals: 1 },
    { value: 95, suffix: "%", label: "Taux de satisfaction", icon: TrendingUp },
  ];

  return (
    <section className="py-16 bg-gradient-to-br from-gray-50 to-white border-y border-gray-100">
      <div className="container-custom">
        {/* Logos de clients */}
        <div className="text-center mb-12 animate-fade-in">
          <p className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-6">
            Ils nous font confiance
          </p>

          <div className="flex flex-wrap items-center justify-center gap-x-12 gap-y-6 opacity-60 grayscale hover:grayscale-0 transition-all duration-500">
            {["Cabinet Médical Plus", "Plomberie Pro", "Avocat & Associés", "Dentiste Smile", "Coiffure Élégance", "Consulting Expert"].map((name, index) => (
              <div
                key={index}
                className="text-xl font-bold text-gray-700 hover:text-[#0066CC] transition-colors"
                style={{ animationDelay: `${index * 0.1}s` }}
              >
                {name}
              </div>
            ))}
          </div>
        </div>

        {/* Stats animées */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6 mt-12">
          {stats.map((stat, index) => (
            <AnimatedStat
              key={index}
              value={stat.value}
              suffix={stat.suffix}
              label={stat.label}
              icon={stat.icon}
              decimals={stat.decimals}
              delay={index * 0.1}
            />
          ))}
        </div>
      </div>
    </section>
  );
}

function AnimatedStat({
  value,
  suffix,
  label,
  icon: Icon,
  decimals = 0,
  delay = 0,
}: {
  value: number;
  suffix: string;
  label: string;
  icon: any;
  decimals?: number;
  delay?: number;
}) {
  const [count, setCount] = useState(0);
  const [isVisible, setIsVisible] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true);
        }
      },
      { threshold: 0.3 }
    );

    if (ref.current) {
      observer.observe(ref.current);
    }

    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!isVisible) return;

    const duration = 2000; // 2 seconds
    const steps = 60;
    const increment = value / steps;
    const stepDuration = duration / steps;

    let current = 0;
    const timer = setInterval(() => {
      current += increment;
      if (current >= value) {
        setCount(value);
        clearInterval(timer);
      } else {
        setCount(current);
      }
    }, stepDuration);

    return () => clearInterval(timer);
  }, [isVisible, value]);

  return (
    <div
      ref={ref}
      className="text-center p-6 bg-white rounded-xl shadow-soft hover:shadow-medium transition-all card-hover"
      style={{ animationDelay: `${delay}s` }}
    >
      <Icon className="h-8 w-8 text-[#0066CC] mx-auto mb-3" />
      <div className="text-3xl font-bold text-gray-900 mb-1">
        {decimals > 0 ? count.toFixed(decimals) : Math.floor(count).toLocaleString()}
        <span className="text-[#0066CC]">{suffix}</span>
      </div>
      <div className="text-sm text-gray-600 font-medium">{label}</div>
    </div>
  );
}
