import type { StageMetric } from '../../imports/analytics'
import { LAYER_LABEL } from '../../imports/api'
import TiltCard from '../3d/TiltCard'

interface AttackKillChainFunnelProps {
  stages: StageMetric[]
}

export default function AttackKillChainFunnel({ stages }: AttackKillChainFunnelProps) {
  return (
    <TiltCard
      className="flex flex-col gap-3 rounded-2xl p-5 shadow-2xl transition-all backdrop-blur-xl hover:border-[#e04c1e]/60"
      glareColor="rgba(224, 76, 30, 0.15)"
      maxRotation={4}
      style={{
        backgroundColor: 'rgba(28, 10, 25, 0.92)',
        border: '1px solid #4a1f40',
        boxShadow: '0 8px 32px rgba(0, 0, 0, 0.45), inset 0 1px 0 rgba(255, 255, 255, 0.08)',
      }}
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#3d1433] pb-3">
        <div className="flex items-center gap-2">
          <span className="h-2.5 w-2.5 rounded-full bg-[#e04c1e] animate-ping" />
          <h2 className="text-sm font-bold uppercase tracking-widest" style={{ color: '#dba136' }}>
            Multi-Layer Attack Kill Chain
          </h2>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span className="text-[#e2d5de]/70">Penetration Depth:</span>
          <span className="font-mono font-bold px-2.5 py-0.5 rounded-full text-[#ef4444] bg-[#3a0815] border border-[#ef4444]/40 shadow-sm">
            100% (4 / 4 Layers Hit)
          </span>
        </div>
      </div>

      {/* Stepper Pipeline */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3 pt-1">
        {stages.map((stage, idx) => {
          const isHit = stage.status === 'hit'
          const isFinal = idx === stages.length - 1

          return (
            <div
              key={stage.id}
              className="relative flex flex-col justify-between rounded-xl p-4 transition-all duration-200 hover:-translate-y-1 hover:shadow-lg"
              style={{
                background: isHit
                  ? isFinal
                    ? 'linear-gradient(145deg, rgba(65, 10, 25, 0.8) 0%, rgba(30, 8, 20, 0.9) 100%)'
                    : 'linear-gradient(145deg, rgba(50, 16, 22, 0.8) 0%, rgba(28, 8, 24, 0.9) 100%)'
                  : 'rgba(18, 5, 15, 0.7)',
                border: isHit
                  ? isFinal
                    ? '1px solid rgba(239, 68, 68, 0.6)'
                    : '1px solid rgba(224, 76, 30, 0.5)'
                  : '1px solid #3d1433',
              }}
            >
              {/* Header: Stage and Badge */}
              <div>
                <div className="flex items-center justify-between gap-1 mb-2">
                  <span className="text-xs font-bold uppercase tracking-wider text-white">
                    {stage.name}
                  </span>
                  <span
                    className="text-[10px] font-mono font-bold px-2 py-0.5 rounded-full uppercase"
                    style={{
                      backgroundColor: isHit
                        ? isFinal
                          ? 'rgba(239, 68, 68, 0.2)'
                          : 'rgba(224, 76, 30, 0.2)'
                        : 'rgba(16, 185, 129, 0.2)',
                      color: isHit ? (isFinal ? '#ef4444' : '#ff6b35') : '#10b981',
                      border: isHit
                        ? isFinal
                          ? '1px solid rgba(239, 68, 68, 0.5)'
                          : '1px solid rgba(224, 76, 30, 0.5)'
                        : '1px solid rgba(16, 185, 129, 0.5)',
                    }}
                  >
                    {isHit ? (isFinal ? 'CRITICAL BREACH' : 'HIT') : 'CLEARED'}
                  </span>
                </div>

                <p className="text-xs line-clamp-2 leading-relaxed text-[#e2d5de]/70 font-['Figtree',sans-serif]">
                  {stage.description}
                </p>
              </div>

              {/* Footer info: Layer & Events */}
              <div className="mt-4 pt-2.5 border-t border-[#3d1433]/80 flex items-center justify-between text-xs">
                <span className="font-mono text-[11px] px-2 py-0.5 rounded bg-[#2a0e24] text-[#dba136] border border-[#3d1433]">
                  {LAYER_LABEL[stage.layer]}
                </span>
                <span className="font-mono text-[11px] text-[#ff6b35] font-semibold">
                  {stage.eventCount} {stage.eventCount === 1 ? 'event' : 'events'}
                </span>
              </div>
            </div>
          )
        })}
      </div>
    </TiltCard>
  )
}
