import { PILLAR_CONFIG } from '@/types/radar'

interface PillarPillProps {
  pillar: string
  size?: 'sm' | 'md'
}

export function PillarPill({ pillar, size = 'sm' }: PillarPillProps) {
  const config = PILLAR_CONFIG[pillar] ?? { label: pillar, color: '#6b7280', bg: '#f3f4f6' }

  return (
    <span
      className={`inline-flex items-center rounded-full font-medium tracking-wide ${
        size === 'sm' ? 'px-2.5 py-0.5 text-[10px]' : 'px-3 py-1 text-xs'
      }`}
      style={{ backgroundColor: config.bg, color: config.color }}
    >
      {config.label}
    </span>
  )
}
