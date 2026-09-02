import type { LucideIcon } from "lucide-react";

interface MetricCardProps {
  icon: LucideIcon;
  label: string;
  value: string;
  detail: string;
  tone: "mint" | "amber" | "blue" | "rose";
}

export function MetricCard({ icon: Icon, label, value, detail, tone }: MetricCardProps) {
  return (
    <article className={`metric-card tone-${tone}`}>
      <div className="metric-top"><span className="metric-icon"><Icon size={18} /></span><span>{label}</span></div>
      <strong>{value}</strong>
      <p>{detail}</p>
    </article>
  );
}
