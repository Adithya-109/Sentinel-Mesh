import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts'
import type { DefenseComparisonItem } from '../../imports/analytics'
import TiltCard from '../3d/TiltCard'

interface DefenseBenchmarkChartProps {
  defenseComparisons: DefenseComparisonItem[]
}

export default function DefenseBenchmarkChart({ defenseComparisons }: DefenseBenchmarkChartProps) {
  // Normalize data for chart display
  const chartData = defenseComparisons
    .filter((d) => d.condition !== 'gate' || d.energyPerHour !== null)
    .map((d) => ({
      condition: d.condition,
      name: d.label.replace('Attack + ', '').replace(' (baseline)', ''),
      energy: d.energyPerHour ?? 310,
      days: d.projectedDays ?? 39.5,
      isGate: d.condition === 'gate',
    }))

  return (
    <TiltCard
      className="flex flex-col rounded-2xl p-5 shadow-2xl transition-all backdrop-blur-xl hover:border-[#38bdf8]/60"
      glareColor="rgba(224, 76, 30, 0.12)"
      maxRotation={3}
      style={{
        backgroundColor: 'rgba(28, 10, 25, 0.92)',
        border: '1px solid #4a1f40',
        boxShadow: '0 8px 32px rgba(0, 0, 0, 0.45), inset 0 1px 0 rgba(255, 255, 255, 0.08)',
      }}
    >
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3 border-b border-[#3d1433] pb-3">
        <div>
          <h3 className="text-xs uppercase tracking-widest font-bold" style={{ color: '#dba136' }}>
            Defense Strategy Benchmark: Energy vs. Autonomy
          </h3>
          <p className="text-xs text-[#e2d5de]/70 mt-0.5 font-['Figtree',sans-serif]">
            Evaluating post-quantum defense layers against battery exhaustion attacks
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-[#10b981] animate-pulse" />
          <span className="font-mono text-[11px] font-bold px-2.5 py-0.5 rounded-full bg-[#10b981]/20 text-[#10b981] border border-[#10b981]/40 shadow-sm">
            EnergyGate Active
          </span>
        </div>
      </div>

      <div className="h-[250px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData} margin={{ top: 10, right: 10, left: -10, bottom: 20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#3d1433" vertical={false} />
            <XAxis
              dataKey="name"
              tick={{ fill: '#e2d5de', fontSize: 10, fontFamily: 'Manrope' }}
              interval={0}
              angle={-10}
              textAnchor="end"
            />
            <YAxis
              yAxisId="left"
              tick={{ fill: '#e04c1e', fontSize: 10, fontFamily: 'Roboto Mono' }}
              label={{ value: 'J / hr', angle: -90, position: 'insideLeft', fill: '#e04c1e', fontSize: 10 }}
            />
            <YAxis
              yAxisId="right"
              orientation="right"
              tick={{ fill: '#38bdf8', fontSize: 10, fontFamily: 'Roboto Mono' }}
              label={{ value: 'Days Autonomy', angle: 90, position: 'insideRight', fill: '#38bdf8', fontSize: 10 }}
            />
            <Tooltip
              content={({ active, payload, label }) => {
                if (active && payload && payload.length) {
                  return (
                    <div
                      className="rounded-lg p-3 text-xs font-mono shadow-2xl backdrop-blur-md"
                      style={{ backgroundColor: '#250b1f', border: '1px solid #4a1f40' }}
                    >
                      <p className="font-bold text-white mb-1.5">{label}</p>
                      <p className="text-[#e04c1e] font-semibold">Energy Drain: {payload[0]?.value} J/hr</p>
                      <p className="text-[#38bdf8] font-semibold mt-0.5">Sensor Lifetime: {payload[1]?.value} days</p>
                    </div>
                  )
                }
                return null
              }}
            />
            <Legend
              verticalAlign="top"
              wrapperStyle={{ fontSize: 11, paddingBottom: 12 }}
              formatter={(value) => (
                <span style={{ color: value === 'Energy Drain (J/hr)' ? '#e04c1e' : '#38bdf8' }} className="font-semibold">
                  {value}
                </span>
              )}
            />
            <Bar yAxisId="left" dataKey="energy" name="Energy Drain (J/hr)" fill="#e04c1e" radius={[4, 4, 0, 0]} />
            <Bar yAxisId="right" dataKey="days" name="Projected Days" fill="#38bdf8" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </TiltCard>
  )
}
