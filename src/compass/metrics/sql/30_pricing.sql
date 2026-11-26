-- metric_pricing_basis: the Pricing basis's coefficients, one row per term.

CREATE VIEW metric_pricing_basis AS
SELECT model, component, term, coefficient
FROM pricing_coefficients;

-- metric_pricing_expected: one row per Policy with its expected claim count and
-- mean claim amount on the Pricing basis, evaluated from the stored coefficients
-- (log link). Same breakdown dimensions as metric_policies.
--   log(frequency) = intercept + age * (age - 40) / 10 + log_trip_cost * ln(trip_cost)
--                    + product_flight [flight] + segment_<s> + state_<st> + month_<departure month>
--   log(severity)  = intercept + age * (age - 40) / 10 + log_trip_cost * ln(trip_cost)
--                    + product_flight [flight] + post_departure [post-departure claim]
-- A term that is not stored (a reference level) contributes 0.

CREATE VIEW metric_pricing_expected AS
WITH
    f AS (SELECT term, coefficient FROM pricing_coefficients WHERE component = 'frequency'),
    s AS (SELECT term, coefficient FROM pricing_coefficients WHERE component = 'severity'),
    c AS (
        SELECT
            (SELECT coefficient FROM f WHERE term = 'intercept')              AS f_intercept,
            (SELECT coefficient FROM f WHERE term = 'age')                    AS f_age,
            (SELECT coefficient FROM f WHERE term = 'log_trip_cost')          AS f_log_trip_cost,
            (SELECT coefficient FROM f WHERE term = 'product_flight')         AS f_product_flight,
            (SELECT coefficient FROM s WHERE term = 'intercept')              AS s_intercept,
            (SELECT coefficient FROM s WHERE term = 'age')                    AS s_age,
            (SELECT coefficient FROM s WHERE term = 'log_trip_cost')          AS s_log_trip_cost,
            (SELECT coefficient FROM s WHERE term = 'product_flight')         AS s_product_flight,
            (SELECT coefficient FROM s WHERE term = 'post_departure')         AS s_post_departure,
            (SELECT coefficient FROM pricing_coefficients
             WHERE component = 'premium' AND term = 'post_departure_share')  AS post_departure_share
    ),
    eta AS (
        SELECT
            mp.*,
            c.post_departure_share,
            c.s_post_departure,
            c.f_intercept
                + c.f_age * (b.age - 40) / 10.0
                + c.f_log_trip_cost * ln(greatest(mp.trip_cost, 1.0))
                + CASE WHEN mp.product = 'flight' THEN c.f_product_flight ELSE 0 END
                + coalesce(fs.coefficient, 0) + coalesce(fst.coefficient, 0) + coalesce(fm.coefficient, 0)
                AS frequency_eta,
            c.s_intercept
                + c.s_age * (b.age - 40) / 10.0
                + c.s_log_trip_cost * ln(greatest(mp.trip_cost, 1.0))
                + CASE WHEN mp.product = 'flight' THEN c.s_product_flight ELSE 0 END
                AS severity_eta
        FROM metric_policies mp
        JOIN bookings b USING (booking_id)
        CROSS JOIN c
        LEFT JOIN f fs  ON fs.term  = 'segment_' || mp.segment
        LEFT JOIN f fst ON fst.term = 'state_' || b.state_of_residence
        LEFT JOIN f fm  ON fm.term  = 'month_' || mp.departure_month
    )
SELECT
    policy_id, booking_id, segment, coverage_type, product, destination_region, destination, underwriting_year,
    departure_month, purchase_date, departure_date, return_date, trip_cost,
    exp(frequency_eta) AS expected_claims,
    (1 - post_departure_share) * exp(severity_eta)
        + post_departure_share * exp(severity_eta + s_post_departure) AS expected_severity
FROM eta;

INSERT INTO metric_definitions VALUES
    ('expected_claim_count', 'Expected claims', 'metric_pricing_expected', 'sum(expected_claims)', 'count',
     'Expected number of claims on the Pricing basis: the pricing GLM frequency, summed over Policies.'),
    ('expected_claim_frequency', 'Expected claim frequency', 'metric_pricing_expected',
     'sum(expected_claims) / count(policy_id)', 'ratio',
     'Expected claims per Policy on the Pricing basis (pricing GLM frequency).'),
    ('expected_average_severity', 'Expected average severity', 'metric_pricing_expected',
     'sum(expected_claims * expected_severity) / sum(expected_claims)', 'currency',
     'Expected mean claim amount on the Pricing basis: pricing GLM severity, mixing pre- and post-departure '
     'claims by the post-departure share, weighted by expected claims.');
