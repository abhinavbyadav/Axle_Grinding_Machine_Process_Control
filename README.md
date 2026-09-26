# Axle Grinding Process Monitor

Upload an Excel workbook to review left and right axle measurements with three-sigma control charts. The app reports each measurement's mean and sample standard deviation, highlights points beyond the control limits, and flags sustained monotonic trends.

## Workbook format

Include these column headers in the worksheet: `serial number`, `left`, and `right`. Headers are case-insensitive. Rows without a serial number or numeric left/right values are omitted from the analysis. If the workbook has multiple sheets, select the worksheet to analyze in the app.

The control limits are calculated independently for left and right as mean ± 3 times the sample standard deviation. A sequence of seven consecutive increases or decreases is flagged as a possible trend. Any point beyond a control limit triggers a recommendation to stop the machine and hand the process over to maintenance; a trend without an outlier prompts a process check and closer monitoring.

## Run locally

Install `uv` if it is not already available, then run:

```
uv sync
uv run streamlit run streamlit_app.py
```
