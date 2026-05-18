export default function KpiCard({ value, label, subLabel }) {
  return (
    <div className="rounded-[22px] border border-[#E2E8F0] bg-white p-5 shadow-sm">
      <div className="text-4xl font-black">{value}</div>
      <div className="mt-1 text-sm font-black">{label}</div>
      <div className="text-sm text-[#64748B]">{subLabel}</div>
    </div>
  );
}
