/**
 * Reservation workflow contract — Zod schemas for availability and booking.
 *
 * Types only — no runtime implementation. Backend in E6/E9, UI in E9.
 * Enables the frontend to implement the workflow against a well-defined
 * interface before the backend is ready.
 */

import { z } from 'zod';

// --- Primitives ---

export const TimeSlotSchema = z
  .object({
    time: z.string().min(1),
    capacity: z.number().int().positive(),
  })
  .strict();

export type TimeSlot = z.infer<typeof TimeSlotSchema>;

// --- Query and request schemas ---

export const ReservationAvailabilityQuerySchema = z
  .object({
    date: z.string().min(1),
    partySize: z.number().int().positive(),
    tenantId: z.string().min(1),
  })
  .strict();

export type ReservationAvailabilityQuery = z.infer<typeof ReservationAvailabilityQuerySchema>;

export const ReservationBookingRequestSchema = z
  .object({
    tenantId: z.string().min(1),
    date: z.string().min(1),
    partySize: z.number().int().positive(),
    contactName: z.string().min(1),
    contactEmail: z.string().email(),
    contactPhone: z.string().min(1),
    notes: z.string().optional(),
  })
  .strict();

export type ReservationBookingRequest = z.infer<typeof ReservationBookingRequestSchema>;

// --- Result schema ---

export const ReservationAvailabilityResultSchema = z
  .object({
    available: z.boolean(),
    slots: z.array(TimeSlotSchema),
    message: z.string().optional(),
  })
  .strict();

export type ReservationAvailabilityResult = z.infer<typeof ReservationAvailabilityResultSchema>;

// --- Workflow state machine ---

export const ReservationWorkflowStateSchema = z.discriminatedUnion('status', [
  z.object({ status: z.literal('idle') }).strict(),
  z.object({ status: z.literal('checking') }).strict(),
  z
    .object({
      status: z.literal('available'),
      result: ReservationAvailabilityResultSchema,
    })
    .strict(),
  z
    .object({
      status: z.literal('unavailable'),
      result: ReservationAvailabilityResultSchema,
    })
    .strict(),
  z.object({ status: z.literal('submitting') }).strict(),
  z
    .object({
      status: z.literal('confirmed'),
      bookingRef: z.string().optional(),
    })
    .strict(),
  z
    .object({
      status: z.literal('error'),
      message: z.string(),
    })
    .strict(),
]);

export type ReservationWorkflowState = z.infer<typeof ReservationWorkflowStateSchema>;
