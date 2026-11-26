-- metric_pricing_basis: the Pricing basis's coefficients, one row per term.

CREATE VIEW metric_pricing_basis AS
SELECT model, component, term, coefficient
FROM pricing_coefficients;
