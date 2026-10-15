import { useEffect, useState } from 'react'
import { WAKING_EVENT } from '../api/client'
import { Spinner } from './ui'

/** Shown while the (possibly sleeping) backend takes more than 5s to answer the first request. */
export default function WakingBanner() {
  const [waking, setWaking] = useState(false)

  useEffect(() => {
    const onWaking = (e: Event) => setWaking((e as CustomEvent<boolean>).detail)
    window.addEventListener(WAKING_EVENT, onWaking)
    return () => window.removeEventListener(WAKING_EVENT, onWaking)
  }, [])

  if (!waking) return null
  return (
    <div role="status" className="fixed inset-x-0 top-0 z-[60] flex justify-center p-3">
      <div className="flex items-center gap-2 rounded-full border border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-900 shadow-md">
        <Spinner />
        Waking up the server… free hosting sleeps when idle, this can take up to a minute.
      </div>
    </div>
  )
}
