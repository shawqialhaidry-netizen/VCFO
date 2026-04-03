import { useState, useEffect, useRef } from 'react'

function easeOutCubic(t) {
  return 1 - (1 - t) ** 3
}

/**
 * Interpolate toward numeric `target` when `target` changes (UI only).
 * First run animates from 0; later runs animate from the last displayed value.
 * Easing: ease-out cubic; duration 400–700ms typical.
 */
export function useCountUp(target, { durationMs = 600, enabled = true } = {}) {
  const valueRef = useRef(null)
  const [value, setValue] = useState(() => {
    if (!enabled || target == null || !Number.isFinite(Number(target))) return target
    return 0
  })

  useEffect(() => {
    if (!enabled || target == null || !Number.isFinite(Number(target))) {
      setValue(target)
      if (target != null && Number.isFinite(Number(target))) valueRef.current = Number(target)
      return
    }
    const end = Number(target)
    const start =
      valueRef.current != null && Number.isFinite(Number(valueRef.current)) ? Number(valueRef.current) : 0
    if (Math.abs(end - start) < 1e-9) {
      setValue(end)
      valueRef.current = end
      return
    }

    const t0 = performance.now()
    let raf = 0
    const tick = (now) => {
      const u = Math.min(1, (now - t0) / durationMs)
      const eased = easeOutCubic(u)
      const v = start + (end - start) * eased
      valueRef.current = v
      setValue(v)
      if (u < 1) raf = requestAnimationFrame(tick)
      else {
        valueRef.current = end
        setValue(end)
      }
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [target, durationMs, enabled])

  return value
}
