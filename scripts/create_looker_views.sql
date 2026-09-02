-- Views feeding the Looker Studio manager-level dashboard (Sep 2 milestone).
-- Run via: bq query --project_id=flowmate-ai-506118 --use_legacy_sql=false < scripts/create_looker_views.sql
--
-- Looker Studio works best off a single flat source per chart -- these views
-- pre-aggregate the same signals the Bottleneck Detector agent reasons over
-- (agents/common/bigquery_tool.py), so the manager dashboard tells the same
-- story as the agent without duplicating its query logic by hand in Looker
-- Studio's own UI.

CREATE OR REPLACE VIEW `flowmate-ai-506118.flowmate.sprint_bottleneck_heatmap` AS
SELECT
  t.team,
  t.sprint_id,
  tv.sprint_start_date,
  tv.sprint_end_date,
  COUNT(*) AS ticket_count,
  ROUND(COUNTIF(t.state IN ('Resolved', 'Closed')) / COUNT(*), 3) AS close_rate,
  ROUND(AVG(TIMESTAMP_DIFF(COALESCE(t.closed_date, t.changed_date), t.created_date, HOUR)), 1)
    AS avg_cycle_time_hours,
  COUNTIF(t.is_blocked) AS blocked_count,
  ROUND(
    COUNTIF(t.work_item_type = 'Bug' AND t.state IN ('Resolved', 'Closed'))
      / NULLIF(COUNTIF(t.work_item_type = 'Bug'), 0), 3
  ) AS bug_close_rate,
  -- 0 (healthy) to 1 (at risk): rewards low close rate and any blocked
  -- tickets so a single color scale reads as "how bottlenecked is this
  -- team this sprint" without a viewer needing to reason about 3 metrics.
  ROUND(
    (1 - COUNTIF(t.state IN ('Resolved', 'Closed')) / COUNT(*)) * 0.7
      + LEAST(COUNTIF(t.is_blocked) / COUNT(*), 1) * 0.3,
    3
  ) AS bottleneck_risk_score
FROM `flowmate-ai-506118.flowmate.tickets` t
JOIN `flowmate-ai-506118.flowmate.team_velocity` tv
  ON t.team = tv.team AND t.sprint_id = tv.sprint_id
GROUP BY t.team, t.sprint_id, tv.sprint_start_date, tv.sprint_end_date;

CREATE OR REPLACE VIEW `flowmate-ai-506118.flowmate.reviewer_latency_summary` AS
SELECT
  reviewer,
  team,
  COUNT(*) AS review_count,
  ROUND(AVG(review_latency_hours), 1) AS avg_latency_hours,
  ROUND(COUNTIF(review_status = 'Changes Requested') / COUNT(*), 3) AS changes_requested_rate
FROM `flowmate-ai-506118.flowmate.pr_reviews`
WHERE review_status != 'Pending'
GROUP BY reviewer, team
HAVING COUNT(*) >= 5;

-- Mirrors agents/common/bigquery_tool.py::_bug_close_rate_by_sprint_sql() exactly, so the manager
-- dashboard's trend line and the Bottleneck Detector agent's own reasoning are backed by the same
-- query -- the third engineered pattern (declining recent-sprint Bug close rate) isn't visible in
-- either of the two views above, since both are per-team snapshots rather than a time series.
CREATE OR REPLACE VIEW `flowmate-ai-506118.flowmate.bug_close_rate_trend` AS
SELECT
  t.sprint_id,
  s.sprint_end_date,
  ROUND(COUNTIF(t.state IN ('Resolved', 'Closed')) / COUNT(*), 3) AS bug_close_rate,
  COUNT(*) AS bug_count
FROM `flowmate-ai-506118.flowmate.tickets` t
JOIN (
  SELECT DISTINCT sprint_id, sprint_end_date FROM `flowmate-ai-506118.flowmate.team_velocity`
) s ON s.sprint_id = t.sprint_id
WHERE t.work_item_type = 'Bug'
GROUP BY t.sprint_id, s.sprint_end_date
ORDER BY s.sprint_end_date ASC;
