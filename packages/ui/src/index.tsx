import type { ButtonHTMLAttributes, HTMLAttributes, InputHTMLAttributes, SelectHTMLAttributes, ReactNode } from 'react';
import { Icon, type IconName } from '@brewery/design-system/icons';

export function Button({ busy = false, variant = 'primary', children, disabled, className = '', ...props }:
  ButtonHTMLAttributes<HTMLButtonElement> & { busy?: boolean; variant?: 'primary' | 'secondary' }) {
  return <button type="button" {...props} disabled={disabled || busy} aria-busy={busy || undefined}
    className={`button button--${variant} ${className}`}>{children}</button>;
}

export function Card({ children, className = '', clip = false, ...props }: HTMLAttributes<HTMLElement> & { clip?: boolean }) {
  return <section className={`card ${clip ? 'card--clipped' : ''} ${className}`} {...props}>{children}</section>;
}

export function Badge({ children, tone = 'neutral' }: { children: ReactNode; tone?: 'neutral' | 'positive' }) {
  return <span className={`badge badge--${tone}`}>{children}</span>;
}

export function PageHeading({ eyebrow, title, description, action }: { eyebrow: string; title: string; description: string; action?: ReactNode }) {
  return <div className="page-heading"><div><p className="eyebrow">{eyebrow}</p>
    <h1 id="page-title" tabIndex={-1}>{title}</h1><p>{description}</p></div>{action}</div>;
}

export function SearchField({ label, ...props }: InputHTMLAttributes<HTMLInputElement> & { label: string }) {
  return <label className="search-field"><span className="sr-only">{label}</span><Icon name="search" />
    <input {...props} type="search" /></label>;
}

export function SelectField({ label, children, ...props }: SelectHTMLAttributes<HTMLSelectElement> & { label: string }) {
  return <label className="select-field"><span className="sr-only">{label}</span>
    <select {...props}>{children}</select><Icon name="chevron" /></label>;
}

export function EmptyState({ title, description, badge, children }: { title: ReactNode; description: ReactNode; badge: string; children?: ReactNode }) {
  return <div className="empty-state"><div className="empty-state__illustration" aria-hidden="true">
    <Icon name="book" /><span><Icon name="sprout" /></span></div>
    <Badge tone="positive">{badge}</Badge><h2>{title}</h2><p>{description}</p>
    {children && <div className="empty-state__details small muted">{children}</div>}
  </div>;
}

export function CardFooter({ icon, children }: { icon: IconName; children: ReactNode }) {
  return <div className="card-footer"><Icon name={icon} /><span>{children}</span></div>;
}

export function IconTile({ name }: { name: IconName }) {
  return <span className="icon-tile"><Icon name={name} /></span>;
}

export function IconList({ items, boxed = false, className = '' }: {
  items: { icon: IconName; title: string; description: string }[]; boxed?: boolean; className?: string;
}) {
  return <ul className={`icon-list ${boxed ? 'icon-list--boxed' : ''} ${className}`}>
    {items.map((item) => <li key={item.title}>{boxed ? <IconTile name={item.icon} /> : <Icon name={item.icon} />}
      <div><h3>{item.title}</h3><p>{item.description}</p></div></li>)}
  </ul>;
}

export function InlineNote({ icon, children }: { icon: IconName; children: ReactNode }) {
  return <div className="inline-note"><Icon name={icon} /><p>{children}</p></div>;
}
