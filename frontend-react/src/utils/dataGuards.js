/**
 * dataGuards.js — Phase 6.2 runtime safety
 * Type-safe utilities for handling uncertain backend shapes.
 * Import in any page: import { hasFlag, safeStr } from '../utils/dataGuards.js'
 */

/**
 * hasFlag(flags, flag)
 * Safely checks if a flag exists regardless of backend shape.
 * Handles: Array | Object | string | null | undefined
 *
 * Examples:
 *   hasFlag(['single_period', 'capex_missing'], 'single_period') → true
 *   hasFlag({ single_period: true },             'single_period') → true
 *   hasFlag('single_period',                     'single_period') → true
 *   hasFlag(null,                                'single_period') → false
 *   hasFlag(undefined,                           'single_period') → false
 */
export function hasFlag(flags, flag) {
  if (!flags) return false
  if (Array.isArray(flags))        return flags.includes(flag)
  if (typeof flags === 'object')   return Boolean(flags[flag])
  if (typeof flags === 'string')   return flags === flag
  return false
}

/**
 * safeStr(value)
 * Returns a string or null — never crashes on .includes()
 */
export function safeStr(value) {
  if (value == null) return null
  if (typeof value === 'string') return value
  return String(value)
}

/**
 * safeIncludes(value, search)
 * Safely calls .includes() on a string — returns false if not a string
 */
export function safeIncludes(value, search) {
  if (typeof value !== 'string') return false
  return value.includes(search)
}
