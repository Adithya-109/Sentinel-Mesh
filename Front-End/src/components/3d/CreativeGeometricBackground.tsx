import { useEffect, useRef, useState, useCallback } from 'react'

export type BackgroundShapeMode = 'hexagons' | 'quantum' | 'matrix'

interface Shape {
  id: number
  x: number
  y: number
  baseX: number
  baseY: number
  vx: number
  vy: number
  size: number // varying sizes from 8px to 120px
  type: 'hexagon' | 'diamond' | 'radar_ring' | 'cube' | 'crosshair' | 'circle_node'
  rotation: number
  rotationSpeed: number
  depth: number // 0.2 (far) to 1.0 (near)
  color: string
  baseAlpha: number
  pulsePhase: number
  pulseSpeed: number
  hoverScale: number
}

interface Ripple {
  x: number
  y: number
  radius: number
  maxRadius: number
  alpha: number
  speed: number
  color: string
}

interface CreativeGeometricBackgroundProps {
  className?: string
  defaultFocusMode?: boolean
}

export default function CreativeGeometricBackground({
  className = '',
  defaultFocusMode = false,
}: CreativeGeometricBackgroundProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [focusMode, setFocusMode] = useState(defaultFocusMode)
  const [intensity, setIntensity] = useState<'subtle' | 'balanced' | 'vibrant'>('balanced')
  const [showControls, setShowControls] = useState(false)
  const [shockwaveCount, setShockwaveCount] = useState(0)

  // Mutable refs for high-performance 60fps canvas loop
  const mouseRef = useRef({ x: -2000, y: -2000, targetX: -2000, targetY: -2000, active: false })
  const shapesRef = useRef<Shape[]>([])
  const ripplesRef = useRef<Ripple[]>([])
  const configRef = useRef({ focusMode, intensity })

  // Keep configRef synchronized with React state
  useEffect(() => {
    configRef.current = { focusMode, intensity }
  }, [focusMode, intensity])

  const triggerShockwave = useCallback((x?: number, y?: number) => {
    const canvas = canvasRef.current
    if (!canvas) return
    const rect = canvas.getBoundingClientRect()
    const spawnX = x ?? rect.width / 2
    const spawnY = y ?? rect.height / 2

    const colors = ['#e04c1e', '#dba136', '#38bdf8', '#ff6b35']
    const color = colors[Math.floor(Math.random() * colors.length)]

    ripplesRef.current.push({
      x: spawnX,
      y: spawnY,
      radius: 5,
      maxRadius: Math.max(rect.width, rect.height) * 0.75,
      alpha: 0.85,
      speed: 4.5,
      color,
    })
    setShockwaveCount((c) => c + 1)
  }, [])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    let animationId: number
    let width = 0
    let height = 0

    const handleResize = () => {
      const parent = canvas.parentElement
      if (!parent) return
      const dpr = Math.min(window.devicePixelRatio || 1, 2)
      width = parent.clientWidth
      height = parent.clientHeight

      canvas.width = width * dpr
      canvas.height = height * dpr
      canvas.style.width = `${width}px`
      canvas.style.height = `${height}px`
      ctx.scale(dpr, dpr)

      initShapes()
    }

    const initShapes = () => {
      shapesRef.current = []
      const densityMap = { subtle: 24, balanced: 40, vibrant: 62 }
      const count = densityMap[configRef.current.intensity]

      const types: Shape['type'][] = [
        'hexagon',
        'hexagon',
        'diamond',
        'radar_ring',
        'cube',
        'crosshair',
        'circle_node',
      ]

      const palette = [
        '#e04c1e', // Terracotta
        '#dba136', // Golden amber
        '#f59e0b', // Amber
        '#38bdf8', // Cyan
        '#ff6b35', // Ember
        '#10b981', // Emerald
      ]

      for (let i = 0; i < count; i++) {
        const x = Math.random() * width
        const y = Math.random() * height
        const depth = 0.2 + Math.random() * 0.8 // 3D depth layer

        // Varying sizes: micro (8px), small (18px), medium (32px), large (70px), extra-large (110px)
        const sizeCategory = Math.random()
        let size = 12
        if (sizeCategory > 0.88) {
          size = 65 + Math.random() * 45 // Large hero shape
        } else if (sizeCategory > 0.6) {
          size = 30 + Math.random() * 25 // Medium shape
        } else if (sizeCategory > 0.25) {
          size = 16 + Math.random() * 12 // Small shape
        } else {
          size = 8 + Math.random() * 6 // Micro crosshair / node
        }

        shapesRef.current.push({
          id: i,
          x,
          y,
          baseX: x,
          baseY: y,
          vx: (Math.random() - 0.5) * 0.4 * depth,
          vy: (Math.random() - 0.5) * 0.4 * depth,
          size,
          type: types[Math.floor(Math.random() * types.length)],
          rotation: Math.random() * Math.PI * 2,
          rotationSpeed: (Math.random() - 0.5) * 0.015,
          depth,
          color: palette[Math.floor(Math.random() * palette.length)],
          baseAlpha: 0.12 + Math.random() * 0.3,
          pulsePhase: Math.random() * Math.PI * 2,
          pulseSpeed: 0.015 + Math.random() * 0.02,
          hoverScale: 1,
        })
      }
    }

    handleResize()
    window.addEventListener('resize', handleResize)

    // Mouse tracking
    const handleMouseMove = (e: MouseEvent) => {
      const rect = canvas.getBoundingClientRect()
      mouseRef.current.targetX = e.clientX - rect.left
      mouseRef.current.targetY = e.clientY - rect.top
      mouseRef.current.active = true
    }

    const handleMouseLeave = () => {
      mouseRef.current.active = false
      mouseRef.current.targetX = -2000
      mouseRef.current.targetY = -2000
    }

    const handleClick = (e: MouseEvent) => {
      const rect = canvas.getBoundingClientRect()
      const clickX = e.clientX - rect.left
      const clickY = e.clientY - rect.top
      triggerShockwave(clickX, clickY)
    }

    const parent = canvas.parentElement
    if (parent) {
      parent.addEventListener('mousemove', handleMouseMove)
      parent.addEventListener('mouseleave', handleMouseLeave)
      parent.addEventListener('click', handleClick)
    }

    // DRAWING HELPER FUNCTIONS

    const drawHexagon = (
      context: CanvasRenderingContext2D,
      cx: number,
      cy: number,
      radius: number,
      rotation: number
    ) => {
      context.beginPath()
      for (let i = 0; i < 6; i++) {
        const angle = rotation + (i * Math.PI) / 3
        const hx = cx + radius * Math.cos(angle)
        const hy = cy + radius * Math.sin(angle)
        if (i === 0) context.moveTo(hx, hy)
        else context.lineTo(hx, hy)
      }
      context.closePath()
    }

    const drawIsometricCube = (
      context: CanvasRenderingContext2D,
      cx: number,
      cy: number,
      size: number,
      rotation: number
    ) => {
      const r = size * 0.85
      context.save()
      context.translate(cx, cy)
      context.rotate(rotation)

      // Hexagonal bounding
      drawHexagon(context, 0, 0, r, 0)
      context.stroke()

      // Center Y-split for 3D isometric cube
      context.beginPath()
      context.moveTo(0, 0)
      context.lineTo(0, r)
      context.moveTo(0, 0)
      context.lineTo(-r * Math.cos(Math.PI / 6), -r * Math.sin(Math.PI / 6))
      context.moveTo(0, 0)
      context.lineTo(r * Math.cos(Math.PI / 6), -r * Math.sin(Math.PI / 6))
      context.stroke()
      context.restore()
    }

    const drawRadarRing = (
      context: CanvasRenderingContext2D,
      cx: number,
      cy: number,
      size: number,
      rotation: number
    ) => {
      context.save()
      context.translate(cx, cy)
      context.rotate(rotation)

      // Outer dashed circle
      context.beginPath()
      context.setLineDash([4, 6])
      context.arc(0, 0, size, 0, Math.PI * 2)
      context.stroke()
      context.setLineDash([])

      // Inner solid circle
      context.beginPath()
      context.arc(0, 0, size * 0.5, 0, Math.PI * 2)
      context.stroke()

      // 4 Tech Tick Marks
      context.beginPath()
      context.moveTo(-size - 4, 0)
      context.lineTo(-size + 4, 0)
      context.moveTo(size - 4, 0)
      context.lineTo(size + 4, 0)
      context.moveTo(0, -size - 4)
      context.lineTo(0, -size + 4)
      context.moveTo(0, size - 4)
      context.lineTo(0, size + 4)
      context.stroke()

      context.restore()
    }

    const drawDiamond = (
      context: CanvasRenderingContext2D,
      cx: number,
      cy: number,
      size: number,
      rotation: number
    ) => {
      context.save()
      context.translate(cx, cy)
      context.rotate(rotation)
      context.beginPath()
      context.moveTo(0, -size)
      context.lineTo(size * 0.7, 0)
      context.lineTo(0, size)
      context.lineTo(-size * 0.7, 0)
      context.closePath()
      context.stroke()

      // Inscribed cross
      context.beginPath()
      context.moveTo(0, -size * 0.5)
      context.lineTo(0, size * 0.5)
      context.moveTo(-size * 0.35, 0)
      context.lineTo(size * 0.35, 0)
      context.stroke()
      context.restore()
    }

    const drawCrosshair = (
      context: CanvasRenderingContext2D,
      cx: number,
      cy: number,
      size: number
    ) => {
      context.beginPath()
      context.moveTo(cx - size, cy)
      context.lineTo(cx + size, cy)
      context.moveTo(cx, cy - size)
      context.lineTo(cx + size, cy)
      context.stroke()

      context.beginPath()
      context.arc(cx, cy, 2, 0, Math.PI * 2)
      context.fill()
    }

    // MAIN ANIMATION LOOP
    const render = () => {
      // Smooth mouse lerping
      mouseRef.current.x += (mouseRef.current.targetX - mouseRef.current.x) * 0.1
      mouseRef.current.y += (mouseRef.current.targetY - mouseRef.current.y) * 0.1

      // Clear canvas
      ctx.clearRect(0, 0, width, height)

      const isFocus = configRef.current.focusMode
      const globalOpacityMultiplier = isFocus ? 0.22 : 1.0

      // 1. Draw Subtle Background Coordinate Matrix Grid (for easy viewing & structure)
      ctx.save()
      ctx.strokeStyle = 'rgba(219, 161, 54, 0.035)'
      ctx.lineWidth = 1
      const gridSize = 64
      for (let x = 0; x < width; x += gridSize) {
        ctx.beginPath()
        ctx.moveTo(x, 0)
        ctx.lineTo(x, height)
        ctx.stroke()
      }
      for (let y = 0; y < height; y += gridSize) {
        ctx.beginPath()
        ctx.moveTo(0, y)
        ctx.lineTo(width, y)
        ctx.stroke()
      }
      ctx.restore()

      // 2. Animate and Draw Geometric Shapes
      const shapes = shapesRef.current
      for (let i = 0; i < shapes.length; i++) {
        const s = shapes[i]

        // Drift physics
        s.x += s.vx
        s.y += s.vy
        s.rotation += s.rotationSpeed
        s.pulsePhase += s.pulseSpeed

        // Wrap around viewport boundaries gracefully
        if (s.x < -s.size * 2) s.x = width + s.size * 2
        if (s.x > width + s.size * 2) s.x = -s.size * 2
        if (s.y < -s.size * 2) s.y = height + s.size * 2
        if (s.y > height + s.size * 2) s.y = -s.size * 2

        // Mouse Proximity & Parallax Reaction
        const dx = mouseRef.current.x - s.x
        const dy = mouseRef.current.y - s.y
        const dist = Math.sqrt(dx * dx + dy * dy)
        const isNearMouse = dist < 140

        // Smooth scale on hover
        const targetScale = isNearMouse ? 1.35 : 1
        s.hoverScale += (targetScale - s.hoverScale) * 0.1

        // Parallax offset based on depth
        const parallaxX = (mouseRef.current.x - width / 2) * 0.03 * s.depth
        const parallaxY = (mouseRef.current.y - height / 2) * 0.03 * s.depth
        const drawX = s.x + parallaxX
        const drawY = s.y + parallaxY

        // Alpha modulation
        const pulse = 0.5 + 0.5 * Math.sin(s.pulsePhase)
        const alpha = Math.min(
          1,
          (s.baseAlpha + (isNearMouse ? 0.35 : 0) + pulse * 0.15) * globalOpacityMultiplier
        )

        ctx.save()
        ctx.strokeStyle = s.color
        ctx.fillStyle = s.color
        ctx.lineWidth = isNearMouse ? 1.8 : 1.2
        ctx.globalAlpha = alpha

        // Render based on shape type
        const renderSize = s.size * s.hoverScale

        if (s.type === 'hexagon') {
          drawHexagon(ctx, drawX, drawY, renderSize, s.rotation)
          ctx.stroke()

          // Nested concentric hexagon for medium/large shapes
          if (renderSize > 25) {
            drawHexagon(ctx, drawX, drawY, renderSize * 0.5, -s.rotation * 1.5)
            ctx.stroke()
          }
          if (renderSize > 60) {
            ctx.beginPath()
            ctx.arc(drawX, drawY, 3, 0, Math.PI * 2)
            ctx.fill()
          }
        } else if (s.type === 'diamond') {
          drawDiamond(ctx, drawX, drawY, renderSize, s.rotation)
        } else if (s.type === 'radar_ring') {
          drawRadarRing(ctx, drawX, drawY, renderSize, s.rotation)
        } else if (s.type === 'cube') {
          drawIsometricCube(ctx, drawX, drawY, renderSize, s.rotation)
        } else if (s.type === 'crosshair') {
          drawCrosshair(ctx, drawX, drawY, renderSize * 0.6)
        } else {
          // circle_node with glowing orbit
          ctx.beginPath()
          ctx.arc(drawX, drawY, renderSize * 0.4, 0, Math.PI * 2)
          ctx.stroke()
          ctx.beginPath()
          ctx.arc(drawX, drawY, 2, 0, Math.PI * 2)
          ctx.fill()
        }

        // Draw tether link to mouse if very close
        if (isNearMouse && mouseRef.current.active) {
          ctx.beginPath()
          ctx.moveTo(drawX, drawY)
          ctx.lineTo(mouseRef.current.x, mouseRef.current.y)
          ctx.strokeStyle = s.color
          ctx.globalAlpha = (1 - dist / 140) * 0.35 * globalOpacityMultiplier
          ctx.setLineDash([2, 4])
          ctx.stroke()
          ctx.setLineDash([])
        }

        ctx.restore()
      }

      // 3. Render Click Shockwaves / Expanding Geometric Ripples
      const ripples = ripplesRef.current
      for (let i = ripples.length - 1; i >= 0; i--) {
        const r = ripples[i]
        r.radius += r.speed
        r.alpha -= 0.015

        if (r.alpha <= 0 || r.radius >= r.maxRadius) {
          ripples.splice(i, 1)
          continue
        }

        ctx.save()
        ctx.strokeStyle = r.color
        ctx.lineWidth = 1.8
        ctx.globalAlpha = r.alpha * globalOpacityMultiplier

        // Expanding outer concentric hexagon
        drawHexagon(ctx, r.x, r.y, r.radius, r.radius * 0.02)
        ctx.stroke()

        // Expanding inner ring
        ctx.beginPath()
        ctx.setLineDash([6, 8])
        ctx.arc(r.x, r.y, r.radius * 0.6, 0, Math.PI * 2)
        ctx.stroke()
        ctx.setLineDash([])

        ctx.restore()
      }

      animationId = requestAnimationFrame(render)
    }

    render()

    return () => {
      window.removeEventListener('resize', handleResize)
      if (parent) {
        parent.removeEventListener('mousemove', handleMouseMove)
        parent.removeEventListener('mouseleave', handleMouseLeave)
        parent.removeEventListener('click', handleClick)
      }
      cancelAnimationFrame(animationId)
    }
  }, [triggerShockwave])

  return (
    <div className={`absolute inset-0 pointer-events-none overflow-hidden ${className}`}>
      {/* Interactive HTML5 Canvas */}
      <canvas ref={canvasRef} className="absolute inset-0 block w-full h-full pointer-events-auto" />

      {/* Floating Interactive HUD Controls Pill (Bottom-Right) */}
      <div className="pointer-events-auto absolute bottom-4 right-5 z-30 flex items-center gap-2">
        {/* Expanded Controls Drawer */}
        {showControls && (
          <div
            className="flex items-center gap-3 px-4 py-2 rounded-full text-xs font-mono shadow-2xl backdrop-blur-xl animate-in fade-in slide-in-from-bottom-2 duration-200"
            style={{
              backgroundColor: 'rgba(25, 8, 22, 0.95)',
              border: '1px solid #3d1433',
              color: '#ffffff',
            }}
          >
            {/* Focus Mode Switch */}
            <button
              onClick={() => setFocusMode(!focusMode)}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-full transition-all cursor-pointer"
              style={{
                backgroundColor: focusMode ? '#dba136' : 'rgba(255, 255, 255, 0.08)',
                color: focusMode ? '#10040d' : '#e2d5de',
                fontWeight: focusMode ? 'bold' : 'normal',
              }}
              title="Toggle High-Contrast Data Focus Mode"
            >
              <span>{focusMode ? '👓 Focus: ON' : '👓 Focus: OFF'}</span>
            </button>

            {/* Intensity Toggle */}
            <div className="flex items-center gap-1">
              <span className="text-[#e2d5de]/60 text-[10px] uppercase">Density:</span>
              {(['subtle', 'balanced', 'vibrant'] as const).map((lvl) => (
                <button
                  key={lvl}
                  onClick={() => setIntensity(lvl)}
                  className="px-2 py-0.5 rounded text-[10px] uppercase font-bold transition-all cursor-pointer"
                  style={{
                    backgroundColor: intensity === lvl ? '#e04c1e' : 'transparent',
                    color: intensity === lvl ? '#ffffff' : '#e2d5de',
                  }}
                >
                  {lvl[0].toUpperCase()}
                </button>
              ))}
            </div>

            {/* Pulse Ripple Trigger */}
            <button
              onClick={() => triggerShockwave()}
              className="px-2.5 py-1 rounded-full bg-[#e04c1e]/20 text-[#ff6b35] hover:bg-[#e04c1e] hover:text-white border border-[#e04c1e]/40 transition-all font-semibold cursor-pointer"
              title="Emit shockwave ripple across background shapes"
            >
              ⚡ Pulse
            </button>
          </div>
        )}

        {/* HUD Toggle Pill */}
        <button
          onClick={() => setShowControls(!showControls)}
          className="flex items-center gap-2 px-3.5 py-2 rounded-full text-xs font-mono font-semibold transition-all shadow-xl hover:scale-105 active:scale-95 cursor-pointer backdrop-blur-xl"
          style={{
            backgroundColor: showControls ? '#e04c1e' : 'rgba(30, 10, 25, 0.9)',
            color: '#ffffff',
            border: '1px solid #3d1433',
            boxShadow: showControls ? '0 4px 15px rgba(224, 76, 30, 0.4)' : 'none',
          }}
          title="Interactive Background Controls"
        >
          <span className="h-2 w-2 rounded-full bg-[#dba136] animate-pulse" />
          <span>Interactive Shapes</span>
          <span className="text-[10px] text-[#e2d5de]/70">{showControls ? '✕' : '⚙'}</span>
        </button>
      </div>

      {/* Helper text on initial load */}
      {shockwaveCount === 0 && (
        <div
          className="pointer-events-none absolute bottom-4 left-6 text-[11px] font-mono text-[#e2d5de]/50 opacity-80 hidden md:block"
        >
          💡 Tip: Click anywhere to emit geometric shockwaves, or hover over shapes to interact
        </div>
      )}
    </div>
  )
}
