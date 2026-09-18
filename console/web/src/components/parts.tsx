import type { ReactNode } from "react";
import { Link } from "react-router-dom";

export function Wordmark() {
  return <span className="wordmark">SENTINEL<span>MESH</span></span>;
}

export function ArrowUpRight() {
  return (
    <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.2" aria-hidden>
      <path d="M2.5 9.5L9.5 2.5M4 2.5h5.5V8" strokeLinecap="square" />
    </svg>
  );
}

type ButtonProps = {
  children: ReactNode;
  to?: string;
  href?: string;
  onClick?: () => void;
  contrast?: boolean;
  small?: boolean;
  arrow?: boolean;
  className?: string;
};

/** The site's button: white with indigo text, inverting to an outline on hover. */
export function Button({ children, to, href, onClick, contrast, small, arrow = true, className = "" }: ButtonProps) {
  const cls = `button${contrast ? " button--contrast" : ""}${small ? " button--sm" : ""} ${className}`;
  const inner = (
    <>
      <span className="button-text">{children}</span>
      {arrow && <span className="button-icon"><ArrowUpRight /></span>}
    </>
  );
  if (to) return <Link to={to} className={cls}>{inner}</Link>;
  if (href) return <a href={href} className={cls} target="_blank" rel="noreferrer">{inner}</a>;
  return <button type="button" className={cls} onClick={onClick}>{inner}</button>;
}
