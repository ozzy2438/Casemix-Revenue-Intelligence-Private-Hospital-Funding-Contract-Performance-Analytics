# Data Dictionary

## Dimension Tables

### gold.dim_drg
| Column | Type | Description | Example |
|--------|------|-------------|---------|
| drg_code | VARCHAR (PK) | AR-DRG code | J11B |
| drg_description | VARCHAR | DRG description | Knee Replacement w/o Catastrophic CC |
| mdc_code | VARCHAR | Major Diagnostic Category | MDC 08 |
| mdc_description | VARCHAR | MDC name | Musculoskeletal |
| partition_flag | VARCHAR | A = w/ catastrophic CC, B = w/o | A |
| drg_version | VARCHAR | AR-DRG version | AR-DRG v11.0 |
| same_day_flag | BOOLEAN | Typically same-day | FALSE |
| medical_surgical | VARCHAR | Medical vs Surgical | Surgical |
| effective_from | DATE | Valid from | 2021-07-01 |
| effective_to | DATE | Valid to (NULL=current) | NULL |

**Grain**: One row per DRG code

### gold.dim_hospital
| Column | Type | Description | Example |
|--------|------|-------------|---------|
| hospital_id | INTEGER (PK) | Surrogate key | 1 |
| hospital_name | VARCHAR | Hospital name | SJOG Subiaco |
| state | VARCHAR | State | WA |
| peer_group | VARCHAR | AIHW peer group | Group A - Major |
| sector | VARCHAR | Public/private | private |
| local_hospital_network | VARCHAR | LHN | SJOG WA |
| beds | INTEGER | Licensed beds | 500 |
| effective_from | DATE | Valid from | 2020-07-01 |
| effective_to | DATE | Valid to (NULL=current) | NULL |

### gold.dim_payer
| Column | Type | Description | Example |
|--------|------|-------------|---------|
| payer_id | INTEGER (PK) | Surrogate key | 1 |
| payer_name | VARCHAR | Fund name | Medibank Private |
| payer_type | VARCHAR | health_fund/government/self_funded | health_fund |
| fund_category | VARCHAR | large_fund/mid_fund | large_fund |
| effective_from | DATE | Valid from | 2020-07-01 |
| effective_to | DATE | Valid to (NULL=current) | NULL |

### gold.dim_period
| Column | Type | Description | Example |
|--------|------|-------------|---------|
| period_id | INTEGER (PK) | Surrogate key | 9 |
| financial_year | VARCHAR | AU financial year | 2023-24 |
| quarter | VARCHAR | Q1-Q4 | Q1 |
| quarter_start | DATE | Quarter start | 2023-07-01 |
| quarter_end | DATE | Quarter end | 2023-09-30 |
| is_current | BOOLEAN | Current period flag | TRUE |

## Fact Tables

### gold.fact_episodes
| Column | Type | Description | Example |
|--------|------|-------------|---------|
| episode_id | INTEGER (PK) | Surrogate key | 1001 |
| drg_code | VARCHAR (FK) | → dim_drg | J11B |
| hospital_id | INTEGER (FK) | → dim_hospital | 1 |
| payer_id | INTEGER (FK) | → dim_payer | 1 |
| period_id | INTEGER (FK) | → dim_period | 9 |
| los | DOUBLE | Length of stay (days, 0=same-day) | 5.8 |
| cost_weight | DOUBLE | AR-DRG cost weight | 3.214 |
| nwau | DOUBLE | National Weighted Activity Unit | 3.214 |
| estimated_cost | DOUBLE | Estimated cost (AUD) | 19,693 |
| contracted_rate | DOUBLE | Contracted revenue (AUD) | 20,678 |
| is_same_day | BOOLEAN | Same-day flag | FALSE |
| is_outlier | BOOLEAN | Statistical outlier | FALSE |
| is_synthetic | BOOLEAN | Synthetic flag | TRUE |
| source | VARCHAR | Provenance | synthetic_calibrated |

**Grain**: One row per hospital episode (separation)

### gold.fact_national_costs
| Column | Type | Description | Example |
|--------|------|-------------|---------|
| cost_id | INTEGER (PK) | Surrogate key | 1 |
| drg_code | VARCHAR (FK) | → dim_drg | J11B |
| period_id | INTEGER (FK) | → dim_period | 1 |
| sector | VARCHAR | public/private | public |
| cost_weight | DOUBLE | National cost weight | 3.214 |
| average_los | DOUBLE | National avg LOS | 5.8 |
| cost_per_separation | DOUBLE | Avg cost (AUD) | 19,500 |
| nwau_per_separation | DOUBLE | NWAU per sep | 3.214 |
| separation_count | BIGINT | Total separations | 45,230 |
| total_cost | DOUBLE | Total national cost | 881,985,000 |
| source_file | VARCHAR | Source file | nhcdc_cost_weights_v11.xlsx |

**Grain**: One row per DRG × period × sector
**Source**: IHACPA NHCDC

### gold.fact_phi_benefits
| Column | Type | Description | Example |
|--------|------|-------------|---------|
| benefit_id | INTEGER (PK) | Surrogate key | 1 |
| period_id | INTEGER (FK) | → dim_period | 9 |
| payer_id | INTEGER (FK) | → dim_payer | 1 |
| state | VARCHAR | State | NSW |
| hospital_benefits | DOUBLE | Hospital benefits paid (AUD) | 125,000,000 |
| medical_benefits | DOUBLE | Medical benefits (AUD) | 37,500,000 |
| total_benefits | DOUBLE | Combined benefits (AUD) | 162,500,000 |
| membership_count | BIGINT | Fund members | 525,000 |
| episodes_paid | BIGINT | Episodes paid | 15,750 |
| benefit_per_episode | DOUBLE | Avg benefit per episode | 4,730 |
| source_file | VARCHAR | Source file | phi_quarterly_sep2025.xlsx |

**Grain**: One row per period × payer × state
**Source**: APRA Quarterly PHI Statistics

## Analytics Views

### gold.v_casemix_index
Casemix Index = Total NWAU / Total Separations. CMI > 1.0 = more complex than national average.

### gold.v_drg_revenue
DRG-level revenue, cost, margin, and margin percentage by financial year.

### gold.v_payer_performance
Payer-level separations, cost, revenue, margin by financial year.
