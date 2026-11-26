-- The Valuation date: the date at which all data is observed. Earned premium is
-- prorated to it, and claims reported after it do not exist in the warehouse.
-- The generator's VALUATION_DATE must match (a generator test checks it).

CREATE MACRO valuation_date() AS DATE '2026-09-30';
