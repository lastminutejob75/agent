import {
  AlertCircle,
  Calendar,
  Info,
  PhoneCall,
  PhoneOff,
  X,
} from "lucide-react";

export const TYPE_UI = {
  "rendez-vous": { label: "Rendez-vous", icon: Calendar, className: "bg-[#E6F7F8] text-[#007F87]" },
  "a-rappeler": { label: "À rappeler", icon: PhoneCall, className: "bg-[#FFF3EA] text-[#C2410C]" },
  information: { label: "Information", icon: Info, className: "bg-[#EEF5FF] text-[#1D4ED8]" },
  "appel-manque": { label: "Appel manqué", icon: PhoneOff, className: "bg-[#FEF2F2] text-[#B91C1C]" },
  annulation: { label: "Annulation", icon: X, className: "bg-[#FFF3EA] text-[#C2410C]" },
  deplacement: { label: "Déplacement", icon: Calendar, className: "bg-[#E6F7F8] text-[#007F87]" },
  sensible: { label: "Sensible", icon: AlertCircle, className: "bg-[#FEF2F2] text-[#B91C1C]" },
};

export default function TypeBadge({ type }) {
  const conf = TYPE_UI[type] || TYPE_UI.information;
  const Icon = conf.icon;
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-extrabold ${conf.className}`}>
      <Icon size={14} />
      {conf.label}
    </span>
  );
}
