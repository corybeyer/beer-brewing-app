import {
  ArrowRight, BookOpen, Check, ChevronDown, ClipboardList, FlaskConical,
  House, Leaf, Link, LockKeyhole, Plus, RefreshCw, Search, Settings,
  ShieldCheck, Sprout, Wheat, WifiOff,
} from 'lucide-react';

const icons = {
  arrow: ArrowRight, book: BookOpen, check: Check, chevron: ChevronDown,
  clipboard: ClipboardList, flask: FlaskConical, home: House, leaf: Leaf,
  link: Link, lock: LockKeyhole, plus: Plus, refresh: RefreshCw, search: Search,
  settings: Settings, shield: ShieldCheck, sprout: Sprout, wheat: Wheat, offline: WifiOff,
};

export type IconName = keyof typeof icons;

export function Icon({ name, className = '' }: { name: IconName; className?: string }) {
  const Component = icons[name];
  return <Component aria-hidden="true" focusable="false" className={`icon ${className}`} strokeWidth={1.7} />;
}
