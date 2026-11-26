-- metric_policies: one row per Policy, with every breakdown dimension attached.
-- A hotel-and-flight Booking appears on two rows (one per Policy), so Booking
-- count is a DISTINCT count and is correct under any breakdown.
--
-- Underwriting year is the year of the purchase date (a definition, not a stored
-- column). Earned premium is earned evenly from purchase to return, prorated at
-- the Valuation date: earned_share is the share of those days that has passed.

CREATE VIEW metric_policies AS
SELECT
    p.policy_id,
    p.booking_id,
    b.segment,
    b.coverage_type,
    p.product,
    d.region           AS destination_region,
    d.city             AS destination,
    year(b.purchase_date)   AS underwriting_year,
    month(b.departure_date) AS departure_month,
    b.purchase_date,
    b.departure_date,
    b.return_date,
    p.trip_cost,
    p.pure_premium,
    p.commercial_premium,
    greatest(0.0, least(1.0,
        date_diff('day', b.purchase_date, valuation_date())
        / date_diff('day', b.purchase_date, b.return_date))) AS earned_share
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
     'Commercial premium written: the price customers pay, summed over Policies.'),
    ('earned_pure_premium', 'Earned pure premium', 'metric_policies', 'sum(pure_premium * earned_share)', 'currency',
     'Pure premium earned by the Valuation date, earned evenly from purchase date to return date.'),
    ('earned_commercial_premium', 'Earned commercial premium', 'metric_policies',
     'sum(commercial_premium * earned_share)', 'currency',
     'Commercial premium earned by the Valuation date, earned evenly from purchase date to return date.');
