import { PhoneOff, User } from "lucide-react";

function toInitials(name) {
  return String(name || "")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word[0])
    .join("")
    .toUpperCase();
}

export default function PatientAvatar({ patient }) {
  if (patient?.known) {
    return (
      <div className="grid h-11 w-11 place-items-center rounded-full bg-[#E6F7F8] text-sm font-black text-[#009CA4]">
        {toInitials(patient?.name || "PT")}
      </div>
    );
  }
  if (patient?.masked) {
    return (
      <div className="grid h-11 w-11 place-items-center rounded-full bg-[#F1F5F9] text-[#334155]">
        <PhoneOff size={16} />
      </div>
    );
  }
  return (
    <div className="grid h-11 w-11 place-items-center rounded-full bg-[#F1F5F9] text-[#334155]">
      <User size={16} />
    </div>
  );
}
