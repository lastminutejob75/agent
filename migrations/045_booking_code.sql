-- Code rendez-vous court et unique par tenant (identification page publique).
ALTER TABLE public_bookings ADD COLUMN IF NOT EXISTS booking_code VARCHAR(8);

ALTER TABLE appointments ADD COLUMN IF NOT EXISTS booking_code VARCHAR(8);

CREATE UNIQUE INDEX IF NOT EXISTS idx_public_bookings_tenant_booking_code
  ON public_bookings (tenant_id, booking_code)
  WHERE booking_code IS NOT NULL AND booking_code <> '';

CREATE UNIQUE INDEX IF NOT EXISTS idx_appointments_tenant_booking_code
  ON appointments (tenant_id, booking_code)
  WHERE booking_code IS NOT NULL AND booking_code <> '';
