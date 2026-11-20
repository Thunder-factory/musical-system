import { useCallback } from 'react'
import { create } from 'zustand'

import { Button } from './button'
import { Modal } from './modal'

export interface ConfirmOptions {
  title: string
  description?: string
  confirmLabel?: string
  cancelLabel?: string
  variant?: 'danger' | 'primary'
}

interface PendingConfirm extends ConfirmOptions {
  resolve: (accepted: boolean) => void
}

interface ConfirmStore {
  pending: PendingConfirm | null
  openConfirm: (options: ConfirmOptions) => Promise<boolean>
  resolveConfirm: (accepted: boolean) => void
}

const useConfirmStore = create<ConfirmStore>((set, get) => ({
  pending: null,
  openConfirm: (options) =>
    new Promise<boolean>((resolve) => {
      const current = get().pending
      if (current) {
        current.resolve(false)
      }
      set({ pending: { ...options, resolve } })
    }),
  resolveConfirm: (accepted) => {
    const current = get().pending
    if (!current) {
      return
    }
    set({ pending: null })
    current.resolve(accepted)
  },
}))

export function useConfirm(): (options: ConfirmOptions) => Promise<boolean> {
  const openConfirm = useConfirmStore((state) => state.openConfirm)
  return useCallback((options: ConfirmOptions) => openConfirm(options), [openConfirm])
}

export function ConfirmDialogHost() {
  const pending = useConfirmStore((state) => state.pending)
  const resolveConfirm = useConfirmStore((state) => state.resolveConfirm)

  return (
    <Modal
      open={Boolean(pending)}
      onClose={() => resolveConfirm(false)}
      title={pending?.title ?? ''}
      size="sm"
      footer={
        pending ? (
          <>
            <Button variant="secondary" size="sm" onClick={() => resolveConfirm(false)}>
              {pending.cancelLabel ?? 'Cancelar'}
            </Button>
            <Button
              variant={pending.variant ?? 'primary'}
              size="sm"
              onClick={() => resolveConfirm(true)}
            >
              {pending.confirmLabel ?? 'Confirmar'}
            </Button>
          </>
        ) : undefined
      }
    >
      {pending?.description && (
        <p className="text-sm leading-relaxed text-muted">{pending.description}</p>
      )}
    </Modal>
  )
}
