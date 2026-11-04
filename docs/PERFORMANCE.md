# Performance and indexes

The analytics service limits risk and mapping result sets to 5,000 documents and validates filters before querying.

| Query | Index |
|---|---|
| Risk status and residual-level filtering | `risks.status`, `risks.residual_level` |
| Inherent-level and likelihood/impact filtering | `risks.inherent_level`, `risks.inherent_likelihood`, `risks.inherent_impact` |
| Residual likelihood/impact filtering | `risks.residual_likelihood`, `risks.residual_impact` |
| Owner/source filtering | `risks.owner`, `risks.source` |
| Date trend filtering | `risks.created_at`, `risks.closed_at` |
| Asset joins | `risks.asset_id`, `assets.type` |
| Control-theme joins | `risk_controls.control_id`, `controls.id` |
| Treatment status and overdue queries | `risk_controls.status`, `risk_controls.due_date`, compound `(status, due_date)` |
| Bookmark listing | compound `(analytics_bookmarks.user_id, created_at desc)` |

Indexes are created only by the explicit `scripts/create_indexes.py` operator command.
