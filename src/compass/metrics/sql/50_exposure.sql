-- Exposure: trip cost at risk on a given date.
--
-- A Policy is at risk from its purchase date to its return date, both included: before departure it
-- can be cancelled, during the trip it can be interrupted. metric_exposure(on_date) is a table macro
-- returning the metric_policies rows at risk on that date, so exposure breaks down by every
-- metric_policies dimension. Its metrics need a date: metrics.query(..., on=<date>) or metrics.exposure.

CREATE MACRO metric_exposure(on_date) AS TABLE
SELECT *
FROM metric_policies
WHERE purchase_date <= CAST(on_date AS DATE) AND CAST(on_date AS DATE) <= return_date;

INSERT INTO metric_definitions VALUES
    ('exposure', 'Exposure', 'metric_exposure(on_date)', 'coalesce(sum(trip_cost), 0)', 'currency',
     'Trip cost at risk on a given date: the trip cost of every Policy purchased on or before that date '
     'and not yet returned (return date on or after it). Answers "how exposed are we to an event on that day?"'),
    ('policies_at_risk', 'Policies at risk', 'metric_exposure(on_date)', 'count(policy_id)', 'count',
     'Number of Policies at risk on a given date (purchased on or before it, returning on or after it).');
