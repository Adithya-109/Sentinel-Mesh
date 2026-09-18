import React, { useState, useRef, useCallback } from 'react'

interface TiltCardProps {
  children: React.ReactNode
  className?: string
  style?: React.CSSProperties
  maxTilt?: number
  maxRotation?: number
  perspective?: number
  glare?: boolean
  glareColor?: string
  scale?: number
}

export default function TiltCard({
  children,
  className = '',
  style = {},
  maxTilt = 10,
  maxRotation,
  perspective = 1000,
  glare = true,
  glareColor = 'rgba(255, 255, 255, 0.12)',
  scale = 1.02,
}: TiltCardProps) {
  const effectiveMaxTilt = maxRotation ?? maxTilt
  const cardRef = useRef<HTMLDivElement>(null)
  const [transform, setTransform] = useState('')
  const [glarePosition, setGlarePosition] = useState({ x: 50, y: 50, opacity: 0 })
  const [isHovered, setIsHovered] = useState(false)

  const handleMouseMove = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (!cardRef.current) return
      const rect = cardRef.current.getBoundingClientRect()
      const x = e.clientX - rect.left
      const y = e.clientY - rect.top

      const percentX = x / rect.width
      const percentY = y / rect.height

      const tiltX = (percentY - 0.5) * -effectiveMaxTilt * 2
      const tiltY = (percentX - 0.5) * effectiveMaxTilt * 2

      setTransform(
        `perspective(${perspective}px) rotateX(${tiltX.toFixed(2)}deg) rotateY(${tiltY.toFixed(2)}deg) scale3d(${scale}, ${scale}, ${scale})`
      )

      if (glare) {
        setGlarePosition({
          x: Math.round(percentX * 100),
          y: Math.round(percentY * 100),
          opacity: 1,
        })
      }
    },
    [effectiveMaxTilt, glare, perspective, scale]
  )

  const handleMouseEnter = useCallback(() => {
    setIsHovered(true)
  }, [])

  const handleMouseLeave = useCallback(() => {
    setIsHovered(false)
    setTransform(`perspective(${perspective}px) rotateX(0deg) rotateY(0deg) scale3d(1, 1, 1)`)
    setGlarePosition((prev) => ({ ...prev, opacity: 0 }))
  }, [perspective])

  return (
    <div
      ref={cardRef}
      onMouseMove={handleMouseMove}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      className={`relative transform-gpu transition-all duration-300 ${className}`}
      style={{
        transform,
        transformStyle: 'preserve-3d',
        transition: isHovered
          ? 'transform 0.08s ease-out'
          : 'transform 0.5s cubic-bezier(0.2, 0.8, 0.2, 1)',
        ...style,
      }}
    >
      {/* Optional Specular Glare Reflection */}
      {glare && (
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 z-30 rounded-inherit overflow-hidden transition-opacity duration-300"
          style={{
            borderRadius: style.borderRadius || 'inherit',
            opacity: glarePosition.opacity,
            background: `radial-gradient(circle at ${glarePosition.x}% ${glarePosition.y}%, ${glareColor} 0%, transparent 60%)`,
          }}
        />
      )}
      {children}
    </div>
  )
}
