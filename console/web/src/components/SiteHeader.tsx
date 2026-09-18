import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { Wordmark } from "./parts";

export type NavItem = {
  id: string;
  label: string;
  onClick?: () => void;
  to?: string;
  active?: boolean;
  badge?: number;
};

function NavEntry({ item, onDone }: { item: NavItem; onDone?: () => void }) {
  const content = <>{item.label}{!!item.badge && <span className="badge">{item.badge}</span>}</>;
  if (item.to) {
    return <Link to={item.to} className={`underline-link${item.active ? " on" : ""}`} onClick={onDone}>{content}</Link>;
  }
  return (
    <button type="button" className={`tab-btn underline-link${item.active ? " on" : ""}`}
      onClick={() => { item.onClick?.(); onDone?.(); }}>
      {content}
    </button>
  );
}

/** The floating white pill. It slides away while you scroll down and returns on the way up. */
export default function SiteHeader({ nav, action, logoTo = "/" }: { nav: NavItem[]; action?: ReactNode; logoTo?: string }) {
  const [hidden, setHidden] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    let last = window.scrollY;
    let queued = false;
    const onScroll = () => {
      if (queued) return;
      queued = true;
      requestAnimationFrame(() => {
        const y = window.scrollY;
        if (y < 80) setHidden(false);
        else if (y > last + 8) { setHidden(true); setOpen(false); }
        else if (y < last - 8) setHidden(false);
        last = y;
        queued = false;
      });
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header className={`header${hidden ? " hidden" : ""}`}>
      <div className="wrapper">
        <div className="topbar">
          <Link to={logoTo} className="topbar-logo" aria-label="SentinelMesh home"><Wordmark /></Link>
          <nav className="topbar-nav" aria-label="Primary">
            <ul>{nav.map(n => <li key={n.id}><NavEntry item={n} /></li>)}</ul>
          </nav>
          <div className="topbar-action">{action}</div>
          <button type="button" className={`topbar-burger${open ? " open" : ""}`} aria-label="Menu" aria-expanded={open}
            onClick={() => setOpen(o => !o)}>
            <span /><span /><span />
          </button>
          <div className={`topbar-menu${open ? " open" : ""}`}>
            {nav.map(n => (
              n.to
                ? <Link key={n.id} to={n.to} className={n.active ? "on" : ""} onClick={() => setOpen(false)}>{n.label}</Link>
                : <button key={n.id} type="button" className={n.active ? "on" : ""} onClick={() => { n.onClick?.(); setOpen(false); }}>
                    {n.label}{!!n.badge && <span className="badge">{n.badge}</span>}
                  </button>
            ))}
            {action && <div style={{ padding: "12px 10px" }}>{action}</div>}
          </div>
        </div>
      </div>
    </header>
  );
}
