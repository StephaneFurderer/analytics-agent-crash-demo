-- metric_policies: one row per Policy, with every breakdown dimension attached.
-- A hotel-and-flight Booking appears on two rows (one per Policy), so Booking
-- count is a DISTINCT count and is correct under any breakdown.

CREATE VIEW metric_policies AS
SELECT
    p.policy_id,
    p.booking_id,
    b.segment,
    b.coverage_type,
    p.product,
    d.region           AS destination_region,
    d.city             AS destination,
    month(b.departure_date) AS departure_month,
    b.purchase_date,
    b.departure_date,
    b.return_date,
    p.trip_cost,
    p.pure_premium,
    p.commercial_premium
FROM policies p
JOIN bookings b USING (booking_id)
JOIN destinations d USING (destination_id);

INSERT INTO metric_definitions VALUES
    ('booking_count', 'Bookings', 'metric_policies', 'count(DISTINCT booking_id)', 'count',
     'Number of Bookings. A hotel-and-flight Booking counts once even though it holds two Policies.'),
    ('policy_count', 'Policies', 'metric_policies', 'count(policy_id)', 'count',
     'Number of Policies (Hotel or Flight covers). A hotel-and-flight Booking holds two.'),
    ('written_pure_premium', 'Written pure premium', 'metric_policies', 'sum(pure_premium)', 'currency',
     'Pure premium written: expected loss on the Pricing basis, summed over Policies.'),
    ('written_commercial_premium', 'Written commercial premium', 'metric_policies', 'sum(commercial_premium)', 'currency',
     'Commercial premium written: the price customers pay, summed over Policies.');
