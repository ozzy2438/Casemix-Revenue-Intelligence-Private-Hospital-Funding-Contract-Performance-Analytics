# Interview Talking Points

## 30-Second Summary

I built an end-to-end private hospital revenue intelligence solution around the
daily decisions of a Health Funds Team. It combines IHACPA costing, AIHW
activity and APRA private health insurance inputs in DuckDB, creates
privacy-safe calibrated episodes, and turns them into PVM analysis, contract
scenarios, forecasting and a self-service Streamlit interface.

## Five-Minute Walkthrough

1. **Business problem:** revenue can rise while commercial performance
   deteriorates, so executives need the movement split into volume, casemix and
   rate.
2. **Data constraint:** real patient episodes are private. I handled this
   transparently with synthetic records calibrated to public national
   distributions and explicit lineage flags.
3. **Data product:** a DuckDB star schema supports DRG, hospital, payer and time
   analysis with automated quality gates.
4. **Commercial result:** the scenario model shows why DRG-based reimbursement
   and outlier protection matter more than nominal indexation for complex cases.
5. **Delivery:** leaders can filter performance and change contract assumptions
   without touching Python or SQL.

## Questions to Expect

### Why synthetic data?

Episode-level hospital data is not public. Using calibrated synthetic episodes
protects privacy, preserves a realistic analytical grain and makes the project
fully reproducible. I clearly separate real public source inputs from simulated
records.

### Why DuckDB?

The workload is analytical, columnar and local. DuckDB gives fast SQL over
medium-sized datasets without infrastructure overhead, while preserving a
model that can be migrated to an enterprise warehouse.

### How would this move into production?

Replace local files with governed source feeds, move gold models to the
organisation's warehouse, map payer and contract master data, validate outputs
with Finance and Clinical Costing, and publish certified Power BI semantic
models with role-based access.

### What would you validate with stakeholders?

Contract inclusions, exclusions, outlier rules, escalation timing, bundled
services, clinical-cost allocations, payer attribution and the definition of
commercial margin.

### What is the key limitation?

The model demonstrates method and decision workflow, not actual hospital-group
economics. Local clinical practice, contract clauses and cost allocation rules
would materially affect production results.
