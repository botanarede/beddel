import { describe, it, expect } from 'vitest';
import {
  TimeSlotSchema,
  ReservationAvailabilityQuerySchema,
  ReservationBookingRequestSchema,
  ReservationAvailabilityResultSchema,
  ReservationWorkflowStateSchema,
} from './reservation';

describe('TimeSlotSchema', () => {
  it('validates a valid time slot', () => {
    expect(TimeSlotSchema.safeParse({ time: '19:00', capacity: 4 }).success).toBe(true);
  });
});

describe('ReservationAvailabilityQuerySchema', () => {
  it('validates a valid query', () => {
    const result = ReservationAvailabilityQuerySchema.safeParse({
      date: '2026-04-01',
      partySize: 4,
      tenantId: 'casa-savana',
    });
    expect(result.success).toBe(true);
  });

  it('fails when date is missing', () => {
    const result = ReservationAvailabilityQuerySchema.safeParse({
      partySize: 4,
      tenantId: 'casa-savana',
    });
    expect(result.success).toBe(false);
    if (!result.success) {
      const paths = result.error.issues.map((i) => i.path.join('.'));
      expect(paths).toContain('date');
    }
  });

  it('fails when partySize is 0', () => {
    expect(
      ReservationAvailabilityQuerySchema.safeParse({
        date: '2026-04-01',
        partySize: 0,
        tenantId: 'x',
      }).success,
    ).toBe(false);
  });

  it('fails when partySize is negative', () => {
    expect(
      ReservationAvailabilityQuerySchema.safeParse({
        date: '2026-04-01',
        partySize: -2,
        tenantId: 'x',
      }).success,
    ).toBe(false);
  });
});

describe('ReservationBookingRequestSchema', () => {
  const validBooking = {
    tenantId: 'casa-savana',
    date: '2026-04-01',
    partySize: 4,
    contactName: 'John Doe',
    contactEmail: 'john@example.com',
    contactPhone: '555-1234',
    notes: 'Window seat please',
  };

  it('validates a full valid object including optional notes', () => {
    expect(ReservationBookingRequestSchema.safeParse(validBooking).success).toBe(true);
  });

  it('validates without notes (optional field)', () => {
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const { notes: _notes, ...withoutNotes } = validBooking;
    expect(ReservationBookingRequestSchema.safeParse(withoutNotes).success).toBe(true);
  });

  it('fails when contactEmail is not a valid email', () => {
    expect(
      ReservationBookingRequestSchema.safeParse({ ...validBooking, contactEmail: 'not-an-email' })
        .success,
    ).toBe(false);
  });
});

describe('ReservationAvailabilityResultSchema', () => {
  it('validates with available: true and non-empty slots', () => {
    const result = ReservationAvailabilityResultSchema.safeParse({
      available: true,
      slots: [
        { time: '19:00', capacity: 4 },
        { time: '20:00', capacity: 2 },
      ],
      message: 'Tables available',
    });
    expect(result.success).toBe(true);
  });

  it('validates with available: false and empty slots', () => {
    const result = ReservationAvailabilityResultSchema.safeParse({
      available: false,
      slots: [],
    });
    expect(result.success).toBe(true);
  });
});

describe('ReservationWorkflowStateSchema', () => {
  const states = [
    { status: 'idle' },
    { status: 'checking' },
    {
      status: 'available',
      result: { available: true, slots: [{ time: '19:00', capacity: 4 }] },
    },
    {
      status: 'unavailable',
      result: { available: false, slots: [] },
    },
    { status: 'submitting' },
    { status: 'confirmed', bookingRef: 'BK-001' },
    { status: 'error', message: 'Network error' },
  ];

  for (const state of states) {
    it(`validates state: ${state.status}`, () => {
      expect(ReservationWorkflowStateSchema.safeParse(state).success).toBe(true);
    });
  }

  it('fails for unknown status value', () => {
    expect(ReservationWorkflowStateSchema.safeParse({ status: 'cancelled' }).success).toBe(false);
  });
});

describe('index exports', () => {
  it('all reservation schemas are importable from @botanarede/schema', async () => {
    const mod = await import('./index');
    expect(mod.TimeSlotSchema).toBeDefined();
    expect(mod.ReservationAvailabilityQuerySchema).toBeDefined();
    expect(mod.ReservationBookingRequestSchema).toBeDefined();
    expect(mod.ReservationAvailabilityResultSchema).toBeDefined();
    expect(mod.ReservationWorkflowStateSchema).toBeDefined();
  });
});
