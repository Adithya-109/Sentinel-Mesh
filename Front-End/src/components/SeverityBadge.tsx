import type { Severity } from '../imports/types'

const CONFIG: Record<Severity, { icon: string; label: string; bg: string; text: string; border: string }> = {
  info: { icon: 'ℹ', label: 'INFO', bg: 'rgba(16, 185, 129, 0.14)', text: '#10b981', border: 'rgba(16, 185, 129, 0.35)' },
  low: { icon: '▲', label: 'LOW', bg: 'rgba(56, 189, 248, 0.14)', text: '#38bdf8', border: 'rgba(56, 189, 248, 0.35)' },
  medium: { icon: '⚡', label: 'MED', bg: 'rgba(245, 158, 11, 0.16)', text: '#f59e0b', border: 'rgba(245, 158, 11, 0.4)' },
  high: { icon: '●', label: 'HIGH', bg: 'rgba(224, 76, 30, 0.18)', text: '#e04c1e', border: 'rgba(224, 76, 30, 0.45)' },
  critical: { icon: '☠', label: 'CRIT', bg: 'rgba(239, 68, 68, 0.22)', text: '#ef4444', border: 'rgba(239, 68, 68, 0.55)' },
}

interface Props {
  severity: Severity
  compact?: boolean
}

export default function SeverityBadge({ severity, compact }: Props) {
  const { icon, label, bg, text, border } = CONFIG[severity]
  return (
    <span
      style={{ backgroundColor: bg, color: text, border: `1px solid ${border}` }}
      className="inline-flex items-center gap-1 rounded px-2 py-0.5 font-mono text-xs font-semibold tracking-wide whitespace-nowrap shadow-sm"
    >
      <span aria-hidden>{icon}</span>
      {!compact && <span>{label}</span>}
    </span>
  )
}
