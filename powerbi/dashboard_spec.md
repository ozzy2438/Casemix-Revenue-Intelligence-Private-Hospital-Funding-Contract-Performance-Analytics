# Dashboard Specification

## Shared Interaction Model

- Persistent slicers: financial year, hospital, payer and MDC.
- Default scope: latest financial year, all private hospitals, health funds.
- Selecting a payer, DRG or hospital cross-filters every visual on the page.
- Tooltips show volume, revenue, cost, margin, margin percentage and provenance.
- Negative financial values use red; positive outcomes use teal; amber indicates
  commercial attention without confirmed loss.

## Page 1: Executive Summary

**User question:** Where is commercial performance moving and what needs action?

| Position | Visual | Purpose |
|---|---|---|
| Top row | Revenue, margin, separations, CMI, cost KPI cards | 30-second status |
| Middle left | Revenue vs cost trend | Direction and scale |
| Middle right | PVM waterfall | Explain year-on-year revenue movement |
| Bottom left | Payer margin bar | Identify fund-level exposure |
| Bottom right | Top DRG exposure table | Prioritise investigation |

The page should open with no more than five KPI cards and two primary actions:
filter scope or drill into an exposure.

## Page 2: Casemix Explorer

**User question:** Which clinical activity creates value or risk?

- Scatter: cost weight vs margin per separation; bubble size = separations.
- Matrix hierarchy: MDC > DRG > hospital.
- Distribution: same-day, overnight and outlier activity.
- Benchmark: hospital CMI and cost per separation against selected peer scope.
- Drill-through target: DRG detail with trend, payer mix and outlier rate.

## Page 3: Payer & Contract Performance

**User question:** Which fund relationship needs negotiation attention?

- Payer margin and margin percentage ranked bars.
- Cost growth vs benefit growth quadrant.
- Margin-squeeze category matrix by payer and DRG.
- Benefit per episode trend from APRA proxy data.
- Negotiation queue with exposure, evidence and recommended action.

## Page 4: Contract Scenario Modeller

**User question:** What is the commercial impact of proposed terms?

- What-if parameters: DRG indexation, per-diem indexation, daily rate,
  projection horizon and outlier cap.
- Grouped annual margin chart: DRG-based vs per-diem.
- Three-year revenue, margin and DRG advantage cards.
- Outlier shortfall bridge.
- Assumption panel with timestamp and synthetic-data disclosure.

## Human-Centred Design Decisions

- Start with decisions, not source-system terminology.
- Keep financial-year and payer context visible at all times.
- Use colour only for meaning; never rely on colour without a label.
- Place definitions in report-page tooltips rather than permanent screen text.
- Limit executive tables to the top ten actionable rows.
- Preserve a single path from summary to payer, DRG and scenario detail.
