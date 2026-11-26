-- The Metric layer catalogue.
-- Every metric is defined exactly once, as one row here: the view it is computed
-- on and the SQL aggregate expression that computes it. Any breakdown is a
-- GROUP BY over that view's dimension columns, for example:
--
--   SELECT segment, count(DISTINCT booking_id) AS booking_count
--   FROM metric_policies GROUP BY segment;
--
-- The Legacy dashboard reads these rows and never writes its own formulas.

CREATE TABLE metric_definitions (
    metric      VARCHAR PRIMARY KEY,
    label       VARCHAR NOT NULL,
    view_name   VARCHAR NOT NULL,
    expression  VARCHAR NOT NULL,
    unit        VARCHAR NOT NULL CHECK (unit IN ('count', 'currency', 'ratio')),
    description VARCHAR NOT NULL
);
