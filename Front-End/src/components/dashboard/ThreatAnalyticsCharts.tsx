import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Tooltip as RechartsTooltip,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
} from 'recharts'
import type { SeverityCount, MitreTechniqueMetric } from '../../imports/analytics'
import TiltCard from '../3d/TiltCard'

interface ThreatAnalyticsChartsProps {
  severityDistribution: SeverityCount[]
  mitreTechniques: MitreTechniqueMetric[]
}

interface SeverityTooltipPayload {
  name: string
  value: number
  payload: SeverityCount
}

interface MitreTooltipPayload {
  payload: MitreTechniqueMetric
}

export default function ThreatAnalyticsCharts({
  severityDistribution,
  mitreTechniques,
}: ThreatAnalyticsChartsProps) {
  const totalEvents = severityDistribution.reduce((acc, curr) => acc + curr.value, 0)

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* 1. Event Severity Donut Chart */}
      <TiltCard
        className="flex flex-col rounded-2xl p-5 shadow-2xl transition-all backdrop-blur-xl hover:border-[#dba136]/60"
        glareColor="rgba(224, 76, 30, 0.15)"
        maxRotation={4}
        style={{
          backgroundColor: 'rgba(28, 10, 25, 0.92)',
          border: '1px solid #4a1f40',
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.45), inset 0 1px 0 rgba(255, 255, 255, 0.08)',
        }}
      >
        <div className="flex items-center justify-between mb-3 border-b border-[#3d1433] pb-2.5">
          <p className="text-xs uppercase tracking-widest font-bold" style={{ color: '#dba136' }}>
            Threat Severity Distribution
          </p>
          <span className="font-mono text-xs text-[#e2d5de]/70 font-semibold">{totalEvents} Total Events</span>
        </div>

        <div className="flex flex-col sm:flex-row items-center gap-4 h-[220px]">
          <div className="w-full sm:w-1/2 h-full">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={severityDistribution}
                  cx="50%"
                  cy="50%"
                  innerRadius={45}
                  outerRadius={75}
                  paddingAngle={4}
                  dataKey="value"
                >
                  {severityDistribution.map((entry) => (
                    <Cell key={`cell-${entry.name}`} fill={entry.color} stroke="#1e0a19" strokeWidth={2} />
                  ))}
                </Pie>
                <RechartsTooltip
                  content={({ active, payload }) => {
                    if (active && payload && payload.length) {
                      const data = payload[0] as unknown as SeverityTooltipPayload
                      const pct = Math.round((data.value / totalEvents) * 100)
                      return (
                        <div
                          className="rounded-lg p-2.5 text-xs font-mono shadow-xl backdrop-blur-md"
                          style={{ backgroundColor: '#250b1f', border: '1px solid #4a1f40', color: '#ffffff' }}
                        >
                          <p className="font-bold text-white">{data.name}</p>
                          <p style={{ color: data.payload.color }} className="mt-0.5">
                            {data.value} events ({pct}%)
                          </p>
                        </div>
                      )
                    }
                    return null
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>

          {/* Legend and breakdown */}
          <div className="w-full sm:w-1/2 flex flex-col justify-center gap-2.5">
            {severityDistribution.map((item) => (
              <div key={item.name} className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-2">
                  <span className="h-2.5 w-2.5 rounded-full shadow-sm" style={{ backgroundColor: item.color }} />
                  <span className="text-[#e2d5de] font-medium">{item.name}</span>
                </div>
                <div className="flex items-center gap-2 font-mono">
                  <span className="font-bold text-white">{item.value}</span>
                  <span className="text-[#e2d5de]/50">({Math.round((item.value / totalEvents) * 100)}%)</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </TiltCard>

      {/* 2. MITRE ATT&CK Techniques Bar Chart */}
      <TiltCard
        className="flex flex-col rounded-2xl p-5 shadow-2xl transition-all backdrop-blur-xl hover:border-[#dba136]/60"
        glareColor="rgba(219, 161, 54, 0.15)"
        maxRotation={4}
        style={{
          backgroundColor: 'rgba(28, 10, 25, 0.92)',
          border: '1px solid #4a1f40',
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.45), inset 0 1px 0 rgba(255, 255, 255, 0.08)',
        }}
      >
        <div className="flex items-center justify-between mb-3 border-b border-[#3d1433] pb-2.5">
          <p className="text-xs uppercase tracking-widest font-bold" style={{ color: '#dba136' }}>
            MITRE ATT&CK Matrix Alignment
          </p>
          <span className="font-mono text-xs text-[#e2d5de]/70 font-semibold">{mitreTechniques.length} Tactics</span>
        </div>

        <div className="h-[220px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={mitreTechniques}
              layout="vertical"
              margin={{ top: 5, right: 20, left: 10, bottom: 5 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#3d1433" horizontal={false} />
              <XAxis
                type="number"
                allowDecimals={false}
                tick={{ fill: '#dba136', fontSize: 10, fontFamily: 'Roboto Mono' }}
              />
              <YAxis
                type="category"
                dataKey="technique"
                tick={{ fill: '#ffffff', fontSize: 11, fontFamily: 'Roboto Mono' }}
                width={75}
              />
              <RechartsTooltip
                content={({ active, payload }) => {
                  if (active && payload && payload.length) {
                    const data = payload[0] as unknown as MitreTooltipPayload
                    const item = data.payload
                    return (
                      <div
                        className="rounded-lg p-2.5 text-xs shadow-xl backdrop-blur-md"
                        style={{ backgroundColor: '#250b1f', border: '1px solid #4a1f40' }}
                      >
                        <p className="font-mono font-bold text-white">{item.technique}</p>
                        <p className="text-[#dba136] font-medium mt-0.5">{item.name}</p>
                        <p className="text-[#e2d5de]/70 text-[11px] mt-1">Tactic: {item.tactic}</p>
                        <p className="font-mono text-[#ff6b35] mt-0.5 font-bold">{item.count} detections</p>
                      </div>
                    )
                  }
                  return null
                }}
              />
              <Bar dataKey="count" fill="#dba136" radius={[0, 4, 4, 0]}>
                {mitreTechniques.map((entry, idx) => (
                  <Cell
                    key={`mitre-${idx}`}
                    fill={
                      entry.severity === 'critical'
                        ? '#ef4444'
                        : entry.severity === 'high'
                        ? '#e04c1e'
                        : entry.severity === 'medium'
                        ? '#f59e0b'
                        : '#38bdf8'
                    }
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </TiltCard>
    </div>
  )
}
