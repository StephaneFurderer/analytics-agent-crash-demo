-- The hurricane loading: an Expert-judgment estimate of an event's claims that the data has not shown yet.
--
-- metric_hurricane_loading: version-controlled assumption data (compass/assumptions/hurricane_loading.csv),
-- kept separate from the standard development factors. One row per event: the destination region it
-- hits, its date, and the loading per Policy at risk there on that date (see 50_exposure.sql): expected
-- claims (count_per_policy) and expected losses as a share of trip cost (amount_per_trip_cost), on top of
-- the chain-ladder Ultimate.
--
-- metric_experience_loaded: metric_experience plus each Policy's loading (summed over events). The loading
-- is NOT applied by default: `ultimate`, `ae` and `loss_ratio` stay unloaded; the *_with_loading metrics
-- apply it.

CREATE TABLE metric_hurricane_loading AS
SELECT
    CAST(event AS VARCHAR)               AS event,
    CAST(destination_region AS VARCHAR)  AS destination_region,
    CAST(event_date AS DATE)             AS event_date,
    CAST(count_per_policy AS DOUBLE)     AS count_per_policy,
    CAST(amount_per_trip_cost AS DOUBLE) AS amount_per_trip_cost
FROM _hurricane_loading
ORDER BY event_date, event;

CREATE VIEW metric_experience_loaded AS
WITH loading AS (
    SELECT
        e.policy_id,
        sum(h.count_per_policy)            AS loading_claims,
        sum(h.amount_per_trip_cost * e.trip_cost) AS loading_amount
    FROM metric_experience e
    JOIN metric_hurricane_loading h
      ON h.destination_region = e.destination_region
     AND e.purchase_date <= h.event_date AND h.event_date <= e.return_date
    GROUP BY e.policy_id
)
SELECT
    e.*,
    coalesce(l.loading_claims, 0.0) AS loading_claims,
    coalesce(l.loading_amount, 0.0) AS loading_amount
FROM metric_experience e
LEFT JOIN loading l USING (policy_id);

INSERT INTO metric_definitions VALUES
    ('hurricane_loading_claim_count', 'Hurricane loading claims', 'metric_experience_loaded', 'sum(loading_claims)',
     'count',
     'Expert-judgment estimate of an event''s claims not yet in Ultimate: claims per Policy at risk in the '
     'event''s destination region on its date, from the hurricane loading assumption.'),
    ('hurricane_loading', 'Hurricane loading', 'metric_experience_loaded', 'sum(loading_amount)', 'currency',
     'Expert-judgment estimate of an event''s losses not yet in Ultimate: a share of the trip cost at risk in the '
     'event''s destination region on its date, from the hurricane loading assumption. Kept separate from the '
     'standard development factors and not included in Ultimate by default.'),
    ('ultimate_with_loading', 'Ultimate with hurricane loading', 'metric_experience_loaded',
     'sum(incurred * amount_factor + loading_amount)', 'currency',
     'Ultimate on the standard development factors plus the hurricane loading.'),
    ('ultimate_claim_count_with_loading', 'Ultimate claims with hurricane loading', 'metric_experience_loaded',
     'sum(reported_claims * count_factor + loading_claims)', 'count',
     'Ultimate claims on the standard development factors plus the hurricane loading claims.'),
    ('loss_ratio_with_loading', 'Loss ratio with hurricane loading', 'metric_experience_loaded',
     'sum(incurred * amount_factor + loading_amount) / sum(commercial_premium * earned_share)', 'ratio',
     'Ultimate losses with the hurricane loading divided by earned Commercial premium.'),
    ('ae_with_loading', 'A/E with hurricane loading', 'metric_experience_loaded',
     'sum(incurred * amount_factor + loading_amount) / sum(pure_premium * earned_share)', 'ratio',
     'Actual over Expected on the Pricing basis, with the hurricane loading in Actual: Ultimate losses plus the '
     'loading, divided by earned Pure premium. Same A/E bands as A/E.');
