-- metric_claims: one row per reported claim, with the same breakdown dimensions
-- as metric_policies (so claims and premium line up under any breakdown) plus
-- the claim's own type and dates.
--
-- Incurred = Paid + Case reserve. Claims are paid in full when reported, so Case
-- reserve is zero and Incurred equals Paid. Ultimate (Incurred + IBNR) comes later.

CREATE VIEW metric_claims AS
SELECT
    c.claim_id,
    c.claim_type,
    c.loss_date,
    c.report_date,
    c.paid_amount,
    c.case_reserve,
    p.policy_id,
    p.booking_id,
    p.segment,
    p.coverage_type,
    p.product,
    p.destination_region,
    p.destination,
    p.underwriting_year,
    p.departure_month,
    p.purchase_date,
    p.departure_date,
    p.return_date,
    p.trip_cost
FROM claims c
JOIN metric_policies p USING (policy_id);

INSERT INTO metric_definitions VALUES
    ('reported_claim_count', 'Reported claims', 'metric_claims', 'count(claim_id)', 'count',
     'Number of claims reported by the Valuation date.'),
    ('paid', 'Paid', 'metric_claims', 'coalesce(sum(paid_amount), 0)', 'currency',
     'Amount paid on claims reported by the Valuation date. Claims are paid in full when reported.'),
    ('case_reserve', 'Case reserve', 'metric_claims', 'coalesce(sum(case_reserve), 0)', 'currency',
     'Amount set aside for reported claims not yet paid. Always zero: claims are paid in full when reported.'),
    ('incurred', 'Incurred', 'metric_claims', 'coalesce(sum(paid_amount + case_reserve), 0)', 'currency',
     'Paid plus Case reserve on reported claims. Equals Paid, since Case reserves are zero. Not Ultimate: excludes IBNR.');
