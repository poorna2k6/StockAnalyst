import { motion } from 'framer-motion'
import { TrendingUp, TrendingDown } from 'lucide-react'

interface Props {
  price: number
  change_pct: number
  animate?: boolean
  size?: 'sm' | 'md' | 'lg'
}

export function PriceChip({ price, change_pct, animate = false, size = 'md' }: Props) {
  const isGain = change_pct >= 0
  const textColor = isGain ? 'text-emerald-400' : 'text-rose-400'
  const bgColor = isGain ? 'bg-emerald-400/10' : 'bg-rose-400/10'
  const Icon = isGain ? TrendingUp : TrendingDown

  const priceClass =
    size === 'sm' ? 'text-sm font-semibold' :
    size === 'lg' ? 'text-2xl font-bold' :
    'text-base font-semibold'
  const chipClass =
    size === 'sm' ? 'text-xs px-1.5 py-0.5' : 'text-sm px-2 py-1'

  return (
    <div className="flex items-center gap-2">
      <motion.span
        className={`${priceClass} text-white`}
        animate={animate ? { scale: [1, 1.04, 1] } : undefined}
        transition={{ duration: 0.4 }}
      >
        ${price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
      </motion.span>
      <span className={`flex items-center gap-1 rounded-full font-medium ${chipClass} ${textColor} ${bgColor}`}>
        <Icon size={10} />
        {isGain ? '+' : ''}{change_pct.toFixed(2)}%
      </span>
    </div>
  )
}
