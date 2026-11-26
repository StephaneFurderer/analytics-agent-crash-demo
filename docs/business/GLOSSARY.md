# Travel Insurance Actuarial

The definitions a travel insurance actuarial department agrees on. Agents and people both read them, so every answer uses the same meaning.

## Language

### The book

**Booking**:
One customer's purchase of cover for one trip. It holds one or two **Policies**.
_Avoid_: Trip, sale, order

**Policy**:
One cover (Hotel or Flight) within a **Booking**.
_Avoid_: Contract, cover, booking

### Experience vs assumptions

**Actual**:
The claims experience of an **Underwriting year** as at the **Valuation date**, taken as its **Ultimate**: **Incurred** plus **IBNR**.
_Avoid_: Real, observed

**Expected**:
The value implied by an assumption set. It is on the **Pricing basis** unless the **Forecast basis** is stated.
_Avoid_: Predicted, model value

**Pricing basis**:
The assumptions the pricing team set when the product was priced. They stay fixed once a policy is sold.
_Avoid_: Rating model, tariff

**Forecast basis**:
Assumptions that are re-estimated later from newer experience.
_Avoid_: Projection, outlook

**A/E**:
**Actual** divided by **Expected**.
_Avoid_: Model accuracy, loss ratio

**A/E band**:
The label for an **A/E**: adequate up to 1.05, watch above 1.05 up to 1.20, otherwise inadequate.
_Avoid_: Rating, traffic light

### Premium

**Pure premium**:
The expected loss of a **Policy** on the **Pricing basis**.
_Avoid_: Risk premium, technical premium

**Commercial premium**:
The price the customer pays, which is the **Pure premium** plus loadings.
_Avoid_: Gross premium, price

**Earned premium**:
The part of a policy's premium that relates to time already passed. It is earned evenly from the purchase date to the return date.
_Avoid_: Exposure premium

### Performance

**Loss ratio**:
**Ultimate** losses divided by **Earned premium** on a **Commercial premium** basis.
_Avoid_: Claims ratio, burning cost

**Drift**:
A lasting change in **Actual** experience that the **Pricing basis** does not reflect. It shows up as **A/E** moving away from 1.
_Avoid_: Dislocation, deterioration

### Time and maturity

**Valuation date**:
The date at which all data is observed. Claims reported after it do not exist yet.
_Avoid_: As-of date, cut-off date

**Underwriting year**:
The calendar year of a booking's purchase date.
_Avoid_: Cohort year, policy year, departure year

**Development**:
The growth of an **Underwriting year**'s **Incurred** claims over time as late claims are reported, until they reach **Ultimate**. In this demo, development comes only from late reporting, never from changes to **Case reserves**.
_Avoid_: Emergence, run-off

**Paid**:
The amount paid on reported claims as at the **Valuation date**.
_Avoid_: Settled, observed

**Case reserve**:
The amount set aside for a reported claim that has not been paid yet. In this demo a claim is paid in full when it is reported, so case reserves are always zero.
_Avoid_: Outstanding, claim reserve

**Incurred**:
**Paid** plus **Case reserve** on reported claims. Because case reserves are always zero in this demo, Incurred equals Paid.
_Avoid_: Reported losses

**IBNR**:
The expected amount to be paid on claims that occurred on or before the **Valuation date** but had not been reported by it. It is estimated at the portfolio level (for example by **Underwriting year**), never per claim.
_Avoid_: Development, late claims

**Reserve**:
The amount held for future payments: **Case reserves** plus **IBNR**. In this demo it equals **IBNR**.
_Avoid_: Provision, liability

**Ultimate**:
The final value of an **Underwriting year**'s claims once every claim has been reported: **Incurred** plus **IBNR**.
_Avoid_: Final losses, projected losses

**Development factor**:
The ratio of **Ultimate** to **Incurred** for an **Underwriting year** at a given maturity. It is selected separately for claim counts and claim amounts, so **IBNR** has both an expected number of claims and an expected amount.
_Avoid_: LDF, multiplier

**Maturity**:
How long claims have had to be reported: the number of whole months from a **Policy**'s departure month to the month of the **Valuation date** (negative if the trip has not started). **Development factors** are selected by maturity, and an **Underwriting year**'s **IBNR** is the sum over its maturities.
_Avoid_: Age, development period

**Expert judgment**:
An assumption an actuary chooses where the data alone cannot decide, such as how an immature **Underwriting year** will develop.
_Avoid_: Override, gut feel

**Exposure**:
The trip cost at risk on a given date: the trip cost of every **Policy** purchased on or before that date whose trip has not ended (return date on or after it). It answers "how exposed are we to an event on that day?"
_Avoid_: Sum insured, exposure premium

**Hurricane loading**:
An **Expert judgment** estimate of a known event's claims that are not yet in **Ultimate**, for claim counts and claim amounts, set per **Policy** at risk in the event's destination region on its date (per unit of **Exposure** for amounts). It is kept separate from the **Development factors** and is not part of Ultimate, A/E or Loss ratio unless "with loading" is stated.
_Avoid_: Cat load, IBNR (it is on top of it)
