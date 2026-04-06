import { useEffect, useState } from 'react'

function afterPaint(cb) {
  if (typeof window === 'undefined') return
  // Two rAFs is a common "after first paint" heuristic.
  requestAnimationFrame(() => requestAnimationFrame(cb))
}

/**
 * Returns `true` only after first paint / idle.
 *
 * Purpose: defer mounting expensive UI blocks (charts, large composites)
 * so the initial page becomes usable sooner.
 */
export function useDeferredMount({ idle = true, timeoutMs = 1200 } = {}) {
  const [ready, setReady] = useState(false)

  useEffect(() => {
    let cancelled = false
    const done = () => {
      if (cancelled) return
      setReady(true)
    }

    // Debug/perf toggle: allow disabling deferral without code changes.
    // Set localStorage vcfo_perf_no_defer=1 to mount immediately.
    try {
      if (localStorage.getItem('vcfo_perf_no_defer') === '1') {
        done()
        return () => {
          cancelled = true
        }
      }
    } catch {
      /* ignore */
    }

    afterPaint(() => {
      if (!idle) {
        done()
        return
      }

      const ric = window.requestIdleCallback
      if (typeof ric === 'function') {
        ric(() => done(), { timeout: timeoutMs })
      } else {
        window.setTimeout(done, Math.min(350, timeoutMs))
      }
    })

    return () => {
      cancelled = true
    }
  }, [idle, timeoutMs])

  return ready
}

