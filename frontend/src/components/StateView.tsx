import { AlertTriangle, Inbox, LoaderCircle, RefreshCw } from "lucide-react";

export function LoadingState({ label = "Loading traceability data" }: { label?: string }) {
  return <div className="state-view" role="status"><LoaderCircle className="spin" /><strong>{label}</strong><p>Resolving deterministic artifacts and relationships…</p></div>;
}

export function EmptyState({ title, detail }: { title: string; detail: string }) {
  return <div className="state-view"><Inbox /><strong>{title}</strong><p>{detail}</p></div>;
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return <div className="state-view state-error" role="alert"><AlertTriangle /><strong>Unable to load this view</strong><p>{message}</p>{onRetry && <button className="button secondary" onClick={onRetry}><RefreshCw size={15} /> Retry</button>}</div>;
}
