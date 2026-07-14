import { z } from 'zod'

/**
 * Zod schema for an event item (the canonical "agenda" row).
 *
 * Dates are always stored as epoch milliseconds on the public API.
 * Provider-specific date representations (Firestore Timestamp, ISO strings)
 * are converted at the adapter / server-handler boundaries.
 */
export const EventSchema = z.object({
  id: z.string(),
  title: z.string(),
  description: z.string(),
  date: z.number().optional(),
  createdAt: z.number().optional(),
  image: z.string(),
  link: z.string().optional(),
  location: z.string(),
  time: z.string(),
  archived: z.boolean().optional(),
  slug: z.string().optional(),
  tags: z.array(z.string()).optional(),
  attendees: z.number().optional(),
  vips_limit: z.number().optional(),
})

export type Event = z.infer<typeof EventSchema>

/**
 * Accepts any supported date representation and returns epoch milliseconds.
 * Supports: number (pass-through), Date, ISO string, or `dd/MM/yyyy`.
 */
function coerceDateToMillis(value: unknown): number | undefined {
  if (value === undefined || value === null) return undefined
  if (typeof value === 'number') return value
  if (value instanceof Date) return value.getTime()
  if (typeof value === 'string') {
    const ddmmyyyy = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(value)
    if (ddmmyyyy) {
      const day = Number(ddmmyyyy[1])
      const month = Number(ddmmyyyy[2]) - 1
      const year = Number(ddmmyyyy[3])
      return new Date(year, month, day).getTime()
    }
    const parsed = Date.parse(value)
    if (!Number.isNaN(parsed)) return parsed
  }
  return undefined
}

/**
 * Validates incoming event data and normalises its `date` / `createdAt`
 * fields to epoch milliseconds. Throws a Zod error when validation fails.
 */
export function validateAndConvertEvent(data: unknown): Event {
  const raw = (data ?? {}) as Record<string, unknown>
  const normalized: Record<string, unknown> = { ...raw }

  const dateMs = coerceDateToMillis(raw.date)
  if (dateMs !== undefined) normalized.date = dateMs

  const createdAtMs = coerceDateToMillis(raw.createdAt)
  if (createdAtMs !== undefined) normalized.createdAt = createdAtMs

  return EventSchema.parse(normalized)
}
