import { Check } from 'lucide-react'

import type { CreditPlan } from '../../api/client.service'
import { cn } from '../../lib/cn'
import { Badge, Button } from '../ui'

interface PlanCardProps {
  plan: CreditPlan
  isRecommended: boolean
  isCurrent: boolean
  onSelect: (plan: CreditPlan) => void
}

export default function PlanCard({ plan, isRecommended, isCurrent, onSelect }: PlanCardProps) {
  const isPaid = Number(plan.price_usd) > 0
  const disabled = !isPaid

  const actionLabel = !isPaid
    ? isCurrent
      ? 'Plan actual'
      : 'Plan base'
    : isCurrent
      ? 'Recargar plan'
      : `Elegir ${plan.name}`

  return (
    <div
      className={cn(
        'relative flex flex-col gap-3 rounded-xl border p-4 transition-colors',
        isRecommended ? 'border-primary bg-card-hover' : 'border-border-strong bg-surface'
      )}
    >
      {isRecommended && (
        <div className="absolute right-3 top-3">
          <Badge variant="primary">Popular</Badge>
        </div>
      )}

      <div>
        <h3 className="pr-20 text-base font-bold text-white">{plan.name}</h3>
        <div className="mt-1.5 flex items-baseline gap-1">
          <span className="text-2xl font-black text-white">${plan.price_usd}</span>
          <span className="text-xs text-muted">/mes</span>
        </div>
      </div>

      <ul className="flex flex-1 flex-col gap-1.5 text-xs text-muted">
        <li className="flex items-start gap-1.5">
          <Check size={14} className="mt-0.5 shrink-0 text-primary" aria-hidden="true" />
          <span>{plan.credits_per_month} créditos/mes</span>
        </li>
        {plan.features.map((feature, index) => (
          <li key={index} className="flex items-start gap-1.5">
            <Check size={14} className="mt-0.5 shrink-0 text-primary" aria-hidden="true" />
            <span>{feature}</span>
          </li>
        ))}
      </ul>

      <Button
        variant={isPaid ? 'primary' : 'secondary'}
        size="sm"
        disabled={disabled}
        onClick={() => onSelect(plan)}
        className="mt-2 w-full"
      >
        {actionLabel}
      </Button>
    </div>
  )
}
