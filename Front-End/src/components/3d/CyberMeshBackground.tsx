import { useEffect, useRef } from 'react'

interface Node {
  x: number
  y: number
  vx: number
  vy: number
  radius: number
  baseAlpha: number
  pulseSpeed: number
  pulsePhase: number
  color: string
}

interface Pulse {
  fromNode: number
  toNode: number
  progress: number
  speed: number
  color: string
}

export default function CyberMeshBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    let animationFrameId: number
    let width = 0
    let height = 0
    let mouse = { x: -1000, y: -1000, active: false }

    const COLORS = ['#e04c1e', '#f59e0b', '#dba136', '#ff8c5a', '#ffffff']

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
    }

    handleResize()
    window.addEventListener('resize', handleResize)

    // Generate Mesh Nodes
    const nodeCount = Math.min(Math.floor((width * height) / 14000) + 25, 60)
    const nodes: Node[] = []
    for (let i = 0; i < nodeCount; i++) {
      nodes.push({
        x: Math.random() * width,
        y: Math.random() * height,
        vx: (Math.random() - 0.5) * 0.45,
        vy: (Math.random() - 0.5) * 0.45,
        radius: Math.random() * 2 + 1.2,
        baseAlpha: Math.random() * 0.5 + 0.3,
        pulseSpeed: Math.random() * 0.03 + 0.015,
        pulsePhase: Math.random() * Math.PI * 2,
        color: COLORS[Math.floor(Math.random() * COLORS.length)],
      })
    }

    // Packet Pulses traveling along links
    const pulses: Pulse[] = []
    const spawnPulse = () => {
      if (pulses.length > 18 || nodes.length < 2) return
      const fromNode = Math.floor(Math.random() * nodes.length)
      // Find a near neighbor
      let nearest = -1
      let minDist = 140
      for (let j = 0; j < nodes.length; j++) {
        if (j === fromNode) continue
        const dx = nodes[fromNode].x - nodes[j].x
        const dy = nodes[fromNode].y - nodes[j].y
        const d = Math.sqrt(dx * dx + dy * dy)
        if (d < minDist) {
          minDist = d
          nearest = j
        }
      }
      if (nearest !== -1) {
        pulses.push({
          fromNode,
          toNode: nearest,
          progress: 0,
          speed: Math.random() * 0.015 + 0.008,
          color: Math.random() > 0.4 ? '#f59e0b' : '#e04c1e',
        })
      }
    }

    const pulseInterval = setInterval(spawnPulse, 350)

    const handleMouseMove = (e: MouseEvent) => {
      const rect = canvas.getBoundingClientRect()
      mouse.x = e.clientX - rect.left
      mouse.y = e.clientY - rect.top
      mouse.active = true
    }

    const handleMouseLeave = () => {
      mouse.active = false
      mouse.x = -1000
      mouse.y = -1000
    }

    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('mouseleave', handleMouseLeave)

    // Animation Loop
    let time = 0
    const render = () => {
      time += 0.015
      ctx.clearRect(0, 0, width, height)

      // Draw subtle ambient grid wave in background
      ctx.strokeStyle = 'rgba(219, 161, 54, 0.025)'
      ctx.lineWidth = 1
      const gridSize = 48
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

      // Update and connect nodes
      const maxConnectDist = 135

      // Draw connection lines
      for (let i = 0; i < nodes.length; i++) {
        const n1 = nodes[i]

        for (let j = i + 1; j < nodes.length; j++) {
          const n2 = nodes[j]
          const dx = n1.x - n2.x
          const dy = n1.y - n2.y
          const dist = Math.sqrt(dx * dx + dy * dy)

          if (dist < maxConnectDist) {
            const alpha = (1 - dist / maxConnectDist) * 0.22
            ctx.strokeStyle = `rgba(245, 158, 11, ${alpha})`
            ctx.lineWidth = 0.85
            ctx.beginPath()
            ctx.moveTo(n1.x, n1.y)
            ctx.lineTo(n2.x, n2.y)
            ctx.stroke()
          }
        }

        // Connect to mouse if active & close
        if (mouse.active) {
          const mdx = n1.x - mouse.x
          const mdy = n1.y - mouse.y
          const mdist = Math.sqrt(mdx * mdx + mdy * mdy)
          if (mdist < 180) {
            const mAlpha = (1 - mdist / 180) * 0.45
            ctx.strokeStyle = `rgba(224, 76, 30, ${mAlpha})`
            ctx.lineWidth = 1.2
            ctx.beginPath()
            ctx.moveTo(n1.x, n1.y)
            ctx.lineTo(mouse.x, mouse.y)
            ctx.stroke()

            // Subtle elastic attraction toward mouse
            const force = (180 - mdist) * 0.0003
            n1.vx -= mdx * force
            n1.vy -= mdy * force
          }
        }
      }

      // Render traveling packet pulses
      for (let k = pulses.length - 1; k >= 0; k--) {
        const p = pulses[k]
        p.progress += p.speed
        if (p.progress >= 1) {
          pulses.splice(k, 1)
          continue
        }

        const nA = nodes[p.fromNode]
        const nB = nodes[p.toNode]
        if (!nA || !nB) continue

        const px = nA.x + (nB.x - nA.x) * p.progress
        const py = nA.y + (nB.y - nA.y) * p.progress

        // Packet glow halo
        const grad = ctx.createRadialGradient(px, py, 0, px, py, 7)
        grad.addColorStop(0, p.color)
        grad.addColorStop(1, 'rgba(224, 76, 30, 0)')

        ctx.fillStyle = grad
        ctx.beginPath()
        ctx.arc(px, py, 7, 0, Math.PI * 2)
        ctx.fill()

        ctx.fillStyle = '#ffffff'
        ctx.beginPath()
        ctx.arc(px, py, 1.8, 0, Math.PI * 2)
        ctx.fill()
      }

      // Draw and update node positions
      for (let i = 0; i < nodes.length; i++) {
        const node = nodes[i]
        node.x += node.vx
        node.y += node.vy

        // Dampen velocity
        node.vx *= 0.99
        node.vy *= 0.99

        // Keep min drifting speed
        if (Math.abs(node.vx) < 0.1) node.vx += (Math.random() - 0.5) * 0.05
        if (Math.abs(node.vy) < 0.1) node.vy += (Math.random() - 0.5) * 0.05

        // Bounce gently off boundaries
        if (node.x < 0) {
          node.x = 0
          node.vx = Math.abs(node.vx)
        } else if (node.x > width) {
          node.x = width
          node.vx = -Math.abs(node.vx)
        }
        if (node.y < 0) {
          node.y = 0
          node.vy = Math.abs(node.vy)
        } else if (node.y > height) {
          node.y = height
          node.vy = -Math.abs(node.vy)
        }

        // Pulse alpha
        node.pulsePhase += node.pulseSpeed
        const alpha = node.baseAlpha + Math.sin(node.pulsePhase) * 0.25

        // Draw node
        ctx.fillStyle = node.color
        ctx.globalAlpha = Math.max(0.15, Math.min(1, alpha))
        ctx.beginPath()
        ctx.arc(node.x, node.y, node.radius, 0, Math.PI * 2)
        ctx.fill()

        // Occasional outer glow for higher radius nodes
        if (node.radius > 2.2) {
          ctx.strokeStyle = node.color
          ctx.lineWidth = 0.5
          ctx.globalAlpha = alpha * 0.4
          ctx.beginPath()
          ctx.arc(node.x, node.y, node.radius * 2.5, 0, Math.PI * 2)
          ctx.stroke()
        }
      }

      // Draw cursor interactive energy vortex
      if (mouse.active) {
        ctx.globalAlpha = 0.35
        ctx.strokeStyle = '#e04c1e'
        ctx.lineWidth = 1
        ctx.beginPath()
        ctx.arc(mouse.x, mouse.y, 16 + Math.sin(time * 4) * 4, 0, Math.PI * 2)
        ctx.stroke()

        ctx.globalAlpha = 0.15
        ctx.beginPath()
        ctx.arc(mouse.x, mouse.y, 32 + Math.cos(time * 3) * 6, 0, Math.PI * 2)
        ctx.stroke()
      }

      ctx.globalAlpha = 1.0
      animationFrameId = requestAnimationFrame(render)
    }

    render()

    return () => {
      cancelAnimationFrame(animationFrameId)
      clearInterval(pulseInterval)
      window.removeEventListener('resize', handleResize)
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseleave', handleMouseLeave)
    }
  }, [])

  return (
    <canvas
      ref={canvasRef}
      aria-hidden
      className="absolute inset-0 pointer-events-none z-0 overflow-hidden opacity-85"
    />
  )
}
