# Power BI Delivery Pack

This directory contains the reproducible inputs and design contract for a
four-page Power BI report. The `.pbix` binary is intentionally excluded from
version control; the model can be rebuilt from documented, reviewable assets.

## Build the Extracts

```bash
python -m scripts.build_demo
python -m powerbi.export_data
```

Generated files are written to `powerbi/exports/`:

- dimensions and episode-level fact data
- national costs and PHI benefits
- casemix, DRG and payer analytical views
- PVM, margin squeeze, contract scenario and forecast outputs
- `manifest.json` with row counts and provenance flags

## Create the Report

1. Open Power BI Desktop.
2. Select **Get Data > Text/CSV** and import the files in `powerbi/exports/`.
3. Create relationships using [Data Model](data_model.md).
4. Import [Theme](theme.json) from **View > Themes > Browse for themes**.
5. Add measures from [DAX Measures](measures.dax).
6. Build the four pages in [Dashboard Specification](dashboard_spec.md).
7. Mark `dim_period[quarter_start]` as the date column.
8. Hide technical keys and default-summarisation fields from report view.

## Refresh Contract

The report does not depend on manually edited spreadsheets. Refresh is:

```bash
python -m scripts.build_demo
python -m powerbi.export_data
```

Then select **Refresh** in Power BI Desktop.

## Governance

- `fact_episodes[is_synthetic]` must remain visible in model metadata.
- Public-source lineage is retained in `source` and `source_file`.
- Financial results are demo scenarios, not actual hospital or payer results.
- Production deployment requires governed contract master data and approved
  clinical-cost definitions.
