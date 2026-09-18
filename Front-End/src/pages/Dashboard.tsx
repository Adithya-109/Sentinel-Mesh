import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { Link } from 'react-router-dom'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, ResponsiveContainer,
} from 'recharts'
import { api, LAYER_LABEL } from '../imports/api'
import type { SmEvent, Incident, Status, EnergySample, ExperimentRow, ScanResult } from '../imports/types'
import SeverityBadge from '../components/SeverityBadge'
import { computeIncidentMetrics } from '../imports/analytics'
import MetricsGrid from '../components/dashboard/MetricsGrid'
import AttackKillChainFunnel from '../components/dashboard/AttackKillChainFunnel'
import ThreatAnalyticsCharts from '../components/dashboard/ThreatAnalyticsCharts'
import DefenseBenchmarkChart from '../components/dashboard/DefenseBenchmarkChart'
import TiltCard from '../components/3d/TiltCard'
import CreativeGeometricBackground from '../components/3d/CreativeGeometricBackground'

type Tab = 'overview' | 'events' | 'incidents' | 'energy' | 'experiment' | 'scan'

function useInterval(cb: () => void, ms: number) {
  const saved = useRef(cb)
  useEffect(() => { saved.current = cb }, [cb])
  useEffect(() => {
    const id = setInterval(() => saved.current(), ms)
    return () => clearInterval(id)
  }, [ms])
}

function fmt(ts: number) {
  return new Date(ts).toLocaleTimeString()
}

function LinkStateBadge({ link }: { link: string }) {
  const colors: Record<string, { bg: string; text: string; border: string }> = {
    ok: { bg: 'rgba(16, 185, 129, 0.15)', text: '#10b981', border: 'rgba(16, 185, 129, 0.4)' },
    attack: { bg: 'rgba(224, 76, 30, 0.2)', text: '#ff6b35', border: 'rgba(224, 76, 30, 0.5)' },
    tamper: { bg: 'rgba(239, 68, 68, 0.2)', text: '#ef4444', border: 'rgba(239, 68, 68, 0.5)' },
    degraded: { bg: 'rgba(245, 158, 11, 0.2)', text: '#f59e0b', border: 'rgba(245, 158, 11, 0.4)' },
  }
  const c = colors[link] ?? { bg: 'rgba(255, 255, 255, 0.1)', text: '#e2d5de', border: 'rgba(255, 255, 255, 0.2)' }
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 font-mono text-xs font-bold uppercase tracking-wider shadow-sm"
      style={{ backgroundColor: c.bg, color: c.text, border: `1px solid ${c.border}` }}
    >
      <span className="text-[10px]">
        {link === 'attack' ? '⚡' : link === 'tamper' ? '☠' : link === 'ok' ? '✓' : '⚠'}
      </span>
      {link}
    </span>
  )
}

const glassCardStyle: React.CSSProperties = {
  backgroundColor: 'rgba(28, 10, 25, 0.92)',
  border: '1px solid #4a1f40',
  backdropFilter: 'blur(16px)',
  boxShadow: '0 8px 32px rgba(0, 0, 0, 0.45), inset 0 1px 0 rgba(255, 255, 255, 0.08)',
}

const glassItemStyle: React.CSSProperties = {
  backgroundColor: 'rgba(18, 5, 16, 0.85)',
  border: '1px solid #3d1433',
}

export default function Dashboard() {
  const [tab, setTab] = useState<Tab>('overview')
  const [status, setStatus] = useState<Status | null>(null)
  const [events, setEvents] = useState<SmEvent[]>([])
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [energySamples, setEnergySamples] = useState<EnergySample[]>([])
  const [experiment, setExperiment] = useState<ExperimentRow[]>([])
  const [scanText, setScanText] = useState('')
  const [scanResults, setScanResults] = useState<ScanResult[] | null>(null)
  const [scanning, setScanning] = useState(false)
  const lastEventTs = useRef(0)
  const lastEnergyTs = useRef(0)

  const fetchStatus = useCallback(async () => {
    try { setStatus(await api.status()) } catch {}
  }, [])

  const fetchEvents = useCallback(async () => {
    try {
      const ev = await api.events(lastEventTs.current)
      if (ev.length > 0) {
        lastEventTs.current = Math.max(...ev.map((e) => e.ts))
        setEvents((prev) => {
          const ids = new Set(prev.map((e) => e.id))
          const fresh = ev.filter((e) => !ids.has(e.id))
          return [...fresh, ...prev].slice(0, 200)
        })
      }
    } catch {}
  }, [])

  const fetchIncidents = useCallback(async () => {
    try { setIncidents(await api.incidents()) } catch {}
  }, [])

  const fetchEnergy = useCallback(async () => {
    try {
      const data = await api.energy(lastEnergyTs.current)
      if (data.samples.length > 0) {
        lastEnergyTs.current = Math.max(...data.samples.map((s) => s.ts))
        setEnergySamples((prev) => {
          const existing = new Set(prev.map((s) => s.ts))
          const fresh = data.samples.filter((s) => !existing.has(s.ts))
          return [...prev, ...fresh].slice(-600)
        })
      }
    } catch {}
  }, [])

  useEffect(() => {
    fetchStatus(); fetchEvents(); fetchIncidents(); fetchEnergy()
    api.experiment().then((d) => setExperiment(d.rows)).catch(() => {})
  }, [fetchStatus, fetchEvents, fetchIncidents, fetchEnergy])

  useInterval(fetchStatus, 1000)
  useInterval(fetchEvents, 1000)
  useInterval(fetchEnergy, 1000)
  useInterval(fetchIncidents, 3000)

  const metrics = useMemo(
    () => computeIncidentMetrics(incidents, events, status, experiment),
    [incidents, events, status, experiment]
  )

  const handleScanEmail = async () => {
    setScanning(true)
    setScanResults(null)
    try {
      const r = await api.scanEmail(scanText)
      setScanResults(r as unknown as ScanResult[])
    } catch {
      setScanResults([])
    } finally {
      setScanning(false)
    }
  }

  const handleScanFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setScanning(true)
    setScanResults(null)
    try {
      const r = await api.scanFile(file)
      setScanResults(r as unknown as ScanResult[])
    } catch {
      setScanResults([])
    } finally {
      setScanning(false)
    }
  }

  const TABS: { id: Tab; label: string }[] = [
    { id: 'overview', label: 'Overview' },
    { id: 'events', label: 'Events' },
    { id: 'incidents', label: 'Incidents' },
    { id: 'energy', label: 'Energy' },
    { id: 'experiment', label: 'Experiment' },
    { id: 'scan', label: 'Scan' },
  ]

  // Energy chart data: use relative seconds for X axis
  const baseTs = energySamples[0]?.ts ?? 0
  const energyChartData = energySamples.map((s) => ({
    t: baseTs ? Math.round((s.ts - baseTs) / 1000) : 0,
    power: Math.round(s.power_mw),
    battery: Math.round(s.battery_pct * 10) / 10,
  }))

  // Attack start at ~180s, EnergyGate at ~420s
  const attackAt = energySamples.length > 0
    ? Math.round((1789000180000 - energySamples[0].ts) / 1000)
    : null
  const gateAt = energySamples.length > 0
    ? Math.round((1789000420000 - energySamples[0].ts) / 1000)
    : null

  return (
    <div
      className="relative flex min-h-screen selection:bg-[#e04c1e] selection:text-white"
      style={{ backgroundColor: '#180814', color: '#ffffff', fontFamily: "'Manrope', sans-serif" }}
    >
      {/* Sidebar */}
      <aside
        className="flex flex-col gap-6 px-4 py-6 shrink-0 z-20"
        style={{ width: 220, backgroundColor: '#10040d', borderRight: '1px solid #2d0e25' }}
      >
        <Link to="/" className="flex items-center gap-2.5 group transition-opacity hover:opacity-90">
          <div className="w-8 h-8 rounded-lg bg-[#e04c1e] flex items-center justify-center shadow-md transition-transform group-hover:rotate-6">
            <svg width="20" height="20" viewBox="0 0 22 22" fill="none" aria-hidden>
              <polygon points="11,1 21,6 21,16 11,21 1,16 1,6" stroke="#ffffff" strokeWidth="2" fill="none" />
              <circle cx="11" cy="11" r="3" fill="#ffffff" />
            </svg>
          </div>
          <div className="flex flex-col">
            <span className="text-sm font-extrabold tracking-tight text-white">
              Sentinel<span className="text-[#e04c1e]">Mesh</span>
            </span>
            <span className="text-[10px] text-[#dba136] font-mono tracking-widest uppercase">
              Security Console
            </span>
          </div>
        </Link>

        <nav className="flex flex-col gap-1.5">
          {TABS.map(({ id, label }) => {
            const isActive = tab === id
            return (
              <button
                key={id}
                onClick={() => setTab(id)}
                className="text-left px-3.5 py-2.5 rounded-xl text-xs font-bold uppercase tracking-wider transition-all cursor-pointer flex items-center justify-between group"
                style={{
                  backgroundColor: isActive ? '#e04c1e' : 'transparent',
                  color: isActive ? '#ffffff' : '#e2d5de',
                  boxShadow: isActive ? '0 4px 14px rgba(224, 76, 30, 0.35)' : 'none',
                }}
              >
                <span>{label}</span>
                {isActive && <span className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" />}
              </button>
            )
          })}
        </nav>

        <div className="mt-auto pt-4 border-t border-[#2d0e25]">
          <Link
            to="/"
            className="flex items-center justify-center gap-2 text-xs font-bold px-3.5 py-2.5 rounded-xl transition-all hover:bg-[#2a0e24] hover:border-[#dba136] text-center"
            style={{ backgroundColor: '#180814', border: '1px solid #3d1433', color: '#ffffff' }}
          >
            <span>←</span>
            <span>Landing Page</span>
          </Link>
        </div>
      </aside>

      {/* Main Body */}
      <div className="flex flex-col flex-1 min-w-0 relative overflow-hidden">
        {/* Creative Geometric Interactive Background with Multi-Sized Shapes & Ripple Shockwaves */}
        <CreativeGeometricBackground />

        {/* Ambient Radial Depth Glows */}
        <div
          aria-hidden
          className="absolute -top-40 right-10 w-[650px] h-[650px] rounded-full pointer-events-none opacity-20 blur-[140px] z-0"
          style={{
            background: 'radial-gradient(circle, rgba(224, 76, 30, 0.45) 0%, rgba(219, 161, 54, 0.2) 45%, transparent 75%)',
          }}
        />
        <div
          aria-hidden
          className="absolute -bottom-40 -left-20 w-[500px] h-[500px] rounded-full pointer-events-none opacity-15 blur-[130px] z-0"
          style={{
            background: 'radial-gradient(circle, rgba(56, 189, 248, 0.35) 0%, rgba(30, 10, 25, 0.1) 50%, transparent 75%)',
          }}
        />

        {/* Top Status bar */}
        {status && (
          <div
            className="flex flex-wrap items-center gap-4 px-6 py-3 text-sm shrink-0 z-10 backdrop-blur-xl"
            style={{
              backgroundColor: 'rgba(20, 5, 17, 0.92)',
              borderBottom: '1px solid #3d1433',
              boxShadow: '0 4px 20px rgba(0, 0, 0, 0.35)',
            }}
          >
            <LinkStateBadge link={status.link} />
            <span className="font-mono text-xs text-[#dba136] font-semibold">
              ML-KEM-{status.crypto_level}
            </span>
            <span
              style={{ color: status.battery_pct < 20 ? '#ef4444' : '#10b981' }}
              className="font-mono text-sm font-bold"
            >
              🔋 {status.battery_pct.toFixed(1)}%
            </span>
            <span className="font-mono text-xs text-white">
              ⚡ {status.power_mw.toFixed(0)} mW
              <span className="text-[#e2d5de]/60"> / baseline {status.baseline_mw} mW</span>
            </span>
            <span className="font-mono text-xs text-[#f59e0b] font-semibold">
              ⏱ {status.projected_days.toFixed(1)} days left
            </span>
            {status.attack_profile !== 'none' && (
              <span
                className="font-mono text-xs px-2.5 py-0.5 rounded-full uppercase font-bold"
                style={{ backgroundColor: 'rgba(224, 76, 30, 0.2)', color: '#ff6b35', border: '1px solid rgba(224, 76, 30, 0.4)' }}
              >
                profile: {status.attack_profile}
              </span>
            )}
            {/* Per-node */}
            {status.nodes.map((n) => (
              <span
                key={n.id}
                className="font-mono text-xs px-2 py-0.5 rounded-full"
                style={{
                  backgroundColor:
                    n.state === 'tamper'
                      ? 'rgba(239, 68, 68, 0.2)'
                      : n.state === 'attack'
                      ? 'rgba(224, 76, 30, 0.2)'
                      : 'rgba(56, 189, 248, 0.15)',
                  color:
                    n.state === 'tamper'
                      ? '#ef4444'
                      : n.state === 'attack'
                      ? '#ff6b35'
                      : '#38bdf8',
                  border:
                    n.state === 'tamper'
                      ? '1px solid rgba(239, 68, 68, 0.4)'
                      : n.state === 'attack'
                      ? '1px solid rgba(224, 76, 30, 0.4)'
                      : '1px solid rgba(56, 189, 248, 0.3)',
                }}
              >
                {n.id}: {n.state} | {n.rssi} dBm | {n.battery_pct !== null ? `${n.battery_pct.toFixed(0)}%` : 'pwr'}
              </span>
            ))}
            <Link
              to="/"
              className="ml-auto text-xs font-mono text-[#e2d5de]/70 hover:text-white transition-colors flex items-center gap-1 shrink-0 group"
            >
              <span className="group-hover:-translate-x-0.5 transition-transform">←</span>
              <span>Website</span>
            </Link>
          </div>
        )}

        {/* Tab content */}
        <div className="flex-1 p-6 overflow-auto z-10">

          {/* OVERVIEW */}
          {tab === 'overview' && (
            <div className="flex flex-col gap-6">
              {/* Header */}
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div>
                  <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
                    Security Operations <span className="text-[#dba136]">Overview</span>
                  </h1>
                  <p className="text-xs text-[#e2d5de]/70 mt-1 font-['Figtree',sans-serif]">
                    Real-time telemetry, threat detection, and power dissipation analytics
                  </p>
                </div>
                <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-[#10b981]/15 border border-[#10b981]/30">
                  <span className="h-2 w-2 rounded-full bg-[#10b981] animate-pulse" />
                  <span className="font-mono text-xs text-[#10b981] font-semibold">Telemetry Ingestion: Active</span>
                </div>
              </div>

              {/* 1. Executive Metrics Grid */}
              <MetricsGrid metrics={metrics} status={status} />

              {/* 2. Multi-Stage Attack Kill Chain Funnel */}
              <AttackKillChainFunnel stages={metrics.stages} />

              {/* 3. Threat Severity Distribution & MITRE ATT&CK Matrix */}
              <ThreatAnalyticsCharts
                severityDistribution={metrics.severityDistribution}
                mitreTechniques={metrics.mitreTechniques}
              />

              {/* 4. Defense Strategy Benchmark Chart */}
              <DefenseBenchmarkChart defenseComparisons={metrics.defenseComparisons} />

              {/* 5. Incident & Telemetry Stream Drilldown */}
              <div className="grid md:grid-cols-2 gap-6">
                {/* Active Incidents */}
                <TiltCard
                  className="flex flex-col gap-3 rounded-2xl p-5 shadow-2xl transition-all backdrop-blur-xl hover:border-[#e04c1e]/60"
                  glareColor="rgba(224, 76, 30, 0.12)"
                  maxRotation={3}
                  style={glassCardStyle}
                >
                  <div className="flex items-center justify-between border-b border-[#3d1433] pb-2.5">
                    <p className="text-xs font-bold uppercase tracking-widest text-[#dba136]">
                      Active Incidents ({incidents.length})
                    </p>
                    <button
                      onClick={() => setTab('incidents')}
                      className="text-xs font-semibold text-[#ff6b35] transition-colors hover:text-white hover:underline cursor-pointer"
                    >
                      View Details →
                    </button>
                  </div>
                  {incidents.map((inc) => (
                    <div
                      key={inc.id}
                      className="flex flex-col gap-2 p-3.5 rounded-xl transition-all hover:border-[#e04c1e]/50"
                      style={glassItemStyle}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <SeverityBadge severity={inc.severity} />
                          <span className="text-sm font-semibold text-white">{inc.title}</span>
                        </div>
                        <span className="text-xs font-mono text-[#e2d5de]/50">
                          {metrics.attackDurationFormatted}
                        </span>
                      </div>
                      <p className="text-xs text-[#e2d5de]/70 font-['Figtree',sans-serif]">
                        Layers: {inc.layers.map((l) => LAYER_LABEL[l]).join(' → ')}
                      </p>
                      <div className="flex flex-wrap gap-1.5 mt-1">
                        {inc.techniques.map((t) => (
                          <span
                            key={t}
                            className="font-mono text-[10px] px-2 py-0.5 rounded-full bg-[#2a0e24] text-[#dba136] border border-[#3d1433]"
                          >
                            {t}
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
                  {incidents.length === 0 && (
                    <p className="text-sm text-[#e2d5de]/50">No active incidents</p>
                  )}
                </TiltCard>

                {/* Recent Events Stream */}
                <TiltCard
                  className="flex flex-col gap-3 rounded-2xl p-5 shadow-2xl transition-all backdrop-blur-xl hover:border-[#dba136]/60"
                  glareColor="rgba(219, 161, 54, 0.12)"
                  maxRotation={3}
                  style={glassCardStyle}
                >
                  <div className="flex items-center justify-between border-b border-[#3d1433] pb-2.5">
                    <p className="text-xs font-bold uppercase tracking-widest text-[#dba136]">
                      Recent Telemetry Events
                    </p>
                    <button
                      onClick={() => setTab('events')}
                      className="text-xs font-semibold text-[#ff6b35] transition-colors hover:text-white hover:underline cursor-pointer"
                    >
                      All Events ({events.length}) →
                    </button>
                  </div>
                  <div className="flex flex-col gap-2">
                    {events.slice(0, 5).map((ev) => (
                      <div
                        key={ev.id}
                        className="flex items-start gap-2.5 p-2.5 rounded-xl text-xs transition-colors hover:bg-[#250b1f]"
                        style={glassItemStyle}
                      >
                        <SeverityBadge severity={ev.severity} compact />
                        <span className="font-mono text-[#e2d5de]/70 shrink-0 text-[11px]">{fmt(ev.ts)}</span>
                        <div className="flex flex-col min-w-0 flex-1">
                          <span className="text-white truncate font-medium">{ev.summary}</span>
                          {ev.node && (
                            <span className="text-[10px] font-mono text-[#38bdf8]">node: {ev.node}</span>
                          )}
                        </div>
                      </div>
                    ))}
                    {events.length === 0 && (
                      <p className="text-sm text-[#e2d5de]/50">No events recorded</p>
                    )}
                  </div>
                </TiltCard>
              </div>

              {/* 6. Hardware & Node Mesh Topology */}
              {status && status.nodes.length > 0 && (
                <TiltCard
                  className="flex flex-col gap-3 rounded-2xl p-5 shadow-2xl backdrop-blur-xl"
                  glareColor="rgba(224, 76, 30, 0.12)"
                  maxRotation={2}
                  style={glassCardStyle}
                >
                  <div className="flex items-center justify-between border-b border-[#3d1433] pb-2.5">
                    <p className="text-xs font-bold uppercase tracking-widest text-[#dba136]">
                      Sensor Mesh Topology & Hardware Status
                    </p>
                    <span className="font-mono text-xs text-[#e2d5de]/70">
                      Crypto Level: ML-KEM-{status.crypto_level}
                    </span>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-1">
                    {status.nodes.map((n) => (
                      <div
                        key={n.id}
                        className="flex items-center justify-between p-3.5 rounded-xl transition-all"
                        style={{
                          ...glassItemStyle,
                          border: n.state === 'tamper' ? '1px solid rgba(239, 68, 68, 0.6)' : glassItemStyle.border,
                        }}
                      >
                        <div className="flex flex-col gap-1">
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-sm font-bold text-white">
                              {n.id}
                            </span>
                            <span
                              className="text-[10px] font-mono font-bold px-2 py-0.5 rounded-full uppercase"
                              style={{
                                backgroundColor:
                                  n.state === 'tamper'
                                    ? 'rgba(239, 68, 68, 0.2)'
                                    : n.state === 'attack'
                                    ? 'rgba(224, 76, 30, 0.2)'
                                    : 'rgba(56, 189, 248, 0.15)',
                                color:
                                  n.state === 'tamper'
                                    ? '#ef4444'
                                    : n.state === 'attack'
                                    ? '#ff6b35'
                                    : '#38bdf8',
                                border:
                                  n.state === 'tamper'
                                    ? '1px solid rgba(239, 68, 68, 0.4)'
                                    : n.state === 'attack'
                                    ? '1px solid rgba(224, 76, 30, 0.4)'
                                    : '1px solid rgba(56, 189, 248, 0.3)',
                              }}
                            >
                              {n.state}
                            </span>
                          </div>
                          <span className="text-xs text-[#e2d5de]/60 font-mono">
                            Heartbeat: {n.last_seen_ms} ms ago
                          </span>
                        </div>
                        <div className="flex flex-col items-end gap-1 font-mono text-xs">
                          <span className="text-[#dba136]">RSSI: {n.rssi} dBm</span>
                          <span style={{ color: n.battery_pct !== null ? '#38bdf8' : '#10b981' }}>
                            {n.battery_pct !== null ? `Battery: ${n.battery_pct.toFixed(1)}%` : 'Mains Powered'}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </TiltCard>
              )}
            </div>
          )}

          {/* EVENTS */}
          {tab === 'events' && (
            <div className="flex flex-col gap-4">
              <div className="flex items-center justify-between">
                <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
                  Events <span className="text-[#dba136] text-lg font-normal">({events.length})</span>
                </h1>
              </div>
              <div className="overflow-x-auto rounded-2xl shadow-2xl backdrop-blur-xl" style={{ ...glassCardStyle, overflow: 'hidden' }}>
                <table className="w-full text-sm" style={{ borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ backgroundColor: 'rgba(18, 5, 16, 0.95)', borderBottom: '1px solid #3d1433' }}>
                      {['Time', 'Layer', 'Severity', 'Node', 'Summary', 'Reasons'].map((h) => (
                        <th
                          key={h}
                          className="px-4 py-3 text-left text-xs font-bold uppercase tracking-widest"
                          style={{ color: '#dba136' }}
                        >
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {events.map((ev, i) => (
                      <tr
                        key={ev.id}
                        className="transition-colors hover:bg-[#2c0f25]"
                        style={{
                          backgroundColor: i % 2 === 0 ? 'rgba(30, 10, 25, 0.85)' : 'rgba(20, 6, 17, 0.85)',
                          borderBottom: '1px solid #3d1433',
                        }}
                      >
                        <td className="px-4 py-2.5 whitespace-nowrap font-mono text-xs text-[#e2d5de]/70">
                          {fmt(ev.ts)}
                        </td>
                        <td className="px-4 py-2.5 whitespace-nowrap text-xs font-semibold text-white">
                          {LAYER_LABEL[ev.layer]}
                        </td>
                        <td className="px-4 py-2.5">
                          <SeverityBadge severity={ev.severity} />
                        </td>
                        <td className="px-4 py-2.5 text-xs whitespace-nowrap font-mono text-[#38bdf8]">
                          {ev.node ?? '—'}
                        </td>
                        <td className="px-4 py-2.5 text-xs text-[#e2d5de]" style={{ maxWidth: 280 }}>
                          {ev.summary}
                        </td>
                        <td className="px-4 py-2.5">
                          <ul className="list-none flex flex-col gap-0.5">
                            {ev.reasons.slice(0, 3).map((r) => (
                              <li key={r} className="text-xs text-[#e2d5de]/70 font-['Figtree',sans-serif]">
                                · {r}
                              </li>
                            ))}
                          </ul>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* INCIDENTS */}
          {tab === 'incidents' && (
            <div className="flex flex-col gap-5">
              <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">Incidents</h1>
              {incidents.length === 0 && <p className="text-[#e2d5de]/60">No incidents.</p>}
              {incidents.map((inc) => (
                <TiltCard
                  key={inc.id}
                  className="flex flex-col gap-4 p-6 rounded-2xl shadow-2xl transition-all backdrop-blur-xl hover:border-[#e04c1e]/60"
                  glareColor="rgba(224, 76, 30, 0.12)"
                  maxRotation={3}
                  style={glassCardStyle}
                >
                  <div className="flex items-center gap-3 flex-wrap border-b border-[#3d1433] pb-3">
                    <SeverityBadge severity={inc.severity} />
                    <h2 className="text-lg font-bold text-white">{inc.title}</h2>
                    <span className="text-xs font-mono text-[#e2d5de]/60 ml-auto">
                      {fmt(inc.started_ts)} → {fmt(inc.last_ts)}
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {inc.layers.map((l) => (
                      <span
                        key={l}
                        className="text-xs px-2.5 py-1 rounded-full font-medium"
                        style={{ backgroundColor: '#2a0e24', color: '#dba136', border: '1px solid #3d1433' }}
                      >
                        {LAYER_LABEL[l]}
                      </span>
                    ))}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {inc.techniques.map((t) => (
                      <span
                        key={t}
                        className="text-xs px-2.5 py-0.5 rounded-full font-mono font-medium"
                        style={{ backgroundColor: 'rgba(56, 189, 248, 0.15)', color: '#38bdf8', border: '1px solid rgba(56, 189, 248, 0.3)' }}
                      >
                        {t}
                      </span>
                    ))}
                  </div>
                  <div>
                    <p className="text-xs mb-2 font-bold uppercase tracking-wider text-[#dba136]">Stages</p>
                    <div className="flex flex-wrap gap-2">
                      {Object.entries(inc.stages).map(([stage, result]) => (
                        <span
                          key={stage}
                          className="text-xs px-2.5 py-1 rounded-full font-medium uppercase"
                          style={{
                            backgroundColor: result === 'hit' ? 'rgba(224, 76, 30, 0.2)' : 'rgba(16, 185, 129, 0.15)',
                            color: result === 'hit' ? '#ff6b35' : '#10b981',
                            border: result === 'hit' ? '1px solid rgba(224, 76, 30, 0.4)' : '1px solid rgba(16, 185, 129, 0.3)',
                          }}
                        >
                          {stage}: {result}
                        </span>
                      ))}
                    </div>
                  </div>
                  <div className="pt-2 border-t border-[#3d1433]">
                    <p className="text-xs mb-2 font-bold uppercase tracking-wider text-[#dba136]">
                      Linked Events ({inc.event_ids.length})
                    </p>
                    {inc.event_ids.map((eid) => {
                      const ev = events.find((e) => e.id === eid)
                      if (!ev) return null
                      return (
                        <div key={eid} className="flex items-start gap-2.5 py-1.5 text-xs">
                          <SeverityBadge severity={ev.severity} compact />
                          <span className="font-mono text-[#e2d5de]/70 shrink-0 text-[11px]">{fmt(ev.ts)}</span>
                          <span className="text-[#e2d5de]">{ev.summary}</span>
                        </div>
                      )
                    })}
                  </div>
                </TiltCard>
              ))}
            </div>
          )}

          {/* ENERGY */}
          {tab === 'energy' && (
            <div className="flex flex-col gap-6">
              <div>
                <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">Energy Dissipation</h1>
                <p className="text-xs text-[#e2d5de]/60 mt-1 font-['Figtree',sans-serif]">
                  Hardware joule telemetry collected via INA219 sensor on nRF5340 board.
                </p>
              </div>

              {/* Chart A: Power Draw */}
              <TiltCard
                className="rounded-2xl p-5 shadow-2xl backdrop-blur-xl hover:border-[#e04c1e]/60 transition-all"
                glareColor="rgba(224, 76, 30, 0.12)"
                maxRotation={2}
                style={glassCardStyle}
              >
                <div className="flex items-center justify-between mb-4 border-b border-[#3d1433] pb-2.5">
                  <p className="text-xs font-bold uppercase tracking-widest text-[#dba136]">
                    Power Draw (mW) — Real-time Telemetry
                  </p>
                  <span className="font-mono text-xs text-[#ff6b35] font-semibold">INA219 High-Speed Sensor</span>
                </div>
                <ResponsiveContainer width="100%" height={250}>
                  <AreaChart data={energyChartData} margin={{ top: 10, right: 16, left: 0, bottom: 0 }}>
                    <defs>
                      <linearGradient id="powerGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#e04c1e" stopOpacity={0.4} />
                        <stop offset="95%" stopColor="#e04c1e" stopOpacity={0.0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#3d1433" />
                    <XAxis dataKey="t" tick={{ fill: '#e2d5de', fontSize: 10, fontFamily: 'Roboto Mono' }} label={{ value: 'seconds', position: 'insideRight', fill: '#e2d5de', fontSize: 10 }} />
                    <YAxis tick={{ fill: '#dba136', fontSize: 10, fontFamily: 'Roboto Mono' }} width={55} />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#250b1f', border: '1px solid #4a1f40', color: '#ffffff', fontFamily: 'Roboto Mono', fontSize: 11, borderRadius: '8px' }}
                      formatter={(val: number) => [`${val} mW`, 'Power Draw']}
                    />
                    {attackAt !== null && (
                      <ReferenceLine x={attackAt} stroke="#ef4444" strokeDasharray="4 2" label={{ value: 'attack', fill: '#ef4444', fontSize: 10, position: 'top' }} />
                    )}
                    {gateAt !== null && (
                      <ReferenceLine x={gateAt} stroke="#10b981" strokeDasharray="4 2" label={{ value: 'EnergyGate', fill: '#10b981', fontSize: 10, position: 'top' }} />
                    )}
                    {status && (
                      <ReferenceLine y={status.baseline_mw} stroke="#dba136" strokeDasharray="6 3" label={{ value: 'baseline', fill: '#dba136', fontSize: 10, position: 'insideTopRight' }} />
                    )}
                    <Area type="monotone" dataKey="power" stroke="#e04c1e" strokeWidth={2} fill="url(#powerGrad)" dot={false} />
                  </AreaChart>
                </ResponsiveContainer>
              </TiltCard>

              {/* Chart B: Battery % */}
              <TiltCard
                className="rounded-2xl p-5 shadow-2xl backdrop-blur-xl hover:border-[#38bdf8]/60 transition-all"
                glareColor="rgba(56, 189, 248, 0.12)"
                maxRotation={2}
                style={glassCardStyle}
              >
                <div className="flex items-center justify-between mb-4 border-b border-[#3d1433] pb-2.5">
                  <p className="text-xs font-bold uppercase tracking-widest text-[#dba136]">
                    Battery Level (%) — State of Charge
                  </p>
                  <span className="font-mono text-xs text-[#38bdf8] font-semibold">Projected Autonomy</span>
                </div>
                <ResponsiveContainer width="100%" height={250}>
                  <AreaChart data={energyChartData} margin={{ top: 10, right: 16, left: 0, bottom: 0 }}>
                    <defs>
                      <linearGradient id="battGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#38bdf8" stopOpacity={0.4} />
                        <stop offset="95%" stopColor="#38bdf8" stopOpacity={0.0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#3d1433" />
                    <XAxis dataKey="t" tick={{ fill: '#e2d5de', fontSize: 10, fontFamily: 'Roboto Mono' }} label={{ value: 'seconds', position: 'insideRight', fill: '#e2d5de', fontSize: 10 }} />
                    <YAxis tick={{ fill: '#38bdf8', fontSize: 10, fontFamily: 'Roboto Mono' }} width={40} domain={[50, 85]} />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#250b1f', border: '1px solid #4a1f40', color: '#ffffff', fontFamily: 'Roboto Mono', fontSize: 11, borderRadius: '8px' }}
                      formatter={(val: number) => [`${val}%`, 'Battery']}
                    />
                    {attackAt !== null && (
                      <ReferenceLine x={attackAt} stroke="#ef4444" strokeDasharray="4 2" label={{ value: 'attack', fill: '#ef4444', fontSize: 10, position: 'top' }} />
                    )}
                    {gateAt !== null && (
                      <ReferenceLine x={gateAt} stroke="#10b981" strokeDasharray="4 2" label={{ value: 'EnergyGate', fill: '#10b981', fontSize: 10, position: 'top' }} />
                    )}
                    <Area type="monotone" dataKey="battery" stroke="#38bdf8" strokeWidth={2} fill="url(#battGrad)" dot={false} />
                  </AreaChart>
                </ResponsiveContainer>
              </TiltCard>
            </div>
          )}

          {/* EXPERIMENT */}
          {tab === 'experiment' && (
            <div className="flex flex-col gap-4">
              <div>
                <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">Experiment Results</h1>
                <p className="text-xs text-[#e2d5de]/60 mt-1 font-['Figtree',sans-serif]">
                  Comparative benchmark of mitigation strategies under ML-KEM-1024 exhaustion load.
                </p>
              </div>
              <div className="overflow-x-auto rounded-2xl shadow-2xl backdrop-blur-xl" style={{ ...glassCardStyle, overflow: 'hidden' }}>
                <table className="w-full text-sm" style={{ borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ backgroundColor: 'rgba(18, 5, 16, 0.95)', borderBottom: '1px solid #3d1433' }}>
                      {['Condition', 'Energy J/hr', 'Projected Days', 'Legit Connect %', 'Extra Delay ms', 'Status'].map((h) => (
                        <th key={h} className="px-4 py-3 text-left text-xs font-bold uppercase tracking-widest" style={{ color: '#dba136' }}>
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {experiment.map((row, i) => (
                      <tr
                        key={row.condition}
                        className="transition-colors hover:bg-[#2c0f25]"
                        style={{
                          backgroundColor: i % 2 === 0 ? 'rgba(30, 10, 25, 0.85)' : 'rgba(20, 6, 17, 0.85)',
                          borderBottom: '1px solid #3d1433',
                        }}
                      >
                        <td className="px-4 py-3">
                          <div>
                            <p className="text-sm font-semibold text-white">{row.label}</p>
                            <p className="text-xs font-mono text-[#e2d5de]/50">{row.condition}</p>
                          </div>
                        </td>
                        <td className="px-4 py-3 font-mono text-sm text-[#e2d5de]">
                          {row.energy_j_per_hour !== null ? row.energy_j_per_hour.toFixed(1) : '—'}
                        </td>
                        <td
                          className="px-4 py-3 font-mono text-sm font-bold"
                          style={{
                            color: row.projected_days === null ? '#e2d5de'
                              : row.projected_days < 5 ? '#ef4444'
                              : row.projected_days > 30 ? '#10b981'
                              : '#f59e0b',
                          }}
                        >
                          {row.projected_days !== null ? `${row.projected_days.toFixed(1)}d` : '—'}
                        </td>
                        <td
                          className="px-4 py-3 font-mono text-sm font-semibold"
                          style={{ color: row.legit_connect_pct !== null ? (row.legit_connect_pct > 95 ? '#10b981' : '#f59e0b') : '#e2d5de' }}
                        >
                          {row.legit_connect_pct !== null ? `${row.legit_connect_pct}%` : '—'}
                        </td>
                        <td className="px-4 py-3 font-mono text-sm text-[#e2d5de]">
                          {row.legit_extra_delay_ms !== null ? `${row.legit_extra_delay_ms} ms` : '—'}
                        </td>
                        <td className="px-4 py-3">
                          <span
                            className="text-xs px-2.5 py-1 rounded-full font-bold uppercase tracking-wider"
                            style={{
                              backgroundColor:
                                row.status === 'done' ? 'rgba(16, 185, 129, 0.2)' :
                                row.status === 'running' ? 'rgba(245, 158, 11, 0.2)' : 'rgba(255, 255, 255, 0.1)',
                              color:
                                row.status === 'done' ? '#10b981' :
                                row.status === 'running' ? '#f59e0b' : '#e2d5de',
                              border:
                                row.status === 'done' ? '1px solid rgba(16, 185, 129, 0.4)' :
                                row.status === 'running' ? '1px solid rgba(245, 158, 11, 0.4)' : '1px solid rgba(255, 255, 255, 0.2)',
                            }}
                          >
                            {row.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* SCAN */}
          {tab === 'scan' && (
            <div className="flex flex-col gap-6" style={{ maxWidth: 800 }}>
              <div>
                <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">Security Payload Scanner</h1>
                <p className="text-xs text-[#e2d5de]/60 mt-1 font-['Figtree',sans-serif]">
                  Inspect incoming packets, email contents, or binary payloads for quantum handshake anomalies.
                </p>
              </div>

              {/* Email scan */}
              <TiltCard
                className="flex flex-col gap-3.5 p-6 rounded-2xl shadow-2xl backdrop-blur-xl"
                glareColor="rgba(224, 76, 30, 0.12)"
                maxRotation={2}
                style={glassCardStyle}
              >
                <p className="text-xs font-bold uppercase tracking-widest text-[#dba136]">
                  Inspect Payload / Email Text
                </p>
                <textarea
                  value={scanText}
                  onChange={(e) => setScanText(e.target.value)}
                  placeholder="Paste email or raw packet body here…"
                  rows={5}
                  className="w-full rounded-xl p-3.5 text-sm resize-none outline-none font-mono transition-colors focus:border-[#e04c1e]"
                  style={{
                    backgroundColor: '#10040d',
                    border: '1px solid #3d1433',
                    color: '#ffffff',
                  }}
                />
                <button
                  onClick={handleScanEmail}
                  disabled={scanning || !scanText.trim()}
                  className="self-start px-6 py-2.5 rounded-full text-xs font-bold uppercase tracking-wider transition-all cursor-pointer shadow-lg disabled:opacity-50 disabled:cursor-not-allowed hover:brightness-110 active:scale-95"
                  style={{
                    backgroundColor: scanning || !scanText.trim() ? '#2a0e24' : '#e04c1e',
                    color: '#ffffff',
                    boxShadow: scanning || !scanText.trim() ? 'none' : '0 4px 15px rgba(224, 76, 30, 0.35)',
                  }}
                >
                  {scanning ? 'Scanning…' : 'Scan Payload'}
                </button>
              </TiltCard>

              {/* File scan */}
              <TiltCard
                className="flex flex-col gap-3.5 p-6 rounded-2xl shadow-2xl backdrop-blur-xl"
                glareColor="rgba(219, 161, 54, 0.12)"
                maxRotation={2}
                style={glassCardStyle}
              >
                <p className="text-xs font-bold uppercase tracking-widest text-[#dba136]">
                  Inspect Binary / Capture File
                </p>
                <input
                  type="file"
                  onChange={handleScanFile}
                  disabled={scanning}
                  className="text-sm file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-xs file:font-semibold file:bg-[#2a0e24] file:text-[#dba136] hover:file:bg-[#3d1433] file:cursor-pointer text-[#e2d5de]/80"
                />
              </TiltCard>

              {/* Scan results */}
              {scanResults !== null && (
                <div className="flex flex-col gap-3">
                  <p className="text-xs font-bold uppercase tracking-widest text-[#dba136]">
                    Results ({scanResults.length})
                  </p>
                  {scanResults.length === 0 && (
                    <p className="text-sm text-[#e2d5de]/60">No anomalies detected in payload.</p>
                  )}
                  {scanResults.map((r) => (
                    <div
                      key={r.id}
                      className="flex flex-col gap-2.5 p-5 rounded-2xl shadow-2xl backdrop-blur-xl"
                      style={glassCardStyle}
                    >
                      <div className="flex items-center gap-2 flex-wrap">
                        <SeverityBadge severity={r.severity} />
                        <span className="text-sm font-semibold text-white">{r.summary}</span>
                      </div>
                      {r.score !== null && (
                        <p className="text-xs font-mono text-[#dba136] font-bold">
                          Anomaly Score: {r.score.toFixed(2)}
                        </p>
                      )}
                      <ul className="flex flex-col gap-1 mt-1">
                        {r.reasons.map((reason) => (
                          <li key={reason} className="text-xs text-[#e2d5de]/80 font-['Figtree',sans-serif]">
                            · {reason}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
