// UWi Medical — Landing nouvelle maquette (navy, teal, mobile-first)
// Route / — CTAs vers /creer-assistante?new=1
import { Suspense, lazy, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  Facebook,
  Linkedin,
  ArrowRight,
  Phone as PhoneLucide,
  Shield,
  CheckCircle,
  Calendar,
  Headphones,
  Compass,
  CalendarCheck,
  ClipboardList,
  AlertTriangle,
  MessageCircle,
  Play,
  User,
  Users,
  Clock,
  PhoneForwarded,
  SlidersHorizontal,
  Lock,
  TrendingUp,
  BellRing,
  Target,
  MoveRight,
  Zap,
  FileText,
  ChevronRight,
  Check,
  CheckCheck,
  X,
  Bot,
  AppWindow,
  Search,
  Mic,
  Link2,
  ShieldCheck,
  AudioWaveform,
  Globe,
  MapPin,
  Car,
  Info,
  HelpCircle,
  Grid3X3,
  Mail,
  ArrowLeftRight,
  Gauge,
  Bell,
  TrendingDown,
} from "lucide-react";
import "./UwiLandingNew.css";
import UwiMaquetteHeroBlock from "./UwiMaquetteHeroBlock";
import UwiSecurite from "./UwiSecurite";
import MedicalHeadsetCrossIcon from "./icons/MedicalHeadsetCrossIcon";
const AgentsMarquee = lazy(() => import("./AgentsMarquee"));
const AgentsSpotlight = lazy(() => import("./AgentsSpotlight"));
const UwiFAQ = lazy(() => import("./UwiFAQ"));
const UwiEngagementPricing = lazy(() => import("./UwiEngagementPricing"));
const UwiTestimonials = lazy(() => import("./UwiTestimonials"));
const UwiCompare = lazy(() => import("./UwiCompare"));

const UWI_FACEBOOK_URL = "https://www.facebook.com/profile.php?id=61579544710923";
const UWI_LINKEDIN_URL = "https://www.linkedin.com/company/uwi-medical/";

const TYPEWRITER_LINES = [
  "Cabinet du Dr. Martin, bonjour ! Je suis UWi, comment puis-je vous aider ?",
  "Je vérifie les disponibilités… Mardi à 10h ou jeudi à 14h30, lequel vous convient ?",
  "Parfait. Mardi 25 à 10h, c'est noté. Une confirmation SMS vous sera envoyée.",
  "Pour un renouvellement, je transmets votre demande au Dr. Martin. Délai : 24h.",
];

function trackLandingClick(name) {
  if (typeof window === "undefined") return;
  const payload = { event: name, source: "landing_main" };
  window.dataLayer?.push(payload);
  if (typeof window.gtag === "function") {
    window.gtag("event", name, { source: "landing_main" });
  }
}

function LogoStethoscope() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4.5 6.5a4 4 0 0 0 8 0V4a.5.5 0 0 0-1 0v2.5a3 3 0 0 1-6 0V4a.5.5 0 0 0-1 0v2.5z" />
      <path d="M8.5 10.5V14a5.5 5.5 0 0 0 11 0v-1.5" />
      <circle cx="19.5" cy="12" r="1.5" />
    </svg>
  );
}

function PhoneIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor">
      <path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07A19.5 19.5 0 013.07 9.8 19.79 19.79 0 01.22 1.18 2 2 0 012.22 0h3a2 2 0 012 1.72c.127.96.361 1.903.7 2.81a2 2 0 01-.45 2.11L6.91 7.91a16 16 0 006.16 6.16l1.27-.72a2 2 0 012.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0122 16.92z" />
    </svg>
  );
}

const STEPS = [
  { num: "1", title: "Connexion agenda", desc: "Connectez votre Google Calendar (ou autre). Les créneaux sont synchronisés en temps réel." },
  { num: "2", title: "Paramétrage", desc: "Définissez vos horaires, la voix de l'assistant et les règles (urgences, renouvellements)." },
  { num: "3", title: "En production", desc: "UWi décroche, prend les RDV et envoie les rappels. Vous restez concentré sur vos patients." },
];

function SpecRow({ num, icon, name, desc, accent, isLast }) {
  const [hovered, setHovered] = useState(false);

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      className="uwi-spec-row-v3"
      style={{
        display: 'grid',
        gridTemplateColumns: '80px 260px 1fr 40px',
        alignItems: 'center',
        padding: '0 56px',
        borderTop: '1px solid #e2e0d8',
        borderBottom: isLast ? '1px solid #e2e0d8' : 'none',
        minHeight: 116,
        position: 'relative',
        background: hovered ? 'white' : 'transparent',
        transition: 'background 0.25s',
        cursor: 'default',
        overflow: 'hidden',
      }}
    >
      <div style={{
        position: 'absolute', left: 0, top: 0, bottom: 0,
        width: 4, background: accent,
        transform: hovered ? 'scaleY(1)' : 'scaleY(0)',
        transformOrigin: 'center',
        transition: 'transform 0.25s cubic-bezier(.4,0,.2,1)',
      }} />
      <div style={{
        fontFamily: "'Syne', sans-serif", fontWeight: 800,
        fontSize: 13, letterSpacing: '0.04em',
        color: hovered ? accent : '#d0cdc5',
        transition: 'color 0.25s',
      }}>{num}</div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '28px 0' }}>
        <div style={{
          width: 48, height: 48, borderRadius: 13,
          border: `1.5px solid ${hovered ? accent : '#e2e0d8'}`,
          background: hovered ? accent : 'white',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 22, flexShrink: 0,
          transform: hovered ? 'scale(1.08)' : 'scale(1)',
          transition: 'background 0.25s, border-color 0.25s, transform 0.25s',
        }}>
          <span style={{ filter: hovered ? 'grayscale(1) brightness(10)' : 'none', transition: 'filter 0.25s' }}>
            {icon}
          </span>
        </div>
        <div style={{
          fontFamily: "'Syne', sans-serif", fontWeight: 700,
          fontSize: 18, letterSpacing: '-0.02em',
          color: hovered ? accent : '#0d1a1b',
          transition: 'color 0.25s',
        }}>{name}</div>
      </div>
      <div className="uwi-spec-row-desc" style={{
        fontSize: 14, fontWeight: 300, color: '#6b7a7b',
        lineHeight: 1.65, paddingRight: 60,
        fontFamily: "'DM Sans', sans-serif",
      }}>{desc}</div>
      <div className="uwi-spec-row-arr" style={{
        width: 36, height: 36, borderRadius: '50%',
        border: `1.5px solid ${hovered ? accent : '#e2e0d8'}`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 16,
        color: hovered ? accent : '#c8c5bc',
        opacity: hovered ? 1 : 0,
        transform: hovered ? 'translateX(0)' : 'translateX(-10px)',
        transition: 'opacity 0.25s, transform 0.25s, border-color 0.25s, color 0.25s',
        flexShrink: 0,
      }}>→</div>
    </div>
  );
}

function DeferredSectionFallback({ minHeight = 320 }) {
  return <div style={{ minHeight }} aria-hidden="true" />;
}

export default function UwiLanding() {
  const navigate = useNavigate();
  const bgRef = useRef(null);
  const waveRef = useRef(null);
  const waveRefDemo = useRef(null);
  const typedRef = useRef(null);
  const waveWrapRef = useRef(null);
  const waveAnimRef = useRef(null);
  const typeTimerRef = useRef(null);
  const [typedLine, setTypedLine] = useState(0);
  const [typedChar, setTypedChar] = useState(0);
  const [deleting, setDeleting] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [stickyVisible, setStickyVisible] = useState(false);

  useEffect(() => {
    const close = (e) => {
      if (!e.target.closest(".burger-btn") && !e.target.closest(".mobile-dropdown")) {
        setMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  // Sticky CTA mobile : visible après ~hero scrollé, masqué près du footer / CTA final
  useEffect(() => {
    const SHOW_AFTER = 600;
    let ticking = false;
    const update = () => {
      const y = window.scrollY;
      const docH = document.documentElement.scrollHeight;
      const winH = window.innerHeight;
      const nearBottom = y + winH > docH - 600;
      setStickyVisible(y > SHOW_AFTER && !nearBottom);
      ticking = false;
    };
    const onScroll = () => {
      if (!ticking) {
        window.requestAnimationFrame(update);
        ticking = true;
      }
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    update();
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  // BG Aurora canvas
  useEffect(() => {
    const c = bgRef.current;
    if (!c) return;
    const ctx = c.getContext("2d");
    const resize = () => {
      c.width = window.innerWidth;
      c.height = window.innerHeight;
    };
    resize();
    window.addEventListener("resize", resize);
    const blobs = [
      { x: 0.5, y: 0, r: 0.65, col: "rgba(0,240,181,0.08)", sp: 0.00022, ph: 0 },
      { x: 0.85, y: 0.78, r: 0.5, col: "rgba(0,163,163,0.06)", sp: 0.00028, ph: 1.3 },
      { x: 0.1, y: 0.6, r: 0.44, col: "rgba(0,230,204,0.05)", sp: 0.00018, ph: 2.6 },
    ];
    const dots = Array.from({ length: 26 }, () => ({
      x: Math.random(),
      y: Math.random(),
      r: Math.random() * 0.9 + 0.25,
      vx: (Math.random() - 0.5) * 9e-5,
      vy: (Math.random() - 0.5) * 9e-5,
      a: Math.random() * 0.28 + 0.06,
    }));
    let t = 0;
    const loop = () => {
      const W = c.width;
      const H = c.height;
      ctx.clearRect(0, 0, W, H);
      ctx.fillStyle = "#0D1120";
      ctx.fillRect(0, 0, W, H);
      ctx.strokeStyle = "rgba(100,160,200,0.12)";
      ctx.lineWidth = 1;
      for (let x = 0; x < W; x += 44) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, H);
        ctx.stroke();
      }
      for (let y = 0; y < H; y += 44) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(W, y);
        ctx.stroke();
      }
      blobs.forEach((b) => {
        const bx = (b.x + Math.sin(t * b.sp * 1000 + b.ph) * 0.07) * W;
        const by = (b.y + Math.cos(t * b.sp * 1000 + b.ph * 1.4) * 0.055) * H;
        const g = ctx.createRadialGradient(bx, by, 0, bx, by, b.r * Math.min(W, H));
        g.addColorStop(0, b.col);
        g.addColorStop(1, "transparent");
        ctx.fillStyle = g;
        ctx.fillRect(0, 0, W, H);
      });
      dots.forEach((d) => {
        d.x += d.vx;
        d.y += d.vy;
        if (d.x < 0) d.x = 1;
        if (d.x > 1) d.x = 0;
        if (d.y < 0) d.y = 1;
        if (d.y > 1) d.y = 0;
        ctx.beginPath();
        ctx.arc(d.x * W, d.y * H, d.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(0,240,181,${d.a})`;
        ctx.fill();
      });
      t++;
      requestAnimationFrame(loop);
    };
    loop();
    return () => window.removeEventListener("resize", resize);
  }, []);

  // Waveform canvas (hero + section démo)
  const setupWave = (canvasRef) => {
    const c = canvasRef.current;
    if (!c) return () => {};
    const ctx = c.getContext("2d");
    let W = 0;
    let H = 0;
    const sz = () => {
      W = c.offsetWidth * (window.devicePixelRatio || 1);
      H = c.offsetHeight * (window.devicePixelRatio || 1);
      c.width = W;
      c.height = H;
    };
    sz();
    window.addEventListener("resize", sz);
    const N = 44;
    const ph = Array.from({ length: N }, () => Math.random() * Math.PI * 2);
    const sp = Array.from({ length: N }, () => 0.035 + Math.random() * 0.04);
    let t = 0;
    const loop = () => {
      ctx.clearRect(0, 0, W, H);
      const bw = W / N;
      const cy = H / 2;
      for (let i = 0; i < N; i++) {
        const amp =
          Math.sin(t * sp[i] + ph[i]) * 0.4 +
          Math.sin(t * sp[i] * 1.9 + ph[i] * 0.55) * 0.3 +
          Math.sin(t * 0.017 + i * 0.23) * 0.3;
        const bh = Math.max(3, Math.abs(amp) * cy * 0.78 + 4);
        const x = i * bw + bw * 0.2;
        const w = bw * 0.52;
        const a = 0.28 + Math.abs(amp) * 0.62;
        const g = ctx.createLinearGradient(0, cy - bh, 0, cy + bh);
        g.addColorStop(0, `rgba(0,240,181,${a * 0.25})`);
        g.addColorStop(0.5, `rgba(0,240,181,${a})`);
        g.addColorStop(1, `rgba(0,240,181,${a * 0.25})`);
        ctx.fillStyle = g;
        ctx.beginPath();
        if (ctx.roundRect) ctx.roundRect(x, cy - bh, w, bh * 2, w / 2);
        else ctx.rect(x, cy - bh, w, bh * 2);
        ctx.fill();
      }
      t++;
      requestAnimationFrame(loop);
    };
    loop();
    return () => window.removeEventListener("resize", sz);
  };
  useEffect(() => {
    return setupWave(waveRef);
  }, []);
  useEffect(() => {
    return setupWave(waveRefDemo);
  }, []);

  // Typewriter
  useEffect(() => {
    const line = TYPEWRITER_LINES[typedLine];
    if (!line) return;
    if (!deleting && typedChar === line.length) {
      const id = setTimeout(() => setDeleting(true), 2600);
      return () => clearTimeout(id);
    }
    const delay = deleting ? 15 : 34;
    const id = setTimeout(() => {
      if (!deleting) {
        if (typedChar < line.length) setTypedChar((c) => c + 1);
      } else {
        if (typedChar > 0) {
          setTypedChar((c) => c - 1);
        } else {
          setDeleting(false);
          setTypedLine((li) => (li + 1) % TYPEWRITER_LINES.length);
        }
      }
    }, delay);
    return () => clearTimeout(id);
  }, [typedLine, typedChar, deleting]);

  // Scroll reveal (sections .reveal)
  useEffect(() => {
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            e.target.classList.add("visible");
            io.unobserve(e.target);
          }
        });
      },
      { threshold: 0.08 }
    );
    const run = () => document.querySelectorAll(".uwi-landing-new .reveal").forEach((el) => io.observe(el));
    run();
    return () => io.disconnect();
  }, []);

  // Waveform animée + typewriter (section démo)
  useEffect(() => {
    const wrap = waveWrapRef.current;
    if (wrap) {
      wrap.innerHTML = '';
      const bars = [];
      for (let i = 0; i < 52; i++) {
        const b = document.createElement('div');
        Object.assign(b.style, {
          width: '3px', borderRadius: '2px',
          background: '#009CA4', height: '4px',
          flexShrink: '0', transition: 'height 0.15s ease',
        });
        wrap.appendChild(b);
        bars.push(b);
      }
      let rafId;
      const animate = () => {
        const t = Date.now() / 400;
        bars.forEach((b, i) => {
          const h = 8 + Math.abs(Math.sin(t + i * 0.35) * Math.sin(t * 0.7 + i * 0.2)) * 44;
          b.style.height = h + 'px';
          const intensity = h / 52;
          b.style.background = `rgba(0, ${Math.round(156 + intensity * 60)}, ${Math.round(164 + intensity * 54)}, ${0.5 + intensity * 0.5})`;
        });
        rafId = requestAnimationFrame(animate);
      };
      animate();
      waveAnimRef.current = rafId;
    }

    const phrases = [
      "Bonjour, cabinet du Dr Martin. Je peux vous aider à prendre, modifier ou annuler un rendez-vous.",
      "Je vous propose le mardi 15 à 10h ou le jeudi 17 à 14h30.",
      "Pour un renouvellement, je transmets votre demande au Dr.",
      "Votre rendez-vous est confirmé, vous recevrez un SMS.",
    ];
    let pi = 0, ci = 0, deleting = false;
    const el = typedRef.current;

    const type = () => {
      if (!el) return;
      const phrase = phrases[pi];
      if (!deleting) {
        el.textContent = phrase.slice(0, ++ci);
        if (ci === phrase.length) {
          deleting = true;
          typeTimerRef.current = setTimeout(type, 2200);
          return;
        }
      } else {
        el.textContent = phrase.slice(0, --ci);
        if (ci === 0) {
          deleting = false;
          pi = (pi + 1) % phrases.length;
          typeTimerRef.current = setTimeout(type, 400);
          return;
        }
      }
      typeTimerRef.current = setTimeout(type, deleting ? 28 : 42);
    };

    typeTimerRef.current = setTimeout(type, 800);

    return () => {
      if (waveAnimRef.current) cancelAnimationFrame(waveAnimRef.current);
      if (typeTimerRef.current) clearTimeout(typeTimerRef.current);
    };
  }, []);

  // Bento cards — particles + 3D tilt
  useEffect(() => {
    const PC = {
      c1: ['rgba(255,255,255,0.9)', 'rgba(200,255,255,0.7)'],
      c2: ['rgba(0,156,164,0.9)', 'rgba(0,212,222,0.7)'],
      c3: ['rgba(93,217,224,0.8)', 'rgba(0,212,222,0.6)'],
      c4: ['rgba(10,31,32,0.6)', 'rgba(0,80,90,0.4)'],
      c5: ['rgba(0,156,164,0.9)', 'rgba(0,212,222,0.6)'],
      c6: ['rgba(0,156,164,0.9)', 'rgba(62,207,142,0.7)'],
    };
    class PS {
      constructor(c, cols) { this.c = c; this.ctx = c.getContext('2d'); this.cols = cols; this.p = []; this.run = false; }
      resize() { const r = this.c.parentElement.getBoundingClientRect(); this.c.width = r.width; this.c.height = r.height; }
      burst() { const cx = this.c.width / 2, cy = this.c.height / 2; for (let i = 0; i < 24; i++) { const a = (i / 24) * Math.PI * 2, s = Math.random() * 6 + 3; this.p.push({ x: cx, y: cy, vx: Math.cos(a) * s, vy: Math.sin(a) * s, sz: Math.random() * 5 + 2, alpha: 1, col: this.cols[Math.floor(Math.random() * this.cols.length)], life: 1 }); } }
      spawn(mx, my) { for (let i = 0; i < 4; i++) this.p.push({ x: mx, y: my, vx: (Math.random() - .5) * 5, vy: (Math.random() - .5) * 5 - 2, sz: Math.random() * 4 + 2, alpha: 1, col: this.cols[Math.floor(Math.random() * this.cols.length)], life: 1 }); }
      tick() { const ctx = this.ctx; ctx.clearRect(0, 0, this.c.width, this.c.height); this.p = this.p.filter(p => p.alpha > .02); for (const p of this.p) { p.x += p.vx; p.y += p.vy; p.vy += .1; p.vx *= .97; p.life -= .022; p.alpha = Math.max(0, p.life); ctx.globalAlpha = p.alpha; ctx.fillStyle = p.col; ctx.beginPath(); ctx.arc(p.x, p.y, p.sz, 0, Math.PI * 2); ctx.fill(); } ctx.globalAlpha = 1; if (this.run || this.p.length > 0) requestAnimationFrame(() => this.tick()); }
      start() { if (this.run) return; this.run = true; this.resize(); this.burst(); this.tick(); }
      stop() { this.run = false; }
    }
    const cleanups = [];
    ['c1', 'c2', 'c3', 'c4', 'c5', 'c6'].forEach(id => {
      const card = document.querySelector(`[data-bento="${id}"]`);
      if (!card) return;
      const canvas = card.querySelector('.uwi-b-particles');
      if (!canvas) return;
      const sys = new PS(canvas, PC[id]);
      const onEnter = () => sys.start();
      const onLeave = () => { sys.stop(); card.style.transform = ''; };
      const onMove = (e) => {
        const r = card.getBoundingClientRect();
        const mx = e.clientX - r.left, my = e.clientY - r.top;
        card.style.setProperty('--mx', (mx / r.width * 100).toFixed(1) + '%');
        card.style.setProperty('--my', (my / r.height * 100).toFixed(1) + '%');
        const rx = ((my / r.height) - .5) * -22, ry = ((mx / r.width) - .5) * 22;
        card.style.transform = `translateY(-20px) scale(1.05) rotateX(${rx}deg) rotateY(${ry}deg)`;
        if (Math.random() > .55) sys.spawn(mx, my);
      };
      card.addEventListener('mouseenter', onEnter);
      card.addEventListener('mouseleave', onLeave);
      card.addEventListener('mousemove', onMove);
      cleanups.push(() => {
        card.removeEventListener('mouseenter', onEnter);
        card.removeEventListener('mouseleave', onLeave);
        card.removeEventListener('mousemove', onMove);
      });
    });
    return () => cleanups.forEach(fn => fn());
  }, []);

  // Smooth scroll pour ancres (nav)
  useEffect(() => {
    const root = document.querySelector(".uwi-landing-new");
    if (!root) return;
    const handleClick = (e) => {
      const a = e.target.closest('a[href^="#"]');
      if (!a || !a.getAttribute("href") || a.getAttribute("href") === "#") return;
      const id = a.getAttribute("href").slice(1);
      const el = document.getElementById(id);
      if (el) {
        e.preventDefault();
        el.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    };
    root.addEventListener("click", handleClick);
    return () => root.removeEventListener("click", handleClick);
  }, []);

  const line = TYPEWRITER_LINES[typedLine] || "";
  const displayed = line.slice(0, typedChar);

  return (
    <div className="uwi-landing-new">
      <canvas id="bg" ref={bgRef} aria-hidden />

      {/* Nav flottante par-dessus le hero */}
      <nav className="landing-nav" style={{ position: 'fixed', top: 0, left: 0, right: 0, zIndex: 50, background: 'rgba(255,255,255,0.92)', backdropFilter: 'blur(12px)', WebkitBackdropFilter: 'blur(12px)', borderBottom: '1px solid rgba(0,0,0,0.06)' }}>
        <Link to="/" className="logo header-logo">
          <div className="logo-mark header-logo-icon">
            <LogoStethoscope />
          </div>
          <div className="logo-copy">
            <span className="logo-name header-logo-name">UWi Medical</span>
            <span className="logo-tag header-logo-subtitle">IA Secrétariat</span>
          </div>
        </Link>
        <div className="nav-links">
          <a href="#assistants">Assistants</a>
          <a href="#metiers">Spécialités</a>
          <a href="#fonctionnalites">Fonctionnalités</a>
          <a href="#comment">Comment ça marche</a>
          <a href="#pricing">Tarifs</a>
          <Link to="/securite">Sécurité</Link>
          <a href="#faq">FAQ</a>
        </div>
        <div className="nav-actions header-right">
          <Link to="/login" className="nav-btn nav-btn--secondary header-link-connexion">Connexion</Link>
          <Link
            to="/creer-assistante?new=1"
            className="nav-btn header-cta"
            onClick={() => trackLandingClick("nav_create_assistant_click")}
          >
            Créer mon assistant
          </Link>
          <button
            type="button"
            className={`burger-btn ${menuOpen ? "open" : ""}`}
            onClick={() => setMenuOpen(!menuOpen)}
            aria-label="Menu"
            aria-expanded={menuOpen}
          >
            <span /><span /><span />
          </button>
        </div>
      </nav>

      {menuOpen && (
        <div className="mobile-dropdown" style={{ position: 'fixed', top: 64, zIndex: 49 }}>
          <Link to="/login" className="dd-item" onClick={() => setMenuOpen(false)}>
            <span className="dd-icon">👤</span>
            <div>
              <div className="dd-label">Connexion</div>
              <div className="dd-sub">Accéder à mon espace</div>
            </div>
          </Link>
          <a href="#pricing" className="dd-item" onClick={() => setMenuOpen(false)}>
            <span className="dd-icon">💳</span>
            <div>
              <div className="dd-label">Tarifs</div>
              <div className="dd-sub">À partir de 99€/mois</div>
            </div>
          </a>
          <a href="#fonctionnalites" className="dd-item" onClick={() => setMenuOpen(false)}>
            <span className="dd-icon">⚡</span>
            <div>
              <div className="dd-label">Fonctionnalités</div>
              <div className="dd-sub">Agenda, triage, RDV 24/7</div>
            </div>
          </a>
          <a href="#metiers" className="dd-item" onClick={() => setMenuOpen(false)}>
            <span className="dd-icon">🏥</span>
            <div>
              <div className="dd-label">Pour les médecins</div>
              <div className="dd-sub">Certifié HDS, RGPD</div>
            </div>
          </a>
          <Link to="/securite" className="dd-item" onClick={() => setMenuOpen(false)}>
            <span className="dd-icon">🔒</span>
            <div>
              <div className="dd-label">Sécurité & confidentialité</div>
              <div className="dd-sub">Trust Center · RGPD · Hébergement EU</div>
            </div>
          </Link>
          <div className="dd-sep" />
          <Link
            to="/creer-assistante?new=1"
            className="dd-cta"
            onClick={() => {
              trackLandingClick("mobile_menu_create_assistant_click");
              setMenuOpen(false);
            }}
          >
            Créer mon assistant — gratuit 1 mois →
          </Link>
        </div>
      )}

      <div style={{ paddingTop: "76px" }}>
        <UwiMaquetteHeroBlock onTrack={trackLandingClick} />
      </div>

      {/* ── SECTION DÉMO VOCALE (double colonne) ── */}
      <section id="demo" className="uwi-voice-demo reveal landing-section">
        <div className="uwi-voice-demo-inner">
          <div className="uwi-voice-demo-left">
            <div className="uwi-voice-demo-badge">
              <span className="uwi-live-dot" aria-hidden />
              Démo vocale en direct
            </div>
            <p className="uwi-voice-demo-ctx">
              <span aria-hidden>🩺</span>
              Scénario cabinet médical · prise de rendez-vous · orientation patient
            </p>
            <h2 className="uwi-voice-demo-title">
              Appelez UWi. Entendez{' '}
              <span className="gold">la différence.</span>
            </h2>
            <p className="uwi-voice-demo-sub">
              Appelez notre numéro de démonstration et vivez l&apos;expérience d&apos;un patient accueilli, compris et orienté en quelques secondes.
            </p>

            <div className="uwi-voice-demo-phone-card">
              <div className="uwi-voice-demo-phone-ico" aria-hidden>
                <PhoneLucide size={22} strokeWidth={2.25} />
              </div>
              <div className="uwi-voice-demo-phone-meta">
                <div className="uwi-voice-demo-phone-label">Numéro de démo :</div>
                <div className="uwi-voice-demo-phone-num">09 39 24 05 75</div>
              </div>
              <div className="uwi-voice-demo-mini-wave" aria-hidden>
                <span /><span /><span /><span /><span />
              </div>
            </div>

            <div className="uwi-voice-demo-ctas">
              <a
                href="tel:0939240575"
                className="uwi-voice-demo-btn-primary"
                onClick={() => trackLandingClick("demo_phone_click")}
              >
                <PhoneLucide size={18} />
                Appeler la démo
              </a>
              <a
                href="#comment"
                className="uwi-voice-demo-btn-secondary"
                onClick={() => trackLandingClick("demo_how_it_works_click")}
              >
                <Play size={18} fill="currentColor" className="opacity-90" />
                Voir comment ça fonctionne
              </a>
            </div>

            <div className="uwi-voice-demo-foot">
              <div className="uwi-voice-demo-foot-item">
                <CheckCircle size={18} strokeWidth={2} />
                Gratuit / Sans frais
              </div>
              <div className="uwi-voice-demo-foot-item">
                <Shield size={18} strokeWidth={2} />
                Sans inscription / Aucune donnée demandée
              </div>
              <div className="uwi-voice-demo-foot-item">
                <User size={18} strokeWidth={2} />
                Sans engagement / Sans obligation
              </div>
            </div>
          </div>

          <div className="uwi-voice-demo-widget">
            <div className="uwi-voice-demo-widget-pad">
              <div className="uwi-vd-badge-d">
                <span className="uwi-live-dot" style={{ background: '#3ecf8e' }} aria-hidden />
                Démo vocale disponible
              </div>

              <div ref={waveWrapRef} className="uwi-voice-demo-wave" />

              <div className="uwi-voice-demo-agent">
                <div className="uwi-voice-demo-av">UWi</div>
                <div className="uwi-voice-demo-agent-txt">
                  <div className="uwi-voice-demo-agent-name">
                    Assistante d&apos;accueil IA — Cabinet Dr Martin
                  </div>
                  <div className="uwi-voice-demo-agent-sub">
                    Répond immédiatement, même pendant les consultations
                  </div>
                </div>
                <div className="uwi-voice-demo-online" title="En ligne" aria-label="En ligne" />
              </div>

              <div className="uwi-voice-demo-bubble">
                <span ref={typedRef} />
                <span
                  style={{
                    display: 'inline-block',
                    width: 2,
                    height: 14,
                    background: '#009CA4',
                    marginLeft: 2,
                    verticalAlign: 'middle',
                    animation: 'uwiCursorBlink 1s step-end infinite',
                  }}
                />
              </div>

              <div className="uwi-voice-demo-tags">
                <span className="uwi-voice-demo-tag">📅 Prise de rendez-vous</span>
                <span className="uwi-voice-demo-tag">✎ Modification</span>
                <span className="uwi-voice-demo-tag">❓ Questions pratiques</span>
              </div>

              <p className="uwi-voice-demo-widget-hint">
                Un appel suffit pour tester l&apos;expérience patient.
              </p>

              <div className="uwi-voice-demo-widget-num-block">
                <p className="uwi-voice-demo-widget-num-label">Numéro de démonstration</p>
                <p className="uwi-voice-demo-widget-num">09 39 24 05 75</p>
              </div>
            </div>

            <a
              href="tel:0939240575"
              className="uwi-voice-demo-btn-primary"
              onClick={() => trackLandingClick("demo_phone_widget_click")}
            >
              <PhoneLucide size={18} />
              Appeler la démo maintenant
            </a>

            <div className="uwi-voice-demo-widget-footer">
              <span><CheckCircle size={14} /> Gratuit</span>
              <span><Shield size={14} /> Sans inscription</span>
              <span><User size={14} /> Sans engagement</span>
            </div>

            <p className="uwi-voice-demo-widget-closing">
              Démo conçue pour les cabinets médicaux : accueil, orientation et gestion des demandes simples.
            </p>
          </div>
        </div>
      </section>

      {/* ── Section Spécialités médicales ── */}
      <section id="metiers" className="uwi-spec uwi-spec-v4 reveal landing-section">
        <div className="uwi-spec-head">
          <p className="uwi-spec-eyebrow">Spécialités médicales</p>
          <h2 className="uwi-spec-title">
            Un accueil patient <em>configuré</em> pour votre cabinet médical
          </h2>
          <p className="uwi-spec-sub">
            Horaires, motifs de rendez-vous, consignes d&apos;urgence, orientation des patients : UWi est paramétré selon votre organisation et mis en service en moins de 48h.
          </p>
          <div className="uwi-spec-benefits">
            <div className="uwi-spec-benefits-track">
              <div className="uwi-spec-ben">
                <span className="uwi-spec-ben-ico" aria-hidden>
                  <Clock size={22} strokeWidth={2} />
                </span>
                <div className="uwi-spec-ben-txt">
                  <strong>48h</strong>
                  <span className="uwi-spec-ben-label">Mise en service</span>
                  <p className="uwi-spec-ben-desc">
                    Configuration, tests d&apos;appel et formation à votre équipe — clés en main.
                  </p>
                  <span className="uwi-spec-ben-tag">Sans engagement</span>
                </div>
              </div>
              <div className="uwi-spec-ben">
                <span className="uwi-spec-ben-ico" aria-hidden>
                  <PhoneForwarded size={22} strokeWidth={2} />
                </span>
                <div className="uwi-spec-ben-txt">
                  <strong>24/7</strong>
                  <span className="uwi-spec-ben-label">Réponse aux appels patients</span>
                  <p className="uwi-spec-ben-desc">
                    Plus aucun appel manqué : UWi décroche le soir, le week-end et pendant vos consultations.
                  </p>
                  <span className="uwi-spec-ben-tag">0 appel perdu</span>
                </div>
              </div>
              <div className="uwi-spec-ben">
                <span className="uwi-spec-ben-ico" aria-hidden>
                  <SlidersHorizontal size={22} strokeWidth={2} />
                </span>
                <div className="uwi-spec-ben-txt">
                  <strong>Vos règles</strong>
                  <span className="uwi-spec-ben-label">Horaires, motifs, consignes</span>
                  <p className="uwi-spec-ben-desc">
                    Vous gardez la main : modifiez votre agenda, vos motifs et vos consignes en quelques clics.
                  </p>
                  <span className="uwi-spec-ben-tag">100% paramétrable</span>
                </div>
              </div>
              {/* Duplicates pour marquee mobile (cachées en desktop, aria-hidden) */}
              <div className="uwi-spec-ben uwi-spec-ben--dup" aria-hidden="true">
                <span className="uwi-spec-ben-ico" aria-hidden>
                  <Clock size={22} strokeWidth={2} />
                </span>
                <div className="uwi-spec-ben-txt">
                  <strong>48h</strong>
                  <span className="uwi-spec-ben-label">Mise en service</span>
                  <p className="uwi-spec-ben-desc">
                    Configuration, tests d&apos;appel et formation à votre équipe — clés en main.
                  </p>
                  <span className="uwi-spec-ben-tag">Sans engagement</span>
                </div>
              </div>
              <div className="uwi-spec-ben uwi-spec-ben--dup" aria-hidden="true">
                <span className="uwi-spec-ben-ico" aria-hidden>
                  <PhoneForwarded size={22} strokeWidth={2} />
                </span>
                <div className="uwi-spec-ben-txt">
                  <strong>24/7</strong>
                  <span className="uwi-spec-ben-label">Réponse aux appels patients</span>
                  <p className="uwi-spec-ben-desc">
                    Plus aucun appel manqué : UWi décroche le soir, le week-end et pendant vos consultations.
                  </p>
                  <span className="uwi-spec-ben-tag">0 appel perdu</span>
                </div>
              </div>
              <div className="uwi-spec-ben uwi-spec-ben--dup" aria-hidden="true">
                <span className="uwi-spec-ben-ico" aria-hidden>
                  <SlidersHorizontal size={22} strokeWidth={2} />
                </span>
                <div className="uwi-spec-ben-txt">
                  <strong>Vos règles</strong>
                  <span className="uwi-spec-ben-label">Horaires, motifs, consignes</span>
                  <p className="uwi-spec-ben-desc">
                    Vous gardez la main : modifiez votre agenda, vos motifs et vos consignes en quelques clics.
                  </p>
                  <span className="uwi-spec-ben-tag">100% paramétrable</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="uwi-spec-list">
          {[
            { num: '01', slug: 'medecine', icon: '🩺', name: 'Médecine générale', desc: "RDV, renouvellements, demandes simples et premières urgences : UWi qualifie l'appel sans interrompre vos consultations.", color: '#009CA4' },
            { num: '02', slug: 'kine', icon: '🤲', name: 'Kinésithérapie', desc: 'UWi propose les créneaux disponibles, confirme les rendez-vous et limite les interruptions pendant les séances.', color: '#7C5CBF' },
            { num: '03', slug: 'dentaire', icon: '🦷', name: 'Cabinets dentaires', desc: 'Contrôles, soins programmés, urgences dentaires : UWi identifie le motif et oriente le patient vers le bon créneau.', color: '#D4873A' },
            { num: '04', slug: 'osteo', icon: '🫀', name: 'Ostéopathes', desc: 'UWi prend les rendez-vous, répond aux questions pratiques et évite les échanges répétitifs entre deux séances.', color: '#C0507A' },
            { num: '05', slug: 'centres', icon: '🏥', name: 'Centres médicaux & cliniques', desc: 'Plusieurs praticiens, flux élevé, demandes variées : UWi qualifie et oriente vers le bon professionnel ou le bon service.', color: '#1A7F6E' },
            { num: '06', slug: 'specialistes', icon: '🧠', name: 'Spécialistes', desc: "Dermatologues, orthophonistes, psychologues, cardiologues : UWi applique vos consignes de prise de rendez-vous et vos règles d'orientation patient.", color: '#5B7FBF' },
          ].map((s) => (
            <article key={s.num} className="uwi-spec-card" style={{ '--a': s.color }}>
              <div className="uwi-spec-card-bar" style={{ background: s.color }} />
              <div className="uwi-spec-card-body">
                <div className="uwi-spec-rname">
                  <div className="uwi-spec-ico"><span>{s.icon}</span></div>
                  <h3 className="uwi-spec-rn">{s.name}</h3>
                </div>
                <p className="uwi-spec-desc">{s.desc}</p>
                <Link
                  to="/creer-assistante?new=1"
                  className="uwi-spec-config-btn"
                  onClick={() => trackLandingClick(`spec_configure_${s.slug}_click`)}
                >
                  Configurer <span aria-hidden>→</span>
                </Link>
              </div>
            </article>
          ))}
        </div>

        <div className="uwi-spec-cta-wrap">
          <div className="uwi-spec-cta uwi-spec-cta-v4">
            <div className="uwi-spec-cta-left">
              <p className="uwi-spec-cta-title">Votre spécialité n&apos;est pas listée ?</p>
              <p className="uwi-spec-cta-sub">
                On configure UWi avec vos horaires, vos motifs de rendez-vous, vos consignes d&apos;urgence et vos règles d&apos;orientation patient.
              </p>
              <div className="uwi-spec-cta-btns">
                <a
                  href="#demo"
                  className="uwi-spec-btn-g"
                  onClick={() => trackLandingClick("spec_cta_demo_click")}
                >
                  <Play size={16} fill="currentColor" className="uwi-spec-btn-play" />
                  Voir la démo live
                </a>
                <Link
                  to="/creer-assistante?new=1"
                  className="uwi-spec-btn-p"
                  onClick={() => trackLandingClick("spec_cta_create_assistant_click")}
                >
                  Créer mon assistant →
                </Link>
              </div>
            </div>
            <div className="uwi-spec-cta-visual" aria-hidden>
              <div className="uwi-spec-cta-glow" />
              <MedicalHeadsetCrossIcon className="uwi-spec-headset" size={120} />
            </div>
          </div>

          <div className="uwi-spec-trust">
            <div className="uwi-spec-trust-item">
              <Shield size={18} strokeWidth={2} aria-hidden />
              <span>Données sécurisées — Chiffrement de bout en bout</span>
            </div>
            <div className="uwi-spec-trust-item">
              <span className="uwi-spec-trust-flag" aria-hidden>🇫🇷</span>
              <span>Hébergement en France — Infrastructure certifiée</span>
            </div>
            <div className="uwi-spec-trust-item">
              <Lock size={18} strokeWidth={2} aria-hidden />
              <span>Conforme RGPD — Respect de vos obligations</span>
            </div>
          </div>
        </div>
      </section>

      <section id="fonctionnalites" className="uwi-feat reveal">
        <div className="uwi-feat-wrap">

          <div className="uwi-feat-block">
          <h3 className="uwi-feat-block-title">
            <Calendar size={16} strokeWidth={2.2} aria-hidden />
            Gestion des rendez-vous &amp; accueil patient
          </h3>
          <article className="uwi-feat-card uwi-feat-card--page-publique">
            <div className="uwi-feat-card-head">
              <span className="uwi-feat-card-eyebrow">
                <Calendar size={14} strokeWidth={2.2} aria-hidden />
                Page publique du cabinet
              </span>
              <h2 className="uwi-feat-card-title">
                Une page patient claire pour informer, orienter et{" "}
                <span className="uwi-feat-card-title-hl">faciliter les rendez-vous</span>
              </h2>
              <p className="uwi-feat-card-desc">
                UWi crée une page publique professionnelle pour votre cabinet. Les patients y trouvent les informations utiles, peuvent faire une demande de rendez-vous et poser une question simplement, depuis un point d&apos;entrée unique.
              </p>
              <div className="uwi-feat-card-chips">
                <span className="uwi-feat-chip">
                  <span className="uwi-feat-chip-google" aria-hidden>
                    <svg viewBox="0 0 24 24" width="14" height="14">
                      <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                      <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84A11 11 0 0 0 12 23z"/>
                      <path fill="#FBBC05" d="M5.84 14.1A6.6 6.6 0 0 1 5.5 12c0-.73.13-1.44.34-2.1V7.06H2.18A11 11 0 0 0 1 12c0 1.78.43 3.46 1.18 4.94l3.66-2.84z"/>
                      <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84C6.71 7.31 9.14 5.38 12 5.38z"/>
                    </svg>
                  </span>
                  Visible sur Google
                </span>
                <span className="uwi-feat-chip">
                  <Info size={14} strokeWidth={2.2} aria-hidden />
                  Infos pratiques
                </span>
                <span className="uwi-feat-chip">
                  <Calendar size={14} strokeWidth={2.2} aria-hidden />
                  Demande de RDV
                </span>
              </div>
            </div>

            <div className="uwi-feat-mock" aria-hidden>
              <div className="uwi-feat-mock-top">
                <div className="uwi-feat-mock-identity">
                  <div className="uwi-feat-mock-avatar">MR</div>
                  <div className="uwi-feat-mock-id-text">
                    <h3 className="uwi-feat-mock-name">Dr Marie Rousseau</h3>
                    <p className="uwi-feat-mock-meta">Cardiologue · Lille</p>
                    <span className="uwi-feat-mock-ref">
                      <Check size={12} strokeWidth={3} aria-hidden />
                      Référencé
                    </span>
                  </div>
                </div>
                <div className="uwi-feat-mock-photo">
                  <div className="uwi-feat-page-preview" aria-hidden>
                    <div className="uwi-feat-page-preview-bar">
                      <span className="uwi-feat-page-preview-dot" />
                      <span className="uwi-feat-page-preview-dot" />
                      <span className="uwi-feat-page-preview-dot" />
                      <span className="uwi-feat-page-preview-url">uwi.fr/dr-marie-rousseau</span>
                    </div>
                    <div className="uwi-feat-page-preview-chat">
                      <div className="uwi-feat-page-preview-bubble uwi-feat-page-preview-bubble--bot">
                        <span className="uwi-feat-page-preview-bot-av"><Bot size={12} strokeWidth={2.2} /></span>
                        <p>Bonjour, je peux vous aider pour un rendez-vous ?</p>
                      </div>
                      <div className="uwi-feat-page-preview-bubble uwi-feat-page-preview-bubble--user">
                        <p>Oui, demain matin si possible</p>
                      </div>
                      <div className="uwi-feat-page-preview-bubble uwi-feat-page-preview-bubble--bot">
                        <span className="uwi-feat-page-preview-bot-av"><Bot size={12} strokeWidth={2.2} /></span>
                        <p>Bien sûr — 9h00 ou 10h30 ?</p>
                      </div>
                      <div className="uwi-feat-page-preview-slots">
                        <span>9h00</span>
                        <span>10h30</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="uwi-feat-mock-grid">
                <div className="uwi-feat-mock-info">
                  <span className="uwi-feat-mock-info-ico"><MapPin size={16} strokeWidth={2} /></span>
                  <strong>Adresse</strong>
                  <span>12 rue Faidherbe<br />59000 Lille</span>
                </div>
                <div className="uwi-feat-mock-info">
                  <span className="uwi-feat-mock-info-ico"><Clock size={16} strokeWidth={2} /></span>
                  <strong>Horaires</strong>
                  <span>Lun. – Ven. 8h30 – 18h30<br />Sam. 8h30 – 12h30</span>
                </div>
                <div className="uwi-feat-mock-info">
                  <span className="uwi-feat-mock-info-ico"><Car size={16} strokeWidth={2} /></span>
                  <strong>Accès</strong>
                  <span>Métro République<br />Parking à proximité</span>
                </div>
                <div className="uwi-feat-mock-actions">
                  <span className="uwi-feat-mock-btn uwi-feat-mock-btn--primary">
                    <Calendar size={14} strokeWidth={2.2} aria-hidden />
                    Prendre rendez-vous
                    <ChevronRight size={14} strokeWidth={2.2} aria-hidden />
                  </span>
                  <span className="uwi-feat-mock-btn">
                    <MessageCircle size={14} strokeWidth={2.2} aria-hidden />
                    Poser une question
                  </span>
                  <span className="uwi-feat-mock-btn">
                    <Info size={14} strokeWidth={2.2} aria-hidden />
                    Infos pratiques
                  </span>
                </div>
              </div>

              <div className="uwi-feat-mock-bottom">
                <div className="uwi-feat-mock-bot">
                  <span className="uwi-feat-mock-bot-ico"><Bot size={20} strokeWidth={2} /></span>
                  <p>Bonjour, je peux vous aider pour votre rendez-vous ou une question pratique.</p>
                </div>
                <div className="uwi-feat-mock-slots">
                  <div className="uwi-feat-mock-slots-head">
                    <strong>Prochains créneaux disponibles</strong>
                    <span className="uwi-feat-mock-slots-more">Voir plus <ChevronRight size={12} strokeWidth={2.2} aria-hidden /></span>
                  </div>
                  <div className="uwi-feat-mock-slots-list">
                    <span className="uwi-feat-mock-slot">
                      <strong>Lun. 26 mai</strong>
                      <em>09:00</em>
                    </span>
                    <span className="uwi-feat-mock-slot">
                      <strong>Lun. 26 mai</strong>
                      <em>11:30</em>
                    </span>
                    <span className="uwi-feat-mock-slot">
                      <strong>Mar. 27 mai</strong>
                      <em>14:00</em>
                    </span>
                    <span className="uwi-feat-mock-slot">
                      <strong>Mer. 28 mai</strong>
                      <em>10:30</em>
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </article>
          </div>

          <div className="uwi-feat-block">
          <h3 className="uwi-feat-block-title">
            <PhoneLucide size={16} strokeWidth={2.2} aria-hidden />
            Standard téléphonique &amp; orientation patient
          </h3>
          <article className="uwi-feat-card uwi-feat-card--telephone">
            <div className="uwi-feat-tel-top">
              <div className="uwi-feat-card-head uwi-feat-card-head--tel">
                <span className="uwi-feat-card-eyebrow">
                  <PhoneLucide size={14} strokeWidth={2.2} aria-hidden />
                  Ligne téléphonique du cabinet
                </span>
                <h2 className="uwi-feat-card-title">
                  Une voix qui{" "}
                  <span className="uwi-feat-card-title-hl">répond, rassure</span>{" "}
                  et <span className="uwi-feat-card-title-hl">oriente</span>{" "}
                  vos patients
                </h2>
                <p className="uwi-feat-card-desc">
                  UWi prend en charge les appels de votre cabinet via une ligne dédiée. Vos patients appellent un numéro clair, sont accueillis par une voix rassurante et orientés vers la bonne action : rendez-vous, information pratique, message ou transfert si nécessaire.
                </p>
                <div className="uwi-feat-card-chips">
                  <span className="uwi-feat-chip">
                    <PhoneLucide size={14} strokeWidth={2.2} aria-hidden />
                    Ligne dédiée
                  </span>
                  <span className="uwi-feat-chip">
                    <Grid3X3 size={14} strokeWidth={2.2} aria-hidden />
                    Numéro du cabinet
                  </span>
                  <span className="uwi-feat-chip">
                    <ArrowLeftRight size={14} strokeWidth={2.2} aria-hidden />
                    Orientation des appels
                  </span>
                </div>

                <div className="uwi-feat-tel-row" aria-hidden>
                  <div className="uwi-feat-tel-number">
                    <span className="uwi-feat-tel-number-ico">
                      <PhoneLucide size={26} strokeWidth={2} />
                    </span>
                    <div className="uwi-feat-tel-number-body">
                      <span className="uwi-feat-tel-number-lbl">Numéro dédié au cabinet</span>
                      <strong className="uwi-feat-tel-number-val">09 39 24 05 75</strong>
                      <span className="uwi-feat-tel-number-trust">
                        <Check size={12} strokeWidth={3} aria-hidden />
                        Ligne exclusive pour vos patients
                      </span>
                    </div>
                  </div>
                  <div className="uwi-feat-tel-active">
                    <div className="uwi-feat-tel-active-head">
                      <span>Ligne active</span>
                      <span className="uwi-feat-tel-dot" aria-hidden />
                    </div>
                    <div className="uwi-feat-tel-wave" aria-hidden>
                      {Array.from({ length: 18 }).map((_, i) => (
                        <span
                          key={i}
                          style={{
                            height: `${30 + Math.abs(Math.sin((i + 1) * 0.9)) * 60}%`,
                            animationDelay: `${i * 0.06}s`,
                          }}
                        />
                      ))}
                    </div>
                    <div className="uwi-feat-tel-active-call">
                      <span className="uwi-feat-tel-active-call-ico">
                        <PhoneLucide size={14} strokeWidth={2.4} />
                      </span>
                      <div>
                        <strong>Appel entrant</strong>
                        <span>Patient</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="uwi-feat-tel-photo" aria-hidden />

            </div>

            <div className="uwi-feat-tel-clara">
              <div className="uwi-feat-tel-clara-text">
                <h3 className="uwi-feat-tel-clara-title">
                  <span className="uwi-feat-tel-clara-title-hl">Clara</span> répond pour votre cabinet
                </h3>
                <p>
                  Elle accueille chaque patient avec bienveillance, comprend sa demande et l&apos;oriente vers la bonne action.
                </p>
              </div>
              <div className="uwi-feat-tel-actions">
                <div className="uwi-feat-tel-action">
                  <span className="uwi-feat-tel-action-ico"><Calendar size={18} strokeWidth={2} aria-hidden /></span>
                  <strong>Rendez-vous</strong>
                  <span>Prise ou modification de rendez-vous</span>
                </div>
                <div className="uwi-feat-tel-action">
                  <span className="uwi-feat-tel-action-ico"><Info size={18} strokeWidth={2} aria-hidden /></span>
                  <strong>Information pratique</strong>
                  <span>Horaires, accès, préparation…</span>
                </div>
                <div className="uwi-feat-tel-action">
                  <span className="uwi-feat-tel-action-ico"><Mail size={18} strokeWidth={2} aria-hidden /></span>
                  <strong>Message</strong>
                  <span>Prise de message pour le cabinet</span>
                </div>
                <div className="uwi-feat-tel-action">
                  <span className="uwi-feat-tel-action-ico"><ArrowLeftRight size={18} strokeWidth={2} aria-hidden /></span>
                  <strong>Transfert</strong>
                  <span>Mise en relation si nécessaire</span>
                </div>
              </div>
            </div>

            <div className="uwi-feat-tel-foot">
              <ShieldCheck size={16} strokeWidth={2.2} aria-hidden />
              <span>
                Un accueil professionnel, une expérience patient apaisée, un cabinet plus efficace.
              </span>
            </div>
          </article>
          </div>

          <div className="uwi-feat-block">
          <h3 className="uwi-feat-block-title">
            <Gauge size={16} strokeWidth={2.2} aria-hidden />
            Dashboard praticien &amp; pilotage du cabinet
          </h3>
          <article className="uwi-feat-card uwi-feat-card--dashboard">
            <div className="uwi-feat-card-head">
              <span className="uwi-feat-card-eyebrow">
                <Gauge size={14} strokeWidth={2.2} aria-hidden />
                Tableau de bord praticien
              </span>
              <h2 className="uwi-feat-card-title">
                Un <span className="uwi-feat-card-title-hl">dashboard clair</span> pour piloter votre{" "}
                <span className="uwi-feat-card-title-hl">activité patient</span>
              </h2>
              <p className="uwi-feat-card-desc">
                Le praticien retrouve au même endroit les demandes patients, la synthèse des appels, son agenda et les actions à traiter. Une vue simple pour suivre l&apos;activité du cabinet au quotidien.
              </p>
              <div className="uwi-feat-card-chips">
                <span className="uwi-feat-chip">
                  <ClipboardList size={14} strokeWidth={2.2} aria-hidden />
                  Demandes patients
                </span>
                <span className="uwi-feat-chip">
                  <PhoneLucide size={14} strokeWidth={2.2} aria-hidden />
                  Synthèses d&apos;appels
                </span>
                <span className="uwi-feat-chip">
                  <Calendar size={14} strokeWidth={2.2} aria-hidden />
                  Agenda du cabinet
                </span>
              </div>
            </div>

            <div className="uwi-feat-dash-mock" aria-hidden>
              <div className="uwi-feat-dash-header">
                <div className="uwi-feat-dash-identity">
                  <div className="uwi-feat-mock-avatar">MR</div>
                  <div className="uwi-feat-dash-id-text">
                    <strong>Dr Marie Rousseau</strong>
                    <span>
                      Cardiologue · Lille
                      <span className="uwi-feat-dash-status">
                        <span className="uwi-feat-dash-status-dot" />
                        Cabinet actif
                      </span>
                    </span>
                  </div>
                </div>
                <div className="uwi-feat-dash-quick">
                  <span className="uwi-feat-dash-quick-btn"><Bell size={16} strokeWidth={2} /></span>
                  <span className="uwi-feat-dash-quick-btn"><Mail size={16} strokeWidth={2} /></span>
                  <span className="uwi-feat-dash-quick-btn"><User size={16} strokeWidth={2} /></span>
                </div>
              </div>

              <div className="uwi-feat-dash-stats">
                <div className="uwi-feat-dash-stat uwi-feat-dash-stat--orange">
                  <span className="uwi-feat-dash-stat-ico"><Calendar size={16} strokeWidth={2} /></span>
                  <strong>12</strong>
                  <span>Demandes à traiter</span>
                  <em>+3 depuis hier</em>
                </div>
                <div className="uwi-feat-dash-stat">
                  <span className="uwi-feat-dash-stat-ico"><PhoneLucide size={16} strokeWidth={2} /></span>
                  <strong>28</strong>
                  <span>Appels aujourd&apos;hui</span>
                  <em>+6 depuis hier</em>
                </div>
                <div className="uwi-feat-dash-stat">
                  <span className="uwi-feat-dash-stat-ico"><CheckCircle size={16} strokeWidth={2} /></span>
                  <strong>18</strong>
                  <span>RDV confirmés</span>
                  <em>+2 depuis hier</em>
                </div>
                <div className="uwi-feat-dash-stat">
                  <span className="uwi-feat-dash-stat-ico"><MessageCircle size={16} strokeWidth={2} /></span>
                  <strong>7</strong>
                  <span>Messages patients</span>
                  <em>+1 depuis hier</em>
                </div>
              </div>

              <div className="uwi-feat-dash-grid">
                <div className="uwi-feat-dash-col">
                  <div className="uwi-feat-dash-col-head">
                    <span className="uwi-feat-dash-col-dot uwi-feat-dash-col-dot--orange" />
                    Demandes patients
                  </div>
                  <ul className="uwi-feat-dash-list">
                    <li>
                      <div className="uwi-feat-dash-li-text">
                        <strong>Paul Martin</strong>
                        <span>Rappel demandé</span>
                      </div>
                      <span className="uwi-feat-dash-li-time">09:12</span>
                      <span className="uwi-feat-dash-tag uwi-feat-dash-tag--new">Nouveau</span>
                    </li>
                    <li>
                      <div className="uwi-feat-dash-li-text">
                        <strong>Sophie Leroy</strong>
                        <span>Question pratique</span>
                      </div>
                      <span className="uwi-feat-dash-li-time">08:47</span>
                      <span className="uwi-feat-dash-tag uwi-feat-dash-tag--prog">En cours</span>
                    </li>
                    <li>
                      <div className="uwi-feat-dash-li-text">
                        <strong>Thomas Bernard</strong>
                        <span>Confirmation de RDV</span>
                      </div>
                      <span className="uwi-feat-dash-li-time">Hier</span>
                      <span className="uwi-feat-dash-tag uwi-feat-dash-tag--done">Traité</span>
                    </li>
                  </ul>
                  <span className="uwi-feat-dash-col-link">Voir toutes les demandes <ChevronRight size={12} strokeWidth={2.2} /></span>
                </div>

                <div className="uwi-feat-dash-col">
                  <div className="uwi-feat-dash-col-head">
                    <span className="uwi-feat-dash-col-dot uwi-feat-dash-col-dot--blue" />
                    Synthèse des appels
                  </div>
                  <ul className="uwi-feat-dash-list">
                    <li>
                      <span className="uwi-feat-dash-li-time">11:24</span>
                      <div className="uwi-feat-dash-li-text">
                        <strong>Claire Dupont</strong>
                        <span>Patient souhaite déplacer son rendez-vous</span>
                      </div>
                      <span className="uwi-feat-dash-tag uwi-feat-dash-tag--blue">Déplacé</span>
                    </li>
                    <li>
                      <span className="uwi-feat-dash-li-time">10:05</span>
                      <div className="uwi-feat-dash-li-text">
                        <strong>Julien Morel</strong>
                        <span>Question sur horaires</span>
                      </div>
                      <span className="uwi-feat-dash-tag uwi-feat-dash-tag--done">Répondu</span>
                    </li>
                    <li>
                      <span className="uwi-feat-dash-li-time">09:18</span>
                      <div className="uwi-feat-dash-li-text">
                        <strong>Message laissé</strong>
                        <span>Message laissé pour le cabinet</span>
                      </div>
                      <span className="uwi-feat-dash-tag uwi-feat-dash-tag--new">À rappeler</span>
                    </li>
                  </ul>
                  <span className="uwi-feat-dash-col-link">Voir toutes les synthèses <ChevronRight size={12} strokeWidth={2.2} /></span>
                </div>

                <div className="uwi-feat-dash-col">
                  <div className="uwi-feat-dash-col-head">
                    <span className="uwi-feat-dash-col-dot uwi-feat-dash-col-dot--teal" />
                    Agenda du jour
                  </div>
                  <ul className="uwi-feat-dash-list uwi-feat-dash-list--agenda">
                    <li>
                      <span className="uwi-feat-dash-time">09:00</span>
                      <div className="uwi-feat-dash-slot">
                        <strong>Jean Durand</strong>
                        <span>Consultation</span>
                      </div>
                    </li>
                    <li className="uwi-feat-dash-slot-active">
                      <span className="uwi-feat-dash-time">10:30</span>
                      <div className="uwi-feat-dash-slot">
                        <strong>Claire Martin</strong>
                        <span>Consultation</span>
                      </div>
                    </li>
                    <li>
                      <span className="uwi-feat-dash-time">14:00</span>
                      <div className="uwi-feat-dash-slot">
                        <strong>Paul Bernard</strong>
                        <span>Consultation</span>
                      </div>
                    </li>
                    <li>
                      <span className="uwi-feat-dash-time">16:15</span>
                      <div className="uwi-feat-dash-slot">
                        <strong>Sophie Leroy</strong>
                        <span>Suivi</span>
                      </div>
                    </li>
                  </ul>
                  <span className="uwi-feat-dash-col-link">Voir l&apos;agenda complet <ChevronRight size={12} strokeWidth={2.2} /></span>
                </div>
              </div>

              <div className="uwi-feat-dash-bar">
                <span className="uwi-feat-dash-bar-label">
                  <Zap size={14} strokeWidth={2.4} />
                  Actions rapides
                </span>
                <span className="uwi-feat-dash-bar-btn">
                  <ClipboardList size={14} strokeWidth={2} />
                  Voir les demandes
                </span>
                <span className="uwi-feat-dash-bar-btn">
                  <Calendar size={14} strokeWidth={2} />
                  Ouvrir l&apos;agenda
                </span>
                <span className="uwi-feat-dash-bar-btn">
                  <PhoneLucide size={14} strokeWidth={2} />
                  Rappeler un patient
                </span>
                <span className="uwi-feat-dash-bar-btn">
                  <FileText size={14} strokeWidth={2} />
                  Lire les synthèses
                </span>
              </div>
            </div>

            <div className="uwi-feat-tel-foot">
              <ShieldCheck size={16} strokeWidth={2.2} aria-hidden />
              <span>
                Tout ce qu&apos;il faut pour suivre les patients et l&apos;activité du cabinet, en un coup d&apos;œil.
              </span>
            </div>
          </article>
          </div>

          <div className="uwi-feat-block">
          <h3 className="uwi-feat-block-title">
            <CalendarCheck size={16} strokeWidth={2.2} aria-hidden />
            Réduction des no-shows &amp; optimisation du planning
          </h3>
          <article className="uwi-feat-card uwi-feat-card--noshow">
            <div className="uwi-feat-noshow-top">
              <div className="uwi-feat-card-head uwi-feat-card-head--noshow">
                <span className="uwi-feat-card-eyebrow">
                  <Bell size={14} strokeWidth={2.2} aria-hidden />
                  Rappels patients &amp; anti no-show
                </span>
                <h2 className="uwi-feat-card-title">
                  Moins de rendez-vous oubliés, plus de{" "}
                  <span className="uwi-feat-card-title-hl">créneaux honorés</span>
                </h2>
                <p className="uwi-feat-card-desc">
                  UWi aide le cabinet à réduire les absences grâce aux rappels, aux confirmations de rendez-vous et au suivi des patients. Résultat : moins de no-shows, un agenda plus fiable et des créneaux mieux utilisés.
                </p>
                <div className="uwi-feat-card-chips">
                  <span className="uwi-feat-chip">
                    <Bell size={14} strokeWidth={2.2} aria-hidden />
                    Rappels automatiques
                  </span>
                  <span className="uwi-feat-chip">
                    <CheckCircle size={14} strokeWidth={2.2} aria-hidden />
                    Confirmation patient
                  </span>
                  <span className="uwi-feat-chip">
                    <Calendar size={14} strokeWidth={2.2} aria-hidden />
                    Créneaux mieux remplis
                  </span>
                </div>
              </div>

              <div className="uwi-feat-noshow-photo" aria-hidden />
            </div>

            <div className="uwi-feat-dash-mock" aria-hidden>
              <div className="uwi-feat-dash-stats">
                <div className="uwi-feat-dash-stat">
                  <span className="uwi-feat-dash-stat-ico"><Bell size={16} strokeWidth={2} /></span>
                  <strong>24</strong>
                  <span>Rappels envoyés</span>
                  <em>+6 aujourd&apos;hui</em>
                </div>
                <div className="uwi-feat-dash-stat">
                  <span className="uwi-feat-dash-stat-ico"><CheckCircle size={16} strokeWidth={2} /></span>
                  <strong>18</strong>
                  <span>RDV confirmés</span>
                  <em>+4 aujourd&apos;hui</em>
                </div>
                <div className="uwi-feat-dash-stat">
                  <span className="uwi-feat-dash-stat-ico"><Calendar size={16} strokeWidth={2} /></span>
                  <strong>3</strong>
                  <span>Créneaux libérés</span>
                  <em>+2 aujourd&apos;hui</em>
                </div>
                <div className="uwi-feat-dash-stat uwi-feat-dash-stat--success">
                  <span className="uwi-feat-dash-stat-ico"><TrendingDown size={16} strokeWidth={2} /></span>
                  <strong>−32%</strong>
                  <span>No-shows</span>
                  <em>vs semaine passée</em>
                </div>
              </div>

              <div className="uwi-feat-dash-grid">
                <div className="uwi-feat-dash-col">
                  <div className="uwi-feat-dash-col-head">
                    <span className="uwi-feat-dash-col-dot uwi-feat-dash-col-dot--orange" />
                    Patients à relancer
                  </div>
                  <ul className="uwi-feat-dash-list uwi-feat-dash-list--patients">
                    <li>
                      <span className="uwi-feat-dash-pat-av">CM</span>
                      <div className="uwi-feat-dash-li-text">
                        <strong>Claire Martin</strong>
                        <span>Rappel à envoyer</span>
                      </div>
                      <span className="uwi-feat-dash-li-time">09:00</span>
                      <span className="uwi-feat-dash-tag uwi-feat-dash-tag--new">À faire</span>
                    </li>
                    <li>
                      <span className="uwi-feat-dash-pat-av">PB</span>
                      <div className="uwi-feat-dash-li-text">
                        <strong>Paul Bernard</strong>
                        <span>En attente de réponse</span>
                      </div>
                      <span className="uwi-feat-dash-li-time">14:00</span>
                      <span className="uwi-feat-dash-tag uwi-feat-dash-tag--prog">En cours</span>
                    </li>
                    <li>
                      <span className="uwi-feat-dash-pat-av">SL</span>
                      <div className="uwi-feat-dash-li-text">
                        <strong>Sophie Leroy</strong>
                        <span>Confirmation reçue</span>
                      </div>
                      <span className="uwi-feat-dash-li-time">16:15</span>
                      <span className="uwi-feat-dash-tag uwi-feat-dash-tag--done">Confirmé</span>
                    </li>
                    <li>
                      <span className="uwi-feat-dash-pat-av">JD</span>
                      <div className="uwi-feat-dash-li-text">
                        <strong>Jean Durand</strong>
                        <span>Créneau libéré</span>
                      </div>
                      <span className="uwi-feat-dash-li-time">10:30</span>
                      <span className="uwi-feat-dash-tag uwi-feat-dash-tag--new">À recontacter</span>
                    </li>
                  </ul>
                  <span className="uwi-feat-dash-col-link">Voir tous les patients <ChevronRight size={12} strokeWidth={2.2} /></span>
                </div>

                <div className="uwi-feat-dash-col">
                  <div className="uwi-feat-dash-col-head">
                    <span className="uwi-feat-dash-col-dot uwi-feat-dash-col-dot--blue" />
                    Suivi des confirmations
                  </div>
                  <ul className="uwi-feat-dash-list uwi-feat-dash-list--suivi">
                    <li>
                      <span className="uwi-feat-dash-suivi-ico"><MessageCircle size={14} strokeWidth={2} /></span>
                      <div className="uwi-feat-dash-li-text">
                        <strong>SMS envoyé</strong>
                        <span>RDV confirmé</span>
                      </div>
                      <span className="uwi-feat-dash-li-time">09:02</span>
                      <span className="uwi-feat-dash-tag uwi-feat-dash-tag--done">Confirmé</span>
                    </li>
                    <li>
                      <span className="uwi-feat-dash-suivi-ico"><User size={14} strokeWidth={2} /></span>
                      <div className="uwi-feat-dash-li-text">
                        <strong>Patient indisponible</strong>
                        <span>créneau libéré</span>
                      </div>
                      <span className="uwi-feat-dash-li-time">10:15</span>
                      <span className="uwi-feat-dash-tag uwi-feat-dash-tag--new">Libéré</span>
                    </li>
                    <li>
                      <span className="uwi-feat-dash-suivi-ico"><PhoneLucide size={14} strokeWidth={2} /></span>
                      <div className="uwi-feat-dash-li-text">
                        <strong>Rappel vocal effectué</strong>
                        <span>en attente</span>
                      </div>
                      <span className="uwi-feat-dash-li-time">11:08</span>
                      <span className="uwi-feat-dash-tag uwi-feat-dash-tag--prog">En attente</span>
                    </li>
                    <li>
                      <span className="uwi-feat-dash-suivi-ico"><Calendar size={14} strokeWidth={2} /></span>
                      <div className="uwi-feat-dash-li-text">
                        <strong>Annulation anticipée</strong>
                        <span>créneau reproposé</span>
                      </div>
                      <span className="uwi-feat-dash-li-time">12:30</span>
                      <span className="uwi-feat-dash-tag uwi-feat-dash-tag--blue">Replanifié</span>
                    </li>
                  </ul>
                  <span className="uwi-feat-dash-col-link">Voir tout le suivi <ChevronRight size={12} strokeWidth={2.2} /></span>
                </div>

                <div className="uwi-feat-dash-col">
                  <div className="uwi-feat-dash-col-head">
                    <span className="uwi-feat-dash-col-dot uwi-feat-dash-col-dot--teal" />
                    Agenda optimisé
                  </div>
                  <ul className="uwi-feat-dash-list uwi-feat-dash-list--agenda">
                    <li>
                      <span className="uwi-feat-dash-time">09:00</span>
                      <div className="uwi-feat-dash-slot">
                        <strong>Claire Martin</strong>
                        <span>Consultation</span>
                      </div>
                    </li>
                    <li className="uwi-feat-dash-slot-recovered">
                      <span className="uwi-feat-dash-time">10:30</span>
                      <div className="uwi-feat-dash-slot">
                        <strong>Nouveau patient</strong>
                        <span>Créneau repris</span>
                      </div>
                      <span className="uwi-feat-dash-tag uwi-feat-dash-tag--new">Repris</span>
                    </li>
                    <li>
                      <span className="uwi-feat-dash-time">14:00</span>
                      <div className="uwi-feat-dash-slot">
                        <strong>Paul Bernard</strong>
                        <span>Consultation</span>
                      </div>
                    </li>
                    <li className="uwi-feat-dash-slot-active">
                      <span className="uwi-feat-dash-time">16:15</span>
                      <div className="uwi-feat-dash-slot">
                        <strong>Sophie Leroy</strong>
                        <span>Confirmé</span>
                      </div>
                    </li>
                  </ul>
                  <span className="uwi-feat-dash-col-link">Voir l&apos;agenda complet <ChevronRight size={12} strokeWidth={2.2} /></span>
                </div>
              </div>

              <div className="uwi-feat-dash-bar">
                <span className="uwi-feat-dash-bar-label">
                  <Zap size={14} strokeWidth={2.4} />
                  Actions rapides
                </span>
                <span className="uwi-feat-dash-bar-btn">
                  <Bell size={14} strokeWidth={2} />
                  Envoyer les rappels
                </span>
                <span className="uwi-feat-dash-bar-btn">
                  <CheckCircle size={14} strokeWidth={2} />
                  Voir les confirmations
                </span>
                <span className="uwi-feat-dash-bar-btn">
                  <PhoneLucide size={14} strokeWidth={2} />
                  Recontacter un patient
                </span>
                <span className="uwi-feat-dash-bar-btn">
                  <Calendar size={14} strokeWidth={2} />
                  Ouvrir l&apos;agenda
                </span>
              </div>
            </div>

            <div className="uwi-feat-tel-foot">
              <ShieldCheck size={16} strokeWidth={2.2} aria-hidden />
              <span>
                Moins d&apos;absences, un agenda plus stable, une activité mieux sécurisée.
              </span>
            </div>
          </article>
          </div>

        </div>
      </section>

      <section id="comment" className="uwi-hw reveal">
        <div className="uwi-hw-intro">
          <div className="uwi-hw-eyebrow-row">
            <div className="uwi-hw-eyebrow">
              <Zap size={14} strokeWidth={2.5} className="uwi-hw-eyebrow-zap" aria-hidden />
              Comment fonctionne UWi
            </div>
          </div>
          <h2 className="uwi-hw-intro-heading">Vos patients ont le choix.</h2>
          <p className="uwi-hw-intro-lead">
            Ils peuvent prendre rendez-vous par <span className="uwi-hw-intro-hl">téléphone</span>, ou depuis votre{" "}
            <span className="uwi-hw-intro-hl">page publique</span> référencée sur Google avec chat vocal intelligent intégré.
          </p>
          <p className="uwi-hw-intro-note">
            Dans les deux cas, UWi applique vos règles de cabinet, confirme les rendez-vous et centralise tout dans le même agenda.
          </p>

          <div className="uwi-hw-intro-rule" aria-hidden />

          <ul className="uwi-hw-intro-features">
            <li className="uwi-hw-intro-feat">
              <span className="uwi-hw-intro-feat-ico" aria-hidden>
                <PhoneLucide size={20} strokeWidth={2} />
              </span>
              <div className="uwi-hw-intro-feat-text">
                <span className="uwi-hw-intro-feat-title">2 points d&apos;entrée</span>
                <span className="uwi-hw-intro-feat-sub">Téléphone + page publique</span>
              </div>
            </li>
            <li className="uwi-hw-intro-feat">
              <span className="uwi-hw-intro-feat-ico" aria-hidden>
                <Calendar size={20} strokeWidth={2} />
              </span>
              <div className="uwi-hw-intro-feat-text">
                <span className="uwi-hw-intro-feat-title">1 agenda</span>
                <span className="uwi-hw-intro-feat-sub">Tout est centralisé</span>
              </div>
            </li>
            <li className="uwi-hw-intro-feat">
              <span className="uwi-hw-intro-feat-ico" aria-hidden>
                <Clock size={20} strokeWidth={2} />
              </span>
              <div className="uwi-hw-intro-feat-text">
                <span className="uwi-hw-intro-feat-title">24/7</span>
                <span className="uwi-hw-intro-feat-sub">Actif</span>
              </div>
            </li>
          </ul>

          <div className="uwi-hw-intro-rule" aria-hidden />

          <div className="uwi-hw-social-proof">
            <div className="uwi-hw-sp-avatars">
              <div className="uwi-hw-sp-avatar">🩺</div>
              <div className="uwi-hw-sp-avatar">👨‍⚕️</div>
              <div className="uwi-hw-sp-avatar">👩‍⚕️</div>
            </div>
            <div className="uwi-hw-sp-text">
              Déjà utilisé par <strong>+200 cabinets</strong> médicaux
            </div>
          </div>
        </div>

        <div className="uwi-hw-steps-wrap">
          <div className="uwi-hw-cards-stack">
            <article className="uwi-hw-card uwi-hw-card--entree">
              <div className="uwi-hw-card-kicker">
                <div className="uwi-hw-card-badge uwi-hw-card-badge--orange">
                  <Zap size={14} strokeWidth={2.5} className="uwi-hw-card-badge-zap" aria-hidden />
                  <span>01 Point d&apos;entrée</span>
                </div>
              </div>
              <h3 className="uwi-hw-card-h1 uwi-hw-card-h1--orange">Vos patients ont le choix</h3>
              <p className="uwi-hw-card-h2">Deux façons de réserver</p>
              <p className="uwi-hw-card-desc">
                Par téléphone, ou depuis votre page publique référencée sur Google avec chat vocal intelligent intégré.
              </p>
              <div className="uwi-hw-card-pair">
                <div className="uwi-hw-card-mini">
                  <div className="uwi-hw-card-mini-ico">
                    <PhoneLucide size={22} strokeWidth={2} className="uwi-hw-card-mini-ic" aria-hidden />
                  </div>
                  <strong className="uwi-hw-card-mini-label">Téléphone</strong>
                </div>
                <div className="uwi-hw-card-mini">
                  <div className="uwi-hw-card-mini-ico">
                    <AppWindow size={22} strokeWidth={2} className="uwi-hw-card-mini-ic" aria-hidden />
                  </div>
                  <strong className="uwi-hw-card-mini-label">Page publique</strong>
                  <div className="uwi-hw-card-mini-tags">
                    <span className="uwi-hw-chip">
                      <Search size={12} strokeWidth={2} aria-hidden />
                      trouvée via Google
                    </span>
                    <span className="uwi-hw-chip">
                      <AudioWaveform size={12} strokeWidth={2} aria-hidden />
                      chat vocal intégré
                    </span>
                  </div>
                </div>
              </div>
              <div className="uwi-hw-card-foot uwi-hw-card-foot--teal">
                <ShieldCheck size={22} strokeWidth={2} className="uwi-hw-card-foot-ico" aria-hidden />
                <span>Même règles, même agenda.</span>
              </div>
            </article>

            <article className="uwi-hw-card uwi-hw-card--tel">
              <div className="uwi-hw-card-kicker">
                <div className="uwi-hw-card-badge">
                  <Zap size={14} strokeWidth={2.5} className="uwi-hw-card-badge-zap uwi-hw-card-badge-zap--dark" aria-hidden />
                  <span>02 Téléphone</span>
                </div>
              </div>
              <h3 className="uwi-hw-card-h1 uwi-hw-card-h1--amber">Le patient appelle</h3>
              <p className="uwi-hw-card-sub uwi-hw-card-sub--teal">UWi répond et guide la réservation</p>
              <p className="uwi-hw-card-desc uwi-hw-card-desc--muted">
                Le patient appelle le cabinet. UWi répond, comprend la demande et propose un créneau selon les règles du cabinet.
              </p>
              <div className="uwi-hw-tel-demo">
                <div className="uwi-hw-tel-col uwi-hw-tel-col--status">
                  <div className="uwi-hw-tel-ring">
                    <PhoneLucide size={24} strokeWidth={2} className="uwi-hw-tel-ring-ic" aria-hidden />
                  </div>
                  <strong className="uwi-hw-tel-status-title">Appel téléphonique</strong>
                  <div className="uwi-hw-wave" aria-hidden>
                    {[4, 7, 5, 9, 6, 10, 5, 8, 4, 6].map((h, i) => (
                      <span key={i} className="uwi-hw-wave-bar" style={{ height: `${h * 3}px` }} />
                    ))}
                  </div>
                </div>
                <div className="uwi-hw-tel-col uwi-hw-tel-col--chat">
                  <div className="uwi-hw-tel-thread">
                    <div className="uwi-hw-tel-msg">
                      <User size={14} strokeWidth={2} className="uwi-hw-tel-msg-av" aria-hidden />
                      <div className="uwi-hw-bubble uwi-hw-bubble--patient">
                        <span className="uwi-hw-bubble-who">Patient :</span> « Je voudrais prendre rendez-vous. »
                      </div>
                    </div>
                    <div className="uwi-hw-tel-msg">
                      <Bot size={14} strokeWidth={2} className="uwi-hw-tel-msg-av uwi-hw-tel-msg-av--bot" aria-hidden />
                      <div className="uwi-hw-bubble uwi-hw-bubble--uwi">
                        <span className="uwi-hw-bubble-who">UWi :</span> « Bien sûr, je vous propose mardi à 10h. »
                      </div>
                    </div>
                    <div className="uwi-hw-tel-msg">
                      <User size={14} strokeWidth={2} className="uwi-hw-tel-msg-av" aria-hidden />
                      <div className="uwi-hw-bubble uwi-hw-bubble--patient">
                        <span className="uwi-hw-bubble-who">Patient :</span> « Parfait. »
                      </div>
                    </div>
                  </div>
                </div>
              </div>
              <div className="uwi-hw-benefit-row">
                <span className="uwi-hw-benefit">
                  <span className="uwi-hw-benefit-dot">
                    <Zap size={12} strokeWidth={2.5} className="uwi-hw-benefit-dot-ic" aria-hidden />
                  </span>
                  réponse immédiate
                </span>
                <span className="uwi-hw-benefit">
                  <span className="uwi-hw-benefit-dot">
                    <Check size={12} strokeWidth={2.5} className="uwi-hw-benefit-dot-ic" aria-hidden />
                  </span>
                  demande comprise
                </span>
                <span className="uwi-hw-benefit">
                  <span className="uwi-hw-benefit-dot">
                    <Calendar size={12} strokeWidth={2} className="uwi-hw-benefit-dot-ic" aria-hidden />
                  </span>
                  créneau proposé
                </span>
              </div>
              <div className="uwi-hw-card-banner">
                <ShieldCheck size={20} strokeWidth={2} className="uwi-hw-card-banner-ico" aria-hidden />
                <span>Par téléphone, le parcours reste simple et fluide.</span>
              </div>
            </article>

            <article className="uwi-hw-card uwi-hw-card--pub">
              <div className="uwi-hw-card-kicker">
                <div className="uwi-hw-card-badge">
                  <Zap size={14} strokeWidth={2.5} className="uwi-hw-card-badge-zap uwi-hw-card-badge-zap--dark" aria-hidden />
                  <span>03 Page publique</span>
                </div>
              </div>
              <h3 className="uwi-hw-card-h1 uwi-hw-card-h1--teal">Le patient trouve votre page</h3>
              <p className="uwi-hw-card-sub uwi-hw-card-sub--navy">Réservation guidée depuis la page publique</p>
              <p className="uwi-hw-card-desc uwi-hw-card-desc--muted">
                Le patient trouve votre page publique via Google, puis réserve directement grâce au chat vocal intelligent intégré.
              </p>
              <div className="uwi-hw-pub-flow">
                <div className="uwi-hw-pub-step">
                  <div className="uwi-hw-pub-mock uwi-hw-pub-mock--google">
                    <div className="uwi-hw-google-bar">
                      <span className="uwi-hw-google-g">G</span>
                      <span className="uwi-hw-google-q">page du cabinet</span>
                    </div>
                    <div className="uwi-hw-google-snippet">
                      <span className="uwi-hw-google-link">trouvée via Google</span>
                      <span className="uwi-hw-google-result-title">Cabinet du Dr Martin</span>
                      <span className="uwi-hw-google-result-url">www.uwiapp.com › cabinet › dr-martin</span>
                      <p className="uwi-hw-google-result-desc">
                        Page officielle du cabinet : horaires, infos pratiques et prise de rendez-vous avec assistant vocal.
                      </p>
                    </div>
                  </div>
                  <p className="uwi-hw-pub-caption">
                    <Globe size={14} strokeWidth={2} aria-hidden /> visible sur Google
                  </p>
                </div>
                <div className="uwi-hw-pub-arrow" aria-hidden>
                  <ChevronRight size={22} strokeWidth={2} />
                </div>
                <div className="uwi-hw-pub-step">
                  <div className="uwi-hw-pub-mock uwi-hw-pub-mock--site">
                    <div className="uwi-hw-site-top">
                      <div className="uwi-hw-site-av" aria-hidden>
                        UWi
                      </div>
                      <div className="uwi-hw-site-copy">
                        <span className="uwi-hw-site-name">Cabinet du Dr Martin</span>
                        <span className="uwi-hw-site-line">Médecine générale · Paris 15ᵉ</span>
                        <span className="uwi-hw-site-line uwi-hw-site-line--muted">Ouvert aujourd&apos;hui · 9h–19h</span>
                      </div>
                    </div>
                    <div className="uwi-hw-site-meta">
                      <Clock size={14} strokeWidth={2} aria-hidden />
                      <MapPin size={14} strokeWidth={2} aria-hidden />
                      <User size={14} strokeWidth={2} aria-hidden />
                    </div>
                  </div>
                  <p className="uwi-hw-pub-caption">
                    <Globe size={14} strokeWidth={2} aria-hidden /> page publique du cabinet
                  </p>
                </div>
                <div className="uwi-hw-pub-arrow" aria-hidden>
                  <ChevronRight size={22} strokeWidth={2} />
                </div>
                <div className="uwi-hw-pub-step">
                  <div className="uwi-hw-pub-mock uwi-hw-pub-mock--chat">
                    <Mic size={18} strokeWidth={2} className="uwi-hw-pub-mic" aria-hidden />
                    <p className="uwi-hw-pub-chat-q">Bonjour, comment pouvons-nous vous aider ?</p>
                    <div className="uwi-hw-pub-mini-wave" aria-hidden>
                      {[3, 6, 4, 8, 5, 7, 4].map((h, i) => (
                        <span key={i} style={{ height: `${h * 2}px` }} />
                      ))}
                    </div>
                    <p className="uwi-hw-pub-live">
                      <span className="uwi-hw-pub-live-dot" /> En écoute…
                    </p>
                  </div>
                  <p className="uwi-hw-pub-caption">
                    <AudioWaveform size={14} strokeWidth={2} aria-hidden /> chat vocal intégré
                  </p>
                </div>
              </div>
              <div className="uwi-hw-pub-chips">
                <span className="uwi-hw-chip uwi-hw-chip--dark">
                  <Search size={12} strokeWidth={2} aria-hidden />
                  visible sur Google
                </span>
                <span className="uwi-hw-chip uwi-hw-chip--dark">
                  <AudioWaveform size={12} strokeWidth={2} aria-hidden />
                  chat vocal intégré
                </span>
                <span className="uwi-hw-chip uwi-hw-chip--dark">
                  <Calendar size={12} strokeWidth={2} aria-hidden />
                  réservation guidée
                </span>
              </div>
              <div className="uwi-hw-card-banner uwi-hw-card-banner--split">
                <ShieldCheck size={20} strokeWidth={2} className="uwi-hw-card-banner-shield" aria-hidden />
                <p className="uwi-hw-card-banner-text">
                  La page publique et le chat vocal forment <strong className="uwi-hw-card-banner-hl">un seul parcours</strong>.
                </p>
                <span className="uwi-hw-pub-link-ico" aria-hidden>
                  <Link2 size={16} strokeWidth={2} />
                </span>
              </div>
            </article>

            <article className="uwi-hw-card uwi-hw-card--agenda">
              <div className="uwi-hw-card-kicker">
                <div className="uwi-hw-card-badge">
                  <Zap size={14} strokeWidth={2.5} className="uwi-hw-card-badge-zap uwi-hw-card-badge-zap--dark" aria-hidden />
                  <span>04 Même agenda</span>
                </div>
              </div>
              <h3 className="uwi-hw-card-h1 uwi-hw-card-h1--teal2">Tout revient au même endroit</h3>
              <p className="uwi-hw-card-sub uwi-hw-card-sub--navy">Deux points d&apos;entrée, un seul agenda</p>
              <p className="uwi-hw-card-desc uwi-hw-card-desc--muted">
                Qu&apos;il réserve par téléphone ou depuis la page publique, le rendez-vous est confirmé et centralisé dans le même agenda.
              </p>
              <div className="uwi-hw-merge">
                <div className="uwi-hw-merge-top">
                  <div className="uwi-hw-merge-node">
                    <PhoneLucide size={22} strokeWidth={2} className="uwi-hw-merge-node-ic" aria-hidden />
                    <span>Téléphone</span>
                  </div>
                  <div className="uwi-hw-merge-node">
                    <AppWindow size={22} strokeWidth={2} className="uwi-hw-merge-node-ic" aria-hidden />
                    <span>Page publique</span>
                  </div>
                </div>
                <div className="uwi-hw-merge-svg" aria-hidden>
                  <svg viewBox="0 0 280 72" className="uwi-hw-merge-lines" preserveAspectRatio="xMidYMid meet">
                    <path d="M70 0 V28 Q70 44 140 52" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
                    <path d="M210 0 V28 Q210 44 140 52" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
                    <path d="M140 52 V68" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
                    <path d="M132 60 L140 70 L148 60" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </div>
                <div className="uwi-hw-merge-bottom">
                  <div className="uwi-hw-merge-node uwi-hw-merge-node--wide">
                    <Calendar size={24} strokeWidth={2} className="uwi-hw-merge-node-ic" aria-hidden />
                    <span>Agenda unique</span>
                  </div>
                </div>
              </div>
              <div className="uwi-hw-card-foot uwi-hw-card-foot--agenda">
                <span className="uwi-hw-foot-shield">
                  <ShieldCheck size={20} strokeWidth={2} aria-hidden />
                </span>
                <span>
                  Le patient choisit, <em className="uwi-hw-foot-brand">UWi</em> centralise.
                </span>
              </div>
            </article>
          </div>

          <div className="uwi-hw-bottom-stack">
            <article className="uwi-hw-ex-card">
              <div className="uwi-hw-ex-badge">
                <PhoneLucide size={14} strokeWidth={2} aria-hidden />
                <span>Exemple concret</span>
              </div>
              <h3 className="uwi-hw-ex-title">
                <span className="uwi-hw-ex-time">À 19h</span>, un patient veut prendre rendez-vous.
              </h3>
              <div className="uwi-hw-ex-pills">
                <span className="uwi-hw-ex-pill">
                  <PhoneLucide size={14} strokeWidth={2} aria-hidden />
                  Téléphone
                </span>
                <span className="uwi-hw-ex-pill">
                  <Globe size={14} strokeWidth={2} aria-hidden />
                  Page publique
                </span>
              </div>
              <p className="uwi-hw-ex-lead">
                Il appelle le cabinet ou passe par votre page publique trouvée sur Google.
              </p>
              <p className="uwi-hw-ex-body">
                <span className="uwi-hw-ex-hl">
                  UWi répond, comprend la demande, propose un créneau selon vos règles et confirme le rendez-vous.
                </span>
              </p>
              <div className="uwi-hw-ex-success">
                <span className="uwi-hw-ex-success-ic" aria-hidden>
                  <Check size={16} strokeWidth={3} />
                </span>
                <p>
                  Le patient est pris en charge, l&apos;agenda est à jour, et vous n&apos;avez rien eu à gérer.
                </p>
              </div>
            </article>

            <article className="uwi-hw-install-card">
              <div className="uwi-hw-install-badge">
                <Zap size={14} strokeWidth={2.5} aria-hidden />
                <span>Installation rapide</span>
              </div>
              <h3 className="uwi-hw-install-title">
                Opérationnel en <span className="uwi-hw-install-hl">moins de 24h</span>
              </h3>
              <p className="uwi-hw-install-desc">
                Nous configurons UWi selon votre cabinet, vos horaires, vos consignes et votre agenda. Aucune installation
                complexe. Rien à déployer de votre côté.
              </p>
              <div className="uwi-hw-install-btns">
                <Link to="/contact" className="uwi-hw-btn-ghost uwi-hw-btn-ghost--wide">
                  <User size={16} strokeWidth={2} aria-hidden />
                  Parler à un expert
                </Link>
                <Link
                  to="/creer-assistante?new=1"
                  className="uwi-hw-btn-primary uwi-hw-btn-primary--wide"
                  onClick={() => trackLandingClick("how_it_works_create_assistant_click")}
                >
                  Créer mon assistant
                  <ArrowRight size={18} strokeWidth={2} aria-hidden />
                </Link>
              </div>
              <div className="uwi-hw-install-trust">
                <ShieldCheck size={16} strokeWidth={2} className="uwi-hw-install-trust-ic" aria-hidden />
                <span>
                  Aucune installation. <span className="uwi-hw-install-dot">•</span> Aucun engagement.{" "}
                  <span className="uwi-hw-install-dot">•</span> Résiliable à tout moment.
                </span>
              </div>
            </article>
          </div>

        </div>
      </section>

      {/* Spotlight — hors wrap pour pleine largeur */}
      <div className="uwi-fullwidth-section">
        <Suspense fallback={<DeferredSectionFallback minHeight={720} />}>
          <AgentsSpotlight onSelectAgent={(a) => navigate("/creer-assistante?new=1", { state: a })} />
        </Suspense>
      </div>

      <Suspense fallback={<div style={{ minHeight: 600 }} />}>
        <UwiEngagementPricing />
      </Suspense>

      <Suspense fallback={<div style={{ minHeight: 500 }} />}>
        <UwiCompare />
      </Suspense>

      <UwiSecurite />

      <Suspense fallback={<div style={{ minHeight: 400 }} />}>
        <UwiFAQ />
      </Suspense>

      <Suspense fallback={<div style={{ minHeight: 600 }} />}>
        <UwiTestimonials />
      </Suspense>

      {/* CTA final — closing section avec promesse + réassurance + double CTA */}
      <section className="uwi-cta-final reveal">
        <img src="/images/uwi-cta-receptionist.png" alt="" className="uwi-cta-final-bg" aria-hidden="true" />
        <div className="uwi-cta-final-overlay">
          <div className="uwi-cta-final-content">
            <div className="uwi-cta-final-eyebrow">
              <span className="uwi-cta-final-dot" />
              Activation en moins de 24h
            </div>
            <h2 className="uwi-cta-final-title">
              Votre cabinet ne ratera plus <em>jamais</em> un appel.
            </h2>
            <p className="uwi-cta-final-sub">
              Activez UWi aujourd'hui, soyez opérationnel demain. On s'occupe de l'installation,
              de la configuration et du paramétrage — vous restez concentré sur vos patients.
            </p>

            <div className="uwi-cta-final-buttons">
              <Link
                to="/creer-assistante?new=1"
                className="uwi-cta-final-btn-primary"
                onClick={() => trackLandingClick("final_cta_create_assistant_click")}
              >
                <ArrowRight size={18} />
                Créer mon assistant
              </Link>
              <a
                href="tel:+33652398414"
                className="uwi-cta-final-btn-secondary"
                onClick={() => trackLandingClick("final_cta_expert_call_click")}
              >
                <PhoneLucide size={16} />
                Parler à un expert
              </a>
            </div>

            <ul className="uwi-cta-final-reassure">
              <li><CheckCircle size={14} /> Essai gratuit 1 mois</li>
              <li><CheckCircle size={14} /> Sans CB requise</li>
              <li><CheckCircle size={14} /> Installation incluse</li>
              <li><CheckCircle size={14} /> Sans engagement</li>
            </ul>
          </div>
        </div>
      </section>

      {/* Marquee — hors wrap pour pleine largeur */}
      <div className="uwi-fullwidth-section">
        <Suspense fallback={<DeferredSectionFallback minHeight={520} />}>
          <AgentsMarquee onSelectAgent={() => navigate("/creer-assistante?new=1")} />
        </Suspense>
      </div>

      <footer className="landing-footer">
          <Link to="/creer-assistante?new=1">Créer mon assistant</Link>
          <Link to="/contact">Contact</Link>
          <a href="tel:0939240575">09 39 24 05 75</a>
          <Link to="/securite">Sécurité</Link>
          <Link to="/cgv">CGV</Link>
          <Link to="/cgu">CGU</Link>
          <Link to="/mentions-legales">Mentions légales</Link>
          <div className="landing-footer-socials" aria-label="Réseaux sociaux UWi">
            <a
              href={UWI_LINKEDIN_URL}
              target="_blank"
              rel="noreferrer"
              aria-label="LinkedIn UWi"
              title="LinkedIn UWi"
            >
              <Linkedin size={16} />
            </a>
            <a
              href={UWI_FACEBOOK_URL}
              target="_blank"
              rel="noreferrer"
              aria-label="Facebook UWi"
              title="Facebook UWi"
            >
              <Facebook size={16} />
            </a>
          </div>
          <span>© UWi Medical</span>
        </footer>

      {/* Sticky CTA mobile — barre flottante visible après scroll, masquée près du footer */}
      <div
        className="uwi-sticky-cta-mobile"
        data-visible={stickyVisible ? "true" : "false"}
        aria-hidden={!stickyVisible}
      >
        <div className="uwi-sticky-cta-info">
          <span className="uwi-sticky-cta-label">À partir de</span>
          <span className="uwi-sticky-cta-price">
            99€<span>/mois</span>
          </span>
        </div>
        <Link
          to="/creer-assistante?new=1"
          className="uwi-sticky-cta-btn"
          onClick={() => trackLandingClick("sticky_cta_mobile_click")}
          tabIndex={stickyVisible ? 0 : -1}
        >
          Créer mon assistant
          <ArrowRight size={16} strokeWidth={2.5} />
        </Link>
      </div>
    </div>
  );
}
