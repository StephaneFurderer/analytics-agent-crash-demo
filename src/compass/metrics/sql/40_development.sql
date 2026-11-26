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

INSERT INTO metric_definitions VALUES
    ('ultimate', 'Ultimate', 'metric_experience', 'sum(incurred * amount_factor)', 'currency',
     'Final value of claims once every claim has been reported: Incurred plus IBNR, on the standard '
     'development factors. Actual for A/E.'),
    ('ultimate_claim_count', 'Ultimate claims', 'metric_experience', 'sum(reported_claims * count_factor)', 'count',
     'Final number of claims once every claim has been reported: reported claims plus IBNR claims.');

-- Ratios on Ultimate. Earned Policies = sum of earned shares. A/E is on the Pricing basis:
-- its Expected is earned Pure premium.
INSERT INTO metric_definitions VALUES
    ('ultimate_frequency', 'Ultimate frequency', 'metric_experience',
     'sum(reported_claims * count_factor) / sum(earned_share)', 'ratio',
     'Ultimate claims per earned Policy (Policies weighted by the share of their term earned by the Valuation date).'),
    ('ultimate_severity', 'Ultimate severity', 'metric_experience',
     'sum(incurred * amount_factor) / sum(reported_claims * count_factor)', 'currency',
     'Ultimate losses per Ultimate claim.'),
    ('loss_ratio', 'Loss ratio', 'metric_experience',
     'sum(incurred * amount_factor) / sum(commercial_premium * earned_share)', 'ratio',
     'Ultimate losses divided by earned Commercial premium.'),
    ('ae', 'A/E', 'metric_experience',
     'sum(incurred * amount_factor) / sum(pure_premium * earned_share)', 'ratio',
     'Actual over Expected on the Pricing basis: Ultimate losses divided by earned Pure premium. '
     'Bands: adequate up to 1.05, watch up to 1.20, otherwise inadequate.');
