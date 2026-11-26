-- The A/E bands, defined once: adequate up to 1.05, watch up to 1.20, otherwise inadequate.
-- Each band covers A/E above the previous band's upper bound, up to and including its own.
-- The dashboard and the agent label A/E with ae_band(), so both use the same words.

CREATE TABLE metric_ae_bands (
    band        VARCHAR PRIMARY KEY,
    upper_bound DOUBLE,  -- NULL: no upper bound
    description VARCHAR NOT NULL
);

INSERT INTO metric_ae_bands VALUES
    ('adequate', 1.05, 'A/E up to 1.05: the Pricing basis covers the experience.'),
    ('watch', 1.20, 'A/E above 1.05, up to 1.20: monitor; the Pricing basis may be short.'),
    ('inadequate', NULL, 'A/E above 1.20: the Pricing basis does not cover the experience.');

CREATE MACRO ae_band(ae) AS (
    SELECT band FROM metric_ae_bands
    WHERE upper_bound IS NULL OR ae <= upper_bound
    ORDER BY upper_bound NULLS LAST
    LIMIT 1
);
