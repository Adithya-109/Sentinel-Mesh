import type { AggregatedDashboardMetrics } from '../../imports/analytics'
import type { Status } from '../../imports/types'
import TiltCard from '../3d/TiltCard'

interface MetricsGridProps {
  metrics: AggregatedDashboardMetrics
  status: Status | null
}

const cardStyle: React.CSSProperties = {
  backgroundColor: 'rgba(28, 10, 25, 0.92)',
  border: '1px solid #4a1f40',
  boxShadow: '0 8px 32px rgba(0, 0, 0, 0.45), inset 0 1px 0 rgba(255, 255, 255, 0.08)',
}

export default function MetricsGrid({ metrics, status }: MetricsGridProps) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {/* 1. Active Incidents & Severity */}
      <TiltCard maxTilt={5} scale={1.02}>
        <div
          className="flex flex-col justify-between rounded-2xl p-5 transition-all h-full backdrop-blur-xl hover:border-[#e04c1e]/60"
          style={cardStyle}
        >
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs uppercase tracking-wider font-bold text-[#dba136]">
              Active Incidents
            </span>
            <span
              className="text-[10px] font-mono font-bold px-2.5 py-0.5 rounded-full uppercase"
              style={{
                backgroundColor: metrics.criticalIncidentsCount > 0 ? 'rgba(239, 68, 68, 0.2)' : 'rgba(16, 185, 129, 0.15)',
                color: metrics.criticalIncidentsCount > 0 ? '#ef4444' : '#10b981',
                border: metrics.criticalIncidentsCount > 0 ? '1px solid rgba(239, 68, 68, 0.5)' : '1px solid rgba(16, 185, 129, 0.4)',
              }}
            >
              {metrics.criticalIncidentsCount > 0 ? 'CRITICAL ALERT' : 'NORMAL'}
            </span>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="font-mono text-3xl font-black text-white tracking-tight">
              {metrics.totalIncidents}
            </span>
            <span className="text-xs font-mono font-semibold text-[#ff6b35]">
              ({metrics.criticalIncidentsCount} critical)
            </span>
          </div>
          <div className="mt-3 pt-2.5 border-t border-[#3d1433] text-xs flex items-center justify-between text-[#e2d5de]/70">
            <span>Telemetry events:</span>
            <span className="font-mono font-semibold text-white">
              {metrics.totalEvents} logged
            </span>
          </div>
        </div>
      </TiltCard>

      {/* 2. MTTR & Attack Duration */}
      <TiltCard maxTilt={5} scale={1.02}>
        <div
          className="flex flex-col justify-between rounded-2xl p-5 transition-all h-full backdrop-blur-xl hover:border-[#dba136]/60"
          style={cardStyle}
        >
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs uppercase tracking-wider font-bold text-[#dba136]">
              Attack Duration / MTTR
            </span>
            <span
              className="text-[10px] font-mono font-bold px-2.5 py-0.5 rounded-full"
              style={{
                backgroundColor: 'rgba(219, 161, 54, 0.15)',
                color: '#dba136',
                border: '1px solid rgba(219, 161, 54, 0.4)',
              }}
            >
              ACTIVE
            </span>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="font-mono text-3xl font-black text-white tracking-tight">
              {metrics.attackDurationFormatted}
            </span>
            <span className="text-xs font-mono text-[#e2d5de]/60">elapsed</span>
          </div>
          <div className="mt-3 pt-2.5 border-t border-[#3d1433] text-xs flex items-center justify-between text-[#e2d5de]/70">
            <span>Peak event rate:</span>
            <span className="font-mono font-semibold text-[#dba136]">
              {metrics.eventsPerMinute} ev/min
            </span>
          </div>
        </div>
      </TiltCard>

      {/* 3. Power Drain & Anomaly */}
      <TiltCard maxTilt={5} scale={1.02}>
        <div
          className="flex flex-col justify-between rounded-2xl p-5 transition-all h-full backdrop-blur-xl hover:border-[#e04c1e]/60"
          style={cardStyle}
        >
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs uppercase tracking-wider font-bold text-[#dba136]">
              Power Spike Factor
            </span>
            <span
              className="text-[10px] font-mono font-bold px-2.5 py-0.5 rounded-full"
              style={{
                backgroundColor: metrics.powerAnomalyMultiplier > 2 ? 'rgba(224, 76, 30, 0.2)' : 'rgba(16, 185, 129, 0.15)',
                color: metrics.powerAnomalyMultiplier > 2 ? '#ff6b35' : '#10b981',
                border: metrics.powerAnomalyMultiplier > 2 ? '1px solid rgba(224, 76, 30, 0.5)' : '1px solid rgba(16, 185, 129, 0.4)',
              }}
            >
              {metrics.powerAnomalyMultiplier}× SPIKE
            </span>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="font-mono text-3xl font-black text-white tracking-tight">
              {metrics.peakPowerMw} mW
            </span>
            <span className="text-xs font-mono text-[#e2d5de]/60">
              / {metrics.baselinePowerMw} mW base
            </span>
          </div>
          <div className="mt-3 pt-2.5 border-t border-[#3d1433] text-xs flex items-center justify-between text-[#e2d5de]/70">
            <span>Attack profile:</span>
            <span className="font-mono font-semibold text-[#ff6b35] uppercase">
              {status?.attack_profile ?? 'energy_drain'}
            </span>
          </div>
        </div>
      </TiltCard>

      {/* 4. Battery Autonomy & Depletion */}
      <TiltCard maxTilt={5} scale={1.02}>
        <div
          className="flex flex-col justify-between rounded-2xl p-5 transition-all h-full backdrop-blur-xl hover:border-[#38bdf8]/60"
          style={cardStyle}
        >
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs uppercase tracking-wider font-bold text-[#dba136]">
              Battery Degradation
            </span>
            <span
              className="text-[10px] font-mono font-bold px-2.5 py-0.5 rounded-full"
              style={{
                backgroundColor: 'rgba(239, 68, 68, 0.2)',
                color: '#ef4444',
                border: '1px solid rgba(239, 68, 68, 0.5)',
              }}
            >
              -{metrics.batteryDegradationPct}% LOSS
            </span>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="font-mono text-3xl font-black text-white tracking-tight">
              {metrics.projectedDaysCurrent}d
            </span>
            <span className="text-xs font-mono text-[#e2d5de]/60">autonomy remaining</span>
          </div>
          <div className="mt-3 pt-2.5 border-t border-[#3d1433] text-xs flex items-center justify-between text-[#e2d5de]/70">
            <span>Baseline autonomy:</span>
            <span className="font-mono font-semibold text-[#38bdf8]">
              {metrics.projectedDaysIdle}d nominal
            </span>
          </div>
        </div>
      </TiltCard>
    </div>
  )
}
