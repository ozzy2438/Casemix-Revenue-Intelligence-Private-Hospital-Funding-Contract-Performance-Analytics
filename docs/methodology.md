# Methodology Documentation

## 1. Synthetic Episode-Level Data Generation

### 1.1 Rationale

Patient-level episode data is not publicly available in Australia due to the Privacy Act 1988. This project generates **synthetically generated, nationally calibrated episode-level data** — the same approach used by professional consulting firms.

### 1.2 Calibration Sources

| Parameter | Source |
|-----------|--------|
| DRG separation distribution | AIHW AR-DRG Data Cubes |
| Cost weights | IHACPA NHCDC |
| Average LOS | IHACPA NHCDC |
| Same-day rates | AIHW AR-DRG Data Cubes |
| Payer mix | APRA Quarterly PHI Statistics |
| NWAU pricing | IHACPA NEP Determination |

### 1.3 Generation Method

For each synthetic episode:
1. **DRG assignment**: Sampled proportional to national separation shares
2. **Cost weight**: `base_weight × lognormal(0, 0.05)` for realistic within-DRG variation
3. **LOS**: `max(0, lognormal(ln(avg_los), 0.4))` calibrated to DRG average
4. **Estimated cost**: `cost_weight × NWAU_price × lognormal(0, 0.08)`
5. **Contracted rate**: `cost × payer_markup × lognormal(0, 0.03)`
6. **Payer assignment**: Probabilistic from APRA-derived payer mix
7. **Outlier flag**: LOS > 3× DRG average

## 2. Price-Volume-Mix (PVM) Variance Decomposition

For DRGs present in both periods:

- **Volume Effect**: `(Q₁ - Q₀) × w₀ᵢ × P₀ᵢ`
- **Mix Effect**: `Q₁ × (w₁ᵢ - w₀ᵢ) × P₀ᵢ`
- **Rate Effect**: `Q₁ × w₁ᵢ × (P₁ᵢ - P₀ᵢ)`

Where Q = total continuing separations, P = revenue per separation, and w = each
DRG's share of continuing separations. New and discontinued DRGs are reported
separately. The bridge is required to reconcile to the observed revenue change,
with only rounding-level residuals.

## 3. Margin Squeeze Analysis

**Squeeze gap** = cost_growth_rate - revenue_growth_rate

| Gap | Category | Action |
|-----|----------|--------|
| > 5% | SEVERE SQUEEZE | Immediate renegotiation |
| 2-5% | MODERATE SQUEEZE | Flag for next cycle |
| 0-2% | MILD SQUEEZE | Monitor |
| -2-0% | STABLE | No action |
| < -2% | IMPROVING | Maintain terms |

## 4. Contract Scenario Modelling

**DRG-based**: Revenue = cost_weight × NWAU_price × (1 + indexation)^year
**Per-Diem**: Revenue = LOS × daily_rate × (1 + indexation)^year

Outlier handling: Episodes > 3× avg LOS capped at 80% of DRG rate.

## 5. Forecasting

**SARIMAX**: Order (1,1,1), seasonal (1,1,1,4), 4-quarter horizon, 95% CI
**Prophet**: Yearly seasonality, linear growth, 95% CI

## 6. Assumptions & Limitations

1. Synthetic data — calibrated but not capturing within-hospital correlations
2. Constant payer mix across years
3. Linear contract indexation
4. No case-level clinical detail beyond DRG partition
5. No geographic cost variation in episode generator
