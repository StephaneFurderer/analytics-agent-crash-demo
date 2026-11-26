-- Development: IBNR and Ultimate from the standard development factors.
--
-- metric_development_factors: the standard development factors, loaded from version-controlled
-- assumption data (compass/assumptions/development_factors.csv), never derived from the warehouse
-- at query time. Maturity is the number of whole months from a Policy's departure month to the
-- Valuation month (0 = departs in the Valuation month; negative = not departed yet). A Policy uses
-- the factor row with the largest maturity at or below its own, or the first row if it has none.
--
-- metric_experience: one row per Policy, with every metric_policies dimension, its maturity and
-- factors, and its reported claims aggregated. IBNR is a chain-ladder estimate at the portfolio
-- level: Incurred of each maturity cell times (factor - 1), selected separately for counts and
-- amounts. The Policy grain only carries the cells so any breakdown adds up; it is not a
-- per-claim reserve. Reserve = Case reserve + IBNR = IBNR, since Case reserves are zero.

CREATE TABLE metric_development_factors AS
SELECT
    CAST(maturity_months AS INTEGER) AS maturity_months,
    CAST(count_factor AS DOUBLE)     AS count_factor,
    CAST(amount_factor AS DOUBLE)    AS amount_factor
FROM _development_factors
ORDER BY maturity_months;

CREATE VIEW metric_experience AS
WITH
    matured AS (
        SELECT
            p.*,
            date_diff('month', date_trunc('month', p.departure_date), date_trunc('month', valuation_date()))
                AS maturity_months
        FROM metric_policies p
    ),
    -- The factor row each maturity uses: the largest at or below it, else the first row.
    resolved AS (
        SELECT
            m.*,
            coalesce(
                (SELECT max(d.maturity_months) FROM metric_development_factors d
                 WHERE d.maturity_months <= m.maturity_months),
                (SELECT min(d.maturity_months) FROM metric_development_factors d)) AS factor_maturity
        FROM matured m
    ),
    claims AS (
        SELECT policy_id, count(*) AS reported_claims, sum(paid_amount + case_reserve) AS incurred
        FROM claims
        GROUP BY policy_id
    )
SELECT
    r.*,
    f.count_factor,
    f.amount_factor,
    coalesce(c.reported_claims, 0) AS reported_claims,
    coalesce(c.incurred, 0.0)      AS incurred
FROM resolved r
JOIN metric_development_factors f ON f.maturity_months = r.factor_maturity
LEFT JOIN claims c USING (policy_id);

INSERT INTO metric_definitions VALUES
    ('ibnr_claim_count', 'IBNR claims', 'metric_experience', 'sum(reported_claims * (count_factor - 1))', 'count',
     'Expected number of claims occurred but not reported by the Valuation date: reported claims times '
     '(count development factor - 1) at each maturity.'),
    ('ibnr', 'IBNR', 'metric_experience', 'sum(incurred * (amount_factor - 1))', 'currency',
     'Expected amount to be paid on claims occurred but not reported by the Valuation date: Incurred times '
     '(amount development factor - 1) at each maturity, from the standard development factors. The only Reserve.');
