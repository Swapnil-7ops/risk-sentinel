# Analytics methodology

## KPI definitions

- **Total open risks**: risks whose status is not `Closed` after all selected filters are applied.
- **Critical risks**: filtered risks whose selected score view (`residual` by default, or `inherent`) is `Critical`.
- **Appetite breaches**: filtered risks with a residual score greater than the configured risk appetite threshold.
- **Overdue treatments**: risk-control mappings with a due date before the current calendar date and a status other than `Implemented`. Comparisons are date-to-date, not timestamp-to-timestamp.
- **Control coverage**: the number of distinct Annex A controls with at least one `Implemented` mapping divided by 93, expressed as a percentage. This is coverage, not compliance or a complete gap assessment.

Trend values compare the selected period with the immediately preceding period of equal length. If the preceding period contains no data, the dashboard displays **no prior data** rather than a misleading arrow.

All dashboard calculations are recomputed server-side from the validated filter set. The browser receives one summary response for the dashboard visuals.
