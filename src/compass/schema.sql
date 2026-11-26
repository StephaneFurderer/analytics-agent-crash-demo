-- Base tables of the Compass Assistance warehouse.
-- They hold what the department actually records. The true model behind the
-- data never lands here (ADR 0002), and neither does Underwriting year, which is
-- a definition in the Metric layer rather than a stored column.

CREATE TABLE destinations (
    destination_id   INTEGER PRIMARY KEY,
    city             VARCHAR NOT NULL,
    state_or_country VARCHAR NOT NULL,
    region           VARCHAR NOT NULL CHECK (region IN ('us_atlantic', 'gulf_coast', 'caribbean')),
    airport_code     VARCHAR NOT NULL,
    hotel_rate       DOUBLE  NOT NULL
);

CREATE TABLE bookings (
    booking_id         VARCHAR PRIMARY KEY,
    segment            VARCHAR NOT NULL CHECK (segment IN ('winter_birds', 'holiday_travelers', 'baseline')),
    destination_id     INTEGER NOT NULL REFERENCES destinations (destination_id),
    age                INTEGER NOT NULL,
    state_of_residence VARCHAR NOT NULL,
    coverage_type      VARCHAR NOT NULL CHECK (coverage_type IN ('hotel_only', 'flight_only', 'hotel_and_flight')),
    purchase_date      DATE    NOT NULL,
    departure_date     DATE    NOT NULL,
    return_date        DATE    NOT NULL,
    num_nights         INTEGER NOT NULL
);

CREATE TABLE policies (
    policy_id          VARCHAR PRIMARY KEY,
    booking_id         VARCHAR NOT NULL REFERENCES bookings (booking_id),
    product            VARCHAR NOT NULL CHECK (product IN ('hotel', 'flight')),
    trip_cost          DOUBLE  NOT NULL,
    pure_premium       DOUBLE  NOT NULL,
    commercial_premium DOUBLE  NOT NULL
);

-- Claims reported by the Valuation date. A claim is paid in full when it is
-- reported, so case_reserve is always zero.
CREATE TABLE claims (
    claim_id     VARCHAR PRIMARY KEY,
    policy_id    VARCHAR NOT NULL REFERENCES policies (policy_id),
    claim_type   VARCHAR NOT NULL CHECK (claim_type IN ('pre_departure', 'post_departure')),
    loss_date    DATE    NOT NULL,
    report_date  DATE    NOT NULL,
    paid_amount  DOUBLE  NOT NULL,
    case_reserve DOUBLE  NOT NULL DEFAULT 0
);

-- The Pricing basis: the 2025 pricing GLM's coefficients, as the pricing team set
-- them. It is the only model in the warehouse (ADR 0002). `component` is
-- 'frequency' or 'severity' (GLM terms, log link) or 'premium' (the claim-type
-- mix `post_departure_share` and the `expense_load`).
CREATE TABLE pricing_coefficients (
    model       VARCHAR NOT NULL,
    component   VARCHAR NOT NULL CHECK (component IN ('frequency', 'severity', 'premium')),
    term        VARCHAR NOT NULL,
    coefficient DOUBLE  NOT NULL,
    PRIMARY KEY (model, component, term)
);
