import { Phone } from "lucide-react";

export default function EmptyDetailPanel() {
  return (
    <div className="flex h-full min-h-[280px] flex-col items-center justify-center rounded-[24px] border border-[#E2E8F0] bg-white p-8 text-center">
      <div className="grid h-14 w-14 place-items-center rounded-full bg-[#E6F7F8] text-[#009CA4]">
        <Phone size={24} />
      </div>
      <h3 className="mt-4 text-sm font-black text-[#0A1628]">Aucun appel sélectionné</h3>
      <p className="mt-2 max-w-[280px] text-sm leading-6 text-[#64748B]">
        Sélectionnez un appel pour afficher le résumé Clara, l&apos;enregistrement et les actions possibles.
      </p>
    </div>
  );
}
