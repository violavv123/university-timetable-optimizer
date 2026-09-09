import type { ButtonHTMLAttributes, ReactNode } from "react";
import { Icon, type IconName } from "./Icon";
import { humanize } from "../lib/format";

export function Button({
  children,
  variant = "primary",
  icon,
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  icon?: IconName;
}) {
  return (
    <button className={`button button--${variant} ${className}`} {...props}>
      {icon && <Icon name={icon} />}
      <span>{children}</span>
    </button>
  );
}

export function Spinner({ small = false }: { small?: boolean }) {
  return <span className={`spinner${small ? " spinner--small" : ""}`} aria-hidden="true" />;
}

export function FullPageLoader({ label }: { label: string }) {
  return <div className="full-loader"><div className="brand-mark"><Icon name="calendar" /></div><Spinner /><p>{label}…</p></div>;
}

export function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: "success" | "warning" | "danger" | "neutral" | "purple" }) {
  return <span className={`badge badge--${tone}`}><span className="badge__dot" />{children}</span>;
}

export function StatusBadge({ status }: { status: string }) {
  const tone = status === "SUCCEEDED" || status === "READY" || status === "ACTIVE"
    ? "success"
    : status === "RUNNING" || status === "PENDING" || status === "DRAFT"
      ? "warning"
      : status === "FAILED" || status === "INFEASIBLE" || status === "CANCELLED"
        ? "danger"
        : "neutral";
  return <Badge tone={tone}>{humanize(status)}</Badge>;
}

export function PageHeader({ eyebrow, title, description, actions }: { eyebrow?: string; title: string; description?: string; actions?: ReactNode }) {
  return (
    <header className="page-header">
      <div>{eyebrow && <p className="eyebrow">{eyebrow}</p>}<h1>{title}</h1>{description && <p>{description}</p>}</div>
      {actions && <div className="page-header__actions">{actions}</div>}
    </header>
  );
}

export function StatCard({ label, value, detail, icon, tone = "green" }: { label: string; value: ReactNode; detail: string; icon: IconName; tone?: "green" | "gold" | "purple" | "blue" }) {
  return (
    <article className="stat-card">
      <div className={`stat-card__icon stat-card__icon--${tone}`}><Icon name={icon} /></div>
      <div><p>{label}</p><strong>{value}</strong><span>{detail}</span></div>
    </article>
  );
}

export function EmptyState({ icon = "calendar", title, description, action }: { icon?: IconName; title: string; description: string; action?: ReactNode }) {
  return <div className="empty-state"><div className="empty-state__icon"><Icon name={icon} /></div><h3>{title}</h3><p>{description}</p>{action}</div>;
}

export function ErrorBanner({ message }: { message: string }) {
  return <div className="error-banner" role="alert"><Icon name="x" /><span>{message}</span></div>;
}
