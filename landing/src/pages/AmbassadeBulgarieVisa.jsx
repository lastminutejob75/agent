import { useMemo, useState } from "react";

const COPY = {
  fr: {
    dir: "ltr",
    embassy: "Ambassade de la République de Bulgarie",
    section: "Section des visas · Alger",
    eyebrow: "Demande de visa — pré-dépôt en ligne",
    title: "Votre demande, qualifiée en deux minutes",
    intro: "Vessela identifie la catégorie de visa, prépare les pièces requises et transmet un récépissé à la section consulaire.",
    hello: "Bonjour, je suis Vessela. De quel type de visa avez-vous besoin : A, C, D, ou souhaitez-vous être guidé ?",
    choose: "Sélectionnez un motif pour commencer.",
    receipt: "Récépissé de pré-dépôt",
    pending: "En attente",
    purpose: "Motif",
    category: "Catégorie",
    fee: "Frais",
    documents: "Pièces à fournir",
    phone: "Accueil téléphonique 24 h/24",
    transmitted: "PRÉ-DOSSIER",
    navPublic: "Accueil demandeur", navDashboard: "Dashboard consulaire",
    dashboardTitle: "Demandes et appels", applications: "Demandes / 30 jours",
    automated: "Qualifiées sans agent", average: "Délai moyen", incomplete: "Dossiers incomplets",
    reference: "Référence", residence: "Résidence", duration: "Durée", channel: "Canal",
    language: "Langue", status: "Statut", missing: "Pièces manquantes",
    convoke: "Convoquer", requestDoc: "Réclamer une pièce", transfer: "Transférer",
    motifs: { tourisme: "Tourisme", famille: "Visite familiale", etudes: "Études", travail: "Travail", transit: "Transit" },
  },
  en: {
    dir: "ltr",
    embassy: "Embassy of the Republic of Bulgaria",
    section: "Visa section · Algiers",
    eyebrow: "Visa application — online pre-filing",
    title: "Your application, sorted in two minutes",
    intro: "Vessela identifies the visa category, prepares the required documents and sends a receipt to the consular section.",
    hello: "Hello, I’m Vessela. Which visa type do you need: A, C, D, or would you like guidance?",
    choose: "Select a purpose to begin.",
    receipt: "Pre-filing receipt",
    pending: "Pending",
    purpose: "Purpose",
    category: "Category",
    fee: "Fee",
    documents: "Required documents",
    phone: "Telephone assistance 24/7",
    transmitted: "PRE-FILE",
    navPublic: "Applicant desk", navDashboard: "Consular dashboard",
    dashboardTitle: "Applications and calls", applications: "Applications / 30 days",
    automated: "Qualified without an officer", average: "Average time", incomplete: "Incomplete files",
    reference: "Reference", residence: "Residence", duration: "Duration", channel: "Channel",
    language: "Language", status: "Status", missing: "Missing documents",
    convoke: "Book appointment", requestDoc: "Request document", transfer: "Assign to officer",
    motifs: { tourisme: "Tourism", famille: "Family visit", etudes: "Studies", travail: "Work", transit: "Transit" },
  },
  bg: {
    dir: "ltr",
    embassy: "Посолство на Република България",
    section: "Визов отдел · Алжир",
    eyebrow: "Заявление за виза — онлайн предварително подаване",
    title: "Вашето заявление, класирано за две минути",
    intro: "Весела определя визовата категория, подготвя необходимите документи и изпраща разписка до консулския отдел.",
    hello: "Здравейте, аз съм Весела. Какъв вид виза ви е необходима: A, C, D, или желаете насоки?",
    choose: "Изберете цел, за да започнете.",
    receipt: "Разписка за предварително подаване",
    pending: "В очакване",
    purpose: "Цел",
    category: "Категория",
    fee: "Такса",
    documents: "Необходими документи",
    phone: "Телефонно обслужване 24/7",
    transmitted: "ПРЕПИСКА",
    navPublic: "Обслужване на заявители", navDashboard: "Консулско табло",
    dashboardTitle: "Заявления и обаждания", applications: "Заявления / 30 дни",
    automated: "Класирани без служител", average: "Средно време", incomplete: "Непълни преписки",
    reference: "Номер", residence: "Местожителство", duration: "Продължителност", channel: "Канал",
    language: "Език", status: "Статус", missing: "Липсващи документи",
    convoke: "Насрочи час", requestDoc: "Изискай документ", transfer: "Възложи на служител",
    motifs: { tourisme: "Туризъм", famille: "Семейно посещение", etudes: "Обучение", travail: "Работа", transit: "Транзит" },
  },
  ar: {
    dir: "rtl",
    embassy: "سفارة جمهورية بلغاريا",
    section: "قسم التأشيرات · الجزائر",
    eyebrow: "طلب تأشيرة — الإيداع المسبق عبر الإنترنت",
    title: "طلبك مصنّف في دقيقتين",
    intro: "تحدد فيسيلا فئة التأشيرة وتعدّ الوثائق المطلوبة وترسل وصل الإيداع إلى القسم القنصلي.",
    hello: "مرحباً، أنا فيسيلا. ما نوع التأشيرة التي تحتاجها: A أو C أو D، أم تريد المساعدة في الاختيار؟",
    choose: "اختر غرض السفر للبدء.",
    receipt: "وصل الإيداع المسبق",
    pending: "قيد الانتظار",
    purpose: "الغرض",
    category: "الفئة",
    fee: "الرسوم",
    documents: "الوثائق المطلوبة",
    phone: "استقبال هاتفي على مدار الساعة",
    transmitted: "ملف أولي",
    navPublic: "استقبال مقدّم الطلب", navDashboard: "لوحة القسم القنصلي",
    dashboardTitle: "الطلبات والمكالمات", applications: "الطلبات / 30 يوماً",
    automated: "مصنّفة دون موظف", average: "متوسط المدة", incomplete: "ملفات ناقصة",
    reference: "المرجع", residence: "مكان الإقامة", duration: "المدة", channel: "القناة",
    language: "اللغة", status: "الحالة", missing: "الوثائق الناقصة",
    convoke: "تحديد موعد", requestDoc: "طلب وثيقة", transfer: "إحالة إلى موظف",
    motifs: { tourisme: "سياحة", famille: "زيارة عائلية", etudes: "دراسة", travail: "عمل", transit: "عبور" },
  },
};

const CATEGORY = { tourisme: "C", famille: "C", etudes: "D", travail: "D", transit: "A" };
const PURPOSE_QUESTION = {
  fr: "Quel est le motif de votre séjour en Bulgarie ?",
  en: "What is the purpose of your stay in Bulgaria?",
  bg: "Каква е целта на престоя ви в България?",
  ar: "ما غرض إقامتك في بلغاريا؟",
};
const DOCS = {
  A: ["Passeport valide", "Billet confirmé", "Visa de destination finale"],
  C: ["Formulaire signé", "Passeport valide", "Deux photographies", "Justificatif du séjour"],
  D: ["Formulaire long séjour", "Passeport valide", "Justificatif du motif", "Casier judiciaire"],
};

const DEMO_APPLICATIONS = [
  { ref: "BG/DZ/26/0521", name: "Yasmine Ould Ali", purpose: "Visite familiale UE", category: "C", channel: "Chat", lang: "FR", status: "Complète", missing: 0, ago: "4 min" },
  { ref: "BG/DZ/26/0520", name: "Sofiane Merabet", purpose: "Regroupement familial", category: "D", channel: "Téléphone", lang: "FR", status: "Incomplète", missing: 2, ago: "19 min" },
  { ref: "BG/DZ/26/0519", name: "Hakim Saïdi", purpose: "Équipage", category: "C", channel: "Téléphone", lang: "AR", status: "Escaladée", missing: 0, ago: "35 min" },
  { ref: "BG/DZ/26/0518", name: "Karim Belhadj", purpose: "Visite familiale", category: "C", channel: "Téléphone", lang: "FR", status: "Incomplète", missing: 1, ago: "1 h" },
  { ref: "BG/DZ/26/0517", name: "Amina Cherifi", purpose: "Études", category: "D", channel: "Chat", lang: "FR", status: "Nouvelle", missing: 1, ago: "2 h" },
];

const COUNTER_DAYS = [
  { date: "Lun. 27", slots: [{ time: "09:00", used: 6, capacity: 8 }, { time: "10:30", used: 8, capacity: 8 }, { time: "14:00", used: 3, capacity: 6 }] },
  { date: "Mar. 28", slots: [{ time: "09:00", used: 4, capacity: 8 }, { time: "10:30", used: 5, capacity: 8 }, { time: "14:00", used: 6, capacity: 6 }] },
  { date: "Mer. 29", slots: [{ time: "09:00", used: 7, capacity: 8 }, { time: "10:30", used: 2, capacity: 8 }, { time: "14:00", used: 4, capacity: 6 }] },
  { date: "Jeu. 30", slots: [{ time: "09:00", used: 3, capacity: 8 }, { time: "10:30", used: 7, capacity: 8 }, { time: "14:00", used: 2, capacity: 6 }] },
  { date: "Ven. 31", slots: [{ time: "09:00", used: 5, capacity: 8 }, { time: "10:30", used: 4, capacity: 8 }] },
];

const CSS = `
.consular{--ink:#0c2523;--paper:#eaeee8;--white:#fff;--green:#00614a;--rose:#a8325b;--gold:#b98e2b;--line:#cbd3cb;min-height:100vh;background:var(--paper);color:var(--ink);font-family:system-ui,-apple-system,"Segoe UI",sans-serif}
.consular *{box-sizing:border-box}.consular button{font:inherit;cursor:pointer}.consular-header{display:flex;align-items:center;gap:14px;padding:14px 24px;background:var(--ink);color:#fff}
.consular-seal{width:38px;height:38px;border:1px solid var(--gold);border-radius:50%;display:grid;place-items:center;color:var(--gold);font-family:Georgia,serif}.consular-brand{font-family:Georgia,serif}.consular-brand small{display:block;color:#9db3ad;font:11px system-ui;letter-spacing:.12em;text-transform:uppercase;margin-top:3px}.consular-langs{display:flex;gap:4px;margin-inline-start:auto}
.consular-langs button{border:1px solid #31514b;background:transparent;color:#9db3ad;padding:6px 8px}.consular-langs button[data-on="1"]{border-color:var(--gold);color:var(--gold)}
.consular-view{display:flex;border:1px solid #31514b}.consular-view button{border:0;background:transparent;color:#9db3ad;padding:7px 11px}.consular-view button[data-on="1"]{background:#fff;color:var(--ink)}
.consular-demo{padding:6px 24px;background:var(--gold);font:11px ui-monospace;letter-spacing:.05em}.consular-main{max-width:1120px;margin:auto;padding:44px 22px 70px}
.consular-eyebrow{color:var(--green);font:11px ui-monospace;letter-spacing:.16em;text-transform:uppercase}.consular h1{max-width:760px;margin:15px 0 10px;font:400 clamp(34px,5vw,58px)/1.04 Georgia,serif}.consular-lede{max-width:650px;color:#5e6e69;line-height:1.65}
.consular-grid{display:grid;grid-template-columns:minmax(0,1.5fr) minmax(300px,1fr);gap:20px;margin-top:34px}.consular-card{background:var(--white);border:1px solid var(--line);border-radius:4px}
.consular-agent{display:flex;align-items:center;gap:11px;padding:14px 16px;border-bottom:1px solid var(--line)}.consular-avatar{width:36px;height:36px;border-radius:50%;display:grid;place-items:center;background:var(--green);color:#fff;font-family:Georgia,serif}
.consular-live{margin-inline-start:auto;color:var(--green);font:11px ui-monospace}.consular-thread{min-height:260px;padding:20px;background:linear-gradient(#f7f9f5,#fff)}
.consular-restart{border:1px solid var(--line);background:#fff;padding:6px 9px;font-size:12px}
.consular-msg{max-width:82%;padding:12px 14px;border:1px solid var(--line);background:var(--paper);line-height:1.5}.consular-msg.user{margin-inline-start:auto;margin-top:14px;background:var(--ink);color:#fff}.consular-chips{display:flex;flex-wrap:wrap;gap:8px;padding:16px;border-top:1px solid var(--line)}
.consular-chips button{border:1px solid var(--green);background:#fff;color:var(--green);padding:8px 11px}.consular-chips button:hover{background:var(--green);color:#fff}
.consular-composer{display:flex;gap:8px;padding:14px 16px;border-top:1px solid var(--line)}.consular-composer input{min-width:0;flex:1;border:1px solid var(--line);background:#f7f9f5;padding:11px 12px;font:inherit}.consular-composer button{border:0;background:var(--ink);color:#fff;padding:0 18px}.consular-composer button:disabled,.consular-composer input:disabled{opacity:.55;cursor:not-allowed}
.consular-receipt{position:relative;padding:18px;background:#f7f9f5;overflow:hidden}.consular-receipt h2{font:400 20px Georgia,serif;margin:0 0 18px}.consular-row{display:flex;gap:12px;padding:11px 0;border-bottom:1px dashed var(--line)}.consular-row span:first-child{width:36%;color:#5e6e69;font:10px ui-monospace;text-transform:uppercase;letter-spacing:.1em}
.consular-tag{color:var(--green);font:12px ui-monospace;border:1px solid;padding:3px 7px}.consular-docs{padding-inline-start:20px;line-height:1.8;font-size:13px}.consular-stamp{position:absolute;inset-inline-end:18px;bottom:18px;width:92px;height:92px;border:2px solid var(--rose);border-radius:50%;display:grid;place-items:center;color:var(--rose);font:10px ui-monospace;text-align:center;transform:rotate(-12deg)}
.consular-phone{margin-top:20px;padding:18px 20px;background:var(--ink);color:#fff}.consular-phone b{display:block;font:18px Georgia,serif}.consular-phone span{display:block;margin-top:9px;color:var(--gold);font:18px ui-monospace;direction:ltr;text-align:start}
.consular-kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:26px 0 18px}.consular-kpi{padding:16px;background:#fff;border:1px solid var(--line)}.consular-kpi b{display:block;font:26px ui-monospace}.consular-kpi span{color:var(--slate);font-size:12px}.consular-dash{display:grid;grid-template-columns:minmax(0,1.2fr) minmax(320px,.8fr);gap:16px}.consular-list{background:#fff;border:1px solid var(--line)}.consular-case{display:grid;grid-template-columns:1fr auto;gap:10px;width:100%;padding:14px;border:0;border-bottom:1px solid var(--line);background:#fff;text-align:start}.consular-case:hover,.consular-case[data-on="1"]{background:#f7f9f5}.consular-case[data-on="1"]{box-shadow:inset 3px 0 var(--rose)}.consular-case small{display:block;color:var(--slate);margin-top:4px}.consular-status{font:10px ui-monospace;border:1px solid;padding:3px 6px}.consular-detail{background:#fff;border:1px solid var(--line);padding:18px;align-self:start;position:sticky;top:16px}.consular-detail h2{font:22px Georgia;margin:0 0 16px}.consular-actions{display:flex;flex-wrap:wrap;gap:7px;margin-top:18px}.consular-actions button{border:1px solid var(--line);background:#f7f9f5;padding:8px 10px}.consular-actions button:first-child{background:var(--green);color:#fff;border-color:var(--green)}
.consular-dashboard-tabs{display:flex;gap:8px;margin-top:20px}.consular-dashboard-tabs button{border:1px solid var(--line);background:#fff;padding:9px 13px}.consular-dashboard-tabs button[data-on="1"]{background:var(--ink);color:#fff}.consular-agenda{display:grid;grid-template-columns:repeat(5,minmax(150px,1fr));gap:10px;margin-top:18px;overflow-x:auto}.consular-day{background:#fff;border:1px solid var(--line);min-width:150px}.consular-day h3{margin:0;padding:12px;border-bottom:1px solid var(--line);font:15px Georgia}.consular-slot{margin:9px;padding:10px;border-inline-start:3px solid var(--green);background:#f7f9f5}.consular-slot[data-full="1"]{border-inline-start-color:var(--rose);opacity:.65}.consular-slot b{display:block;font:14px ui-monospace}.consular-slot small{color:var(--slate)}
@media(max-width:820px){.consular-grid{grid-template-columns:1fr}.consular-header{flex-wrap:wrap}.consular-langs{width:100%;margin-inline-start:52px}.consular-main{padding-top:30px}}
@media(max-width:820px){.consular-kpis{grid-template-columns:repeat(2,1fr)}.consular-dash{grid-template-columns:1fr}.consular-detail{position:static}}
`;

export default function AmbassadeBulgarieVisa() {
  const [lang, setLang] = useState("fr");
  const t = COPY[lang];
  const [step, setStep] = useState("visaType");
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState([{ from: "bot", text: COPY.fr.hello }]);
  const [application, setApplication] = useState({});
  const category = application.category || null;
  const documents = useMemo(() => (category ? DOCS[category] : []), [category]);

  const options = useMemo(() => {
    if (step === "visaType") {
      const guidance = { fr: "Je ne sais pas", en: "I don’t know", bg: "Не знам", ar: "لا أعرف" };
      return [
        { value: "A", label: "Visa A — transit" },
        { value: "C", label: "Visa C — court séjour" },
        { value: "D", label: "Visa D — long séjour" },
        { value: "unknown", label: guidance[lang] },
      ];
    }
    if (step === "purpose") {
      return Object.entries(t.motifs).map(([value, label]) => ({ value, label }));
    }
    if (step === "duration") {
      return [
        { value: "15", label: "15 jours ou moins" },
        { value: "30", label: "16 à 30 jours" },
        { value: "90", label: "31 à 90 jours" },
        { value: "120", label: "Plus de 90 jours" },
      ];
    }
    if (step === "passport") {
      return [{ value: "yes", label: "Oui" }, { value: "no", label: "Non" }];
    }
    if (step === "appointment") {
      return [{ value: "yes", label: "Oui, proposer un rendez-vous" }, { value: "no", label: "Non, terminer le pré-dossier" }];
    }
    if (step === "slotDate") {
      return COUNTER_DAYS.filter((day) => day.slots.some((slot) => slot.used < slot.capacity))
        .map((day) => ({ value: day.date, label: day.date }));
    }
    if (step === "slotTime") {
      const day = COUNTER_DAYS.find((item) => item.date === application.slotDate);
      return (day?.slots || []).filter((slot) => slot.used < slot.capacity)
        .map((slot) => ({ value: slot.time, label: `${slot.time} · ${slot.capacity - slot.used} places` }));
    }
    return [];
  }, [application.slotDate, lang, step, t]);

  function addExchange(answer, reply) {
    setMessages((current) => [
      ...current,
      { from: "user", text: answer },
      { from: "bot", text: reply },
    ]);
  }

  function answer(value, label = value) {
    if (!String(label).trim() || step === "done") return;
    if (step === "visaType") {
      setApplication(value === "unknown" ? {} : { requestedCategory: value });
      addExchange(
        label,
        value === "unknown"
          ? PURPOSE_QUESTION[lang]
          : `${value} — ${PURPOSE_QUESTION[lang]}`,
      );
      setStep("purpose");
    } else if (step === "purpose") {
      const selectedCategory = CATEGORY[value] || "C";
      setApplication((current) => ({ ...current, purpose: value, purposeLabel: label, category: selectedCategory }));
      addExchange(
        label,
        `Votre demande relève de la catégorie ${selectedCategory}. Dans quelle wilaya résidez-vous ?`,
      );
      setStep("residence");
    } else if (step === "residence") {
      setApplication((current) => ({ ...current, residence: label }));
      addExchange(label, "Combien de jours comptez-vous rester en Bulgarie ?");
      setStep("duration");
    } else if (step === "duration") {
      const days = Number.parseInt(value, 10) || Number.parseInt(label, 10) || 15;
      const reclassified = application.category === "C" && days > 90;
      setApplication((current) => ({
        ...current,
        duration: label,
        category: reclassified ? "D" : current.category,
      }));
      addExchange(
        label,
        reclassified
          ? "Au-delà de 90 jours, votre demande est requalifiée en visa national D. Votre passeport est-il valide au moins trois mois après le retour ?"
          : "Votre passeport est-il valide au moins trois mois après le retour ?",
      );
      setStep("passport");
    } else if (step === "passport") {
      const passportOk = value !== "no" && !/^non$/i.test(label.trim());
      setApplication((current) => ({ ...current, passportOk }));
      addExchange(
        label,
        passportOk
          ? "Merci. Indiquez maintenant votre nom, prénom et numéro de téléphone."
          : "Votre dossier restera incomplet jusqu’au renouvellement du passeport. Indiquez votre nom, prénom et numéro de téléphone.",
      );
      setStep("identity");
    } else if (step === "identity") {
      setApplication((current) => ({
        ...current,
        identity: label,
        reference: "BG/DZ/26/DEMO",
      }));
      addExchange(
        label,
        "Votre pré-dossier est prêt. Souhaitez-vous choisir maintenant un créneau de dépôt au guichet ?",
      );
      setStep("appointment");
    } else if (step === "appointment") {
      if (value === "no") {
        addExchange(label, "Votre pré-dossier est terminé. La décision finale appartient au poste consulaire.");
        setStep("done");
      } else {
        addExchange(label, "Voici les prochaines dates disponibles. Laquelle vous convient ?");
        setStep("slotDate");
      }
    } else if (step === "slotDate") {
      setApplication((current) => ({ ...current, slotDate: value }));
      addExchange(label, "Choisissez une heure de passage au guichet.");
      setStep("slotTime");
    } else if (step === "slotTime") {
      setApplication((current) => ({ ...current, slotTime: value }));
      addExchange(
        label,
        `Votre rendez-vous est réservé le ${application.slotDate} à ${value}. Une confirmation vous sera envoyée. La décision sur le visa appartient au poste consulaire.`,
      );
      setStep("done");
    }
    setInput("");
  }

  function submit(event) {
    event.preventDefault();
    const value = input.trim();
    if (!value) return;
    if (step === "purpose") {
      const normalized = value.toLowerCase();
      const detected = Object.keys(CATEGORY).find((key) => normalized.includes(key))
        || (normalized.includes("famill") ? "famille" : null)
        || (normalized.includes("étud") || normalized.includes("etud") ? "etudes" : null)
        || (normalized.includes("trava") || normalized.includes("emploi") ? "travail" : null)
        || (normalized.includes("tour") || normalized.includes("vacance") ? "tourisme" : null);
      if (detected) {
        answer(detected, value);
        return;
      }
    }
    answer(value, value);
  }

  function changeLanguage(code) {
    setLang(code);
    restart(code);
  }

  function restart(activeLang = lang) {
    setStep("visaType");
    setApplication({});
    setInput("");
    setMessages([{ from: "bot", text: COPY[activeLang].hello }]);
  }

  return (
    <div className="consular" dir={t.dir}>
      <style>{CSS}</style>
      <header className="consular-header">
        <div className="consular-seal" aria-hidden="true">BG</div>
        <div className="consular-brand">{t.embassy}<small>{t.section}</small></div>
        <nav className="consular-langs" aria-label="Langues">
          {Object.keys(COPY).map((code) => (
            <button key={code} data-on={lang === code ? 1 : 0} onClick={() => changeLanguage(code)}>{code.toUpperCase()}</button>
          ))}
        </nav>
      </header>
      <div className="consular-demo">DÉMONSTRATION · DONNÉES FICTIVES · AUCUNE VALEUR OFFICIELLE</div>
      <main className="consular-main">
        <div className="consular-eyebrow">{t.eyebrow}</div>
        <h1>{t.title}</h1>
        <p className="consular-lede">{t.intro}</p>
        <div className="consular-grid">
          <section className="consular-card">
            <div className="consular-agent">
              <div className="consular-avatar">V</div>
              <div><b>Vessela</b><small style={{ display: "block", color: "#5e6e69" }}>Assistante consulaire</small></div>
              <span className="consular-live">● EN LIGNE</span>
              <button type="button" className="consular-restart" onClick={() => restart()}>↻ Recommencer</button>
            </div>
            <div className="consular-thread" aria-live="polite">
              {messages.map((message, index) => (
                <div
                  className={`consular-msg${message.from === "user" ? " user" : ""}`}
                  style={index > 0 && message.from === "bot" ? { marginTop: 14 } : undefined}
                  key={`${message.from}-${index}`}
                >
                  {message.text}
                </div>
              ))}
            </div>
            {options.length > 0 && (
              <div className="consular-chips">
                {options.map(({ value, label }) => (
                  <button key={value} onClick={() => answer(value, label)}>{label}</button>
                ))}
              </div>
            )}
            <form className="consular-composer" onSubmit={submit}>
              <input
                value={input}
                onChange={(event) => setInput(event.target.value)}
                placeholder={step === "done" ? "Pré-dossier terminé" : "Écrivez votre réponse…"}
                disabled={step === "done"}
                aria-label="Votre réponse"
              />
              <button type="submit" disabled={step === "done" || !input.trim()}>Envoyer</button>
            </form>
          </section>
          <aside>
            <section className="consular-card consular-receipt">
              <h2>{t.receipt}</h2>
              <div className="consular-row"><span>Référence</span><b>{application.reference || t.pending}</b></div>
              <div className="consular-row"><span>{t.purpose}</span><b>{application.purpose ? (t.motifs[application.purpose] || application.purposeLabel) : t.pending}</b></div>
              <div className="consular-row"><span>{t.category}</span>{category ? <b className="consular-tag">{category}</b> : t.pending}</div>
              <div className="consular-row"><span>Résidence</span><b>{application.residence || t.pending}</b></div>
              <div className="consular-row"><span>Durée</span><b>{application.duration || t.pending}</b></div>
              <div className="consular-row"><span>Rendez-vous</span><b>{application.slotTime ? `${application.slotDate} · ${application.slotTime}` : t.pending}</b></div>
              <div className="consular-row"><span>{t.fee}</span><b>{category === "C" ? "90 €" : category ? "Configuration du poste" : t.pending}</b></div>
              {documents.length > 0 && <><h3 style={{ font: "12px ui-monospace", marginTop: 20 }}>{t.documents}</h3><ul className="consular-docs">{documents.map((doc) => <li key={doc}>{doc}</li>)}</ul></>}
              {step === "done" && <div className="consular-stamp">{t.transmitted}<br />SECTION VISAS</div>}
            </section>
            <section className="consular-phone"><b>{t.phone}</b><span>+213 21 92 40 51</span></section>
          </aside>
        </div>
      </main>
    </div>
  );
}

export function ConsularDashboardPage() {
  const [lang, setLang] = useState("fr");
  const [section, setSection] = useState("applications");
  const t = COPY[lang];

  return (
    <div className="consular" dir={t.dir}>
      <style>{CSS}</style>
      <header className="consular-header">
        <div className="consular-seal" aria-hidden="true">BG</div>
        <div className="consular-brand">{t.embassy}<small>{t.section}</small></div>
        <nav className="consular-langs" aria-label="Langues">
          {Object.keys(COPY).map((code) => (
            <button key={code} data-on={lang === code ? 1 : 0} onClick={() => setLang(code)}>{code.toUpperCase()}</button>
          ))}
        </nav>
      </header>
      <div className="consular-main" style={{ paddingBottom: 0 }}>
        <div className="consular-dashboard-tabs">
          <button data-on={section === "applications" ? 1 : 0} onClick={() => setSection("applications")}>Demandes et appels</button>
          <button data-on={section === "agenda" ? 1 : 0} onClick={() => setSection("agenda")}>Agenda du guichet</button>
        </div>
      </div>
      {section === "applications" ? <ConsularDashboard t={t} /> : <CounterAgenda />}
    </div>
  );
}

function CounterAgenda() {
  return (
    <main className="consular-main">
      <div className="consular-eyebrow">Capacité interne du guichet</div>
      <h1 style={{ fontSize: "clamp(30px,4vw,44px)" }}>Agenda des rendez-vous</h1>
      <p className="consular-lede">Les créneaux proposés par Vessela utilisent directement les places encore disponibles.</p>
      <div className="consular-agenda">
        {COUNTER_DAYS.map((day) => (
          <section className="consular-day" key={day.date}>
            <h3>{day.date}</h3>
            {day.slots.map((slot) => (
              <div className="consular-slot" data-full={slot.used >= slot.capacity ? 1 : 0} key={slot.time}>
                <b>{slot.time}</b>
                <small>{slot.used}/{slot.capacity} réservés</small>
              </div>
            ))}
          </section>
        ))}
      </div>
    </main>
  );
}

function ConsularDashboard({ t }) {
  const [selectedRef, setSelectedRef] = useState(DEMO_APPLICATIONS[0].ref);
  const selected = DEMO_APPLICATIONS.find((item) => item.ref === selectedRef);

  return (
    <main className="consular-main">
      <div className="consular-eyebrow">Section des visas — poste d’Alger</div>
      <h1 style={{ fontSize: "clamp(30px,4vw,44px)" }}>{t.dashboardTitle}</h1>
      <div className="consular-kpis">
        <div className="consular-kpi"><b>412</b><span>{t.applications}</span></div>
        <div className="consular-kpi"><b>78 %</b><span>{t.automated}</span></div>
        <div className="consular-kpi"><b>1:50</b><span>{t.average}</span></div>
        <div className="consular-kpi"><b>63</b><span>{t.incomplete}</span></div>
      </div>
      <div className="consular-dash">
        <section className="consular-list">
          {DEMO_APPLICATIONS.map((item) => (
            <button
              className="consular-case"
              data-on={selectedRef === item.ref ? 1 : 0}
              key={item.ref}
              onClick={() => setSelectedRef(item.ref)}
            >
              <span>
                <b>{item.name}</b>
                <small>{item.ref} · {item.purpose} · {item.channel} · {item.ago}</small>
              </span>
              <span>
                <b className="consular-tag">{item.category}</b>
                <small className="consular-status">{item.status}</small>
              </span>
            </button>
          ))}
        </section>
        <aside className="consular-detail">
          <h2>{selected.name}</h2>
          <div className="consular-row"><span>{t.reference}</span><b>{selected.ref}</b></div>
          <div className="consular-row"><span>Motif</span><b>{selected.purpose}</b></div>
          <div className="consular-row"><span>Catégorie</span><b className="consular-tag">{selected.category}</b></div>
          <div className="consular-row"><span>{t.channel}</span><b>{selected.channel}</b></div>
          <div className="consular-row"><span>{t.language}</span><b>{selected.lang}</b></div>
          <div className="consular-row"><span>{t.status}</span><b>{selected.status}</b></div>
          <div className="consular-row"><span>{t.missing}</span><b>{selected.missing}</b></div>
          <div className="consular-actions">
            <button>{t.convoke}</button>
            <button disabled={selected.missing === 0}>{t.requestDoc}</button>
            <button>{t.transfer}</button>
          </div>
        </aside>
      </div>
    </main>
  );
}
