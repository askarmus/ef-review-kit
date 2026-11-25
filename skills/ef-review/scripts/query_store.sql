/*  EF Review: slow query finder for SQL Server / Azure SQL.  READ-ONLY.
    Needs Query Store ON (SQL Server 2016+ / Azure SQL) and VIEW DATABASE STATE.
    Run in the application database. Paste the result sets back to Claude.
    Adjust @days / @top as needed.                                                  */

SET NOCOUNT ON;
DECLARE @days int = 7, @top int = 25;
DECLARE @since datetimeoffset = DATEADD(day, -@days, SYSDATETIMEOFFSET());

-- 0. Query Store status
SELECT actual_state_desc, readonly_reason, current_storage_size_mb, max_storage_size_mb, query_capture_mode_desc
FROM sys.database_query_store_options;

-- 1. Top queries by average duration
;WITH agg AS (
    SELECT q.query_id, qt.query_sql_text,
           SUM(rs.count_executions)                                              AS execs,
           SUM(rs.avg_duration * rs.count_executions) / NULLIF(SUM(rs.count_executions),0) / 1000.0 AS avg_ms,
           SUM(rs.avg_cpu_time * rs.count_executions) / 1000.0                   AS total_cpu_ms,
           SUM(rs.avg_logical_io_reads * rs.count_executions) / NULLIF(SUM(rs.count_executions),0) AS avg_reads,
           MAX(rs.max_duration) / 1000.0                                         AS max_ms,
           COUNT(DISTINCT p.plan_id)                                             AS plans
    FROM sys.query_store_query q
    JOIN sys.query_store_query_text qt ON qt.query_text_id = q.query_text_id
    JOIN sys.query_store_plan p        ON p.query_id = q.query_id
    JOIN sys.query_store_runtime_stats rs ON rs.plan_id = p.plan_id
    JOIN sys.query_store_runtime_stats_interval i ON i.runtime_stats_interval_id = rs.runtime_stats_interval_id
    WHERE i.start_time >= @since
    GROUP BY q.query_id, qt.query_sql_text
)
SELECT TOP (@top) 'by_avg_duration' AS list, query_id, execs, CAST(avg_ms AS decimal(12,2)) avg_ms,
       CAST(max_ms AS decimal(12,2)) max_ms, CAST(total_cpu_ms AS decimal(14,0)) total_cpu_ms,
       CAST(avg_reads AS decimal(14,0)) avg_reads, plans,
       LEFT(query_sql_text, 4000) AS sql_text
FROM agg ORDER BY avg_ms DESC;

-- 2. Top queries by total CPU (frequent + moderately slow = biggest load)
;WITH agg AS (
    SELECT q.query_id, qt.query_sql_text,
           SUM(rs.count_executions) execs,
           SUM(rs.avg_cpu_time * rs.count_executions) / 1000.0 total_cpu_ms,
           SUM(rs.avg_duration * rs.count_executions) / NULLIF(SUM(rs.count_executions),0) / 1000.0 avg_ms
    FROM sys.query_store_query q
    JOIN sys.query_store_query_text qt ON qt.query_text_id = q.query_text_id
    JOIN sys.query_store_plan p ON p.query_id = q.query_id
    JOIN sys.query_store_runtime_stats rs ON rs.plan_id = p.plan_id
    JOIN sys.query_store_runtime_stats_interval i ON i.runtime_stats_interval_id = rs.runtime_stats_interval_id
    WHERE i.start_time >= @since
    GROUP BY q.query_id, qt.query_sql_text
)
SELECT TOP (@top) 'by_total_cpu' AS list, query_id, execs, CAST(total_cpu_ms AS decimal(14,0)) total_cpu_ms,
       CAST(avg_ms AS decimal(12,2)) avg_ms, LEFT(query_sql_text, 4000) sql_text
FROM agg ORDER BY total_cpu_ms DESC;

-- 3. Same query, very different plans (parameter sniffing / regressions)
SELECT TOP (@top) 'multi_plan' AS list, q.query_id, COUNT(DISTINCT p.plan_id) plans,
       CAST(MIN(rs.avg_duration)/1000.0 AS decimal(12,2)) best_avg_ms,
       CAST(MAX(rs.avg_duration)/1000.0 AS decimal(12,2)) worst_avg_ms,
       LEFT(MAX(qt.query_sql_text), 4000) sql_text
FROM sys.query_store_query q
JOIN sys.query_store_query_text qt ON qt.query_text_id = q.query_text_id
JOIN sys.query_store_plan p ON p.query_id = q.query_id
JOIN sys.query_store_runtime_stats rs ON rs.plan_id = p.plan_id
JOIN sys.query_store_runtime_stats_interval i ON i.runtime_stats_interval_id = rs.runtime_stats_interval_id
WHERE i.start_time >= @since
GROUP BY q.query_id
HAVING COUNT(DISTINCT p.plan_id) > 1 AND MAX(rs.avg_duration) > 3 * NULLIF(MIN(rs.avg_duration),0)
ORDER BY MAX(rs.avg_duration) DESC;

-- 4. EF-tagged queries (TagWith / TagWithCallSite comments)
SELECT TOP (@top) 'ef_tagged' AS list, q.query_id,
       SUM(rs.count_executions) execs,
       CAST(SUM(rs.avg_duration * rs.count_executions) / NULLIF(SUM(rs.count_executions),0) / 1000.0 AS decimal(12,2)) avg_ms,
       LEFT(qt.query_sql_text, 300) tag_and_start
FROM sys.query_store_query q
JOIN sys.query_store_query_text qt ON qt.query_text_id = q.query_text_id
JOIN sys.query_store_plan p ON p.query_id = q.query_id
JOIN sys.query_store_runtime_stats rs ON rs.plan_id = p.plan_id
JOIN sys.query_store_runtime_stats_interval i ON i.runtime_stats_interval_id = rs.runtime_stats_interval_id
WHERE i.start_time >= @since AND qt.query_sql_text LIKE '-- %'
GROUP BY q.query_id, qt.query_sql_text
ORDER BY avg_ms DESC;

-- 5. Missing index suggestions (since last restart; merge overlaps before adding!)
SELECT TOP (@top) 'missing_index' AS list,
       OBJECT_NAME(d.object_id) AS table_name,
       d.equality_columns, d.inequality_columns, d.included_columns,
       s.user_seeks, s.user_scans,
       CAST(s.avg_total_user_cost * s.avg_user_impact * (s.user_seeks + s.user_scans) AS decimal(18,0)) AS impact_score
FROM sys.dm_db_missing_index_details d
JOIN sys.dm_db_missing_index_groups g ON g.index_handle = d.index_handle
JOIN sys.dm_db_missing_index_group_stats s ON s.group_handle = g.index_group_handle
WHERE d.database_id = DB_ID()
ORDER BY impact_score DESC;

-- 6. Unused / write-only indexes (cost on writes, no reads)
SELECT TOP (@top) 'unused_index' AS list, OBJECT_NAME(i.object_id) table_name, i.name index_name,
       us.user_seeks, us.user_scans, us.user_lookups, us.user_updates
FROM sys.indexes i
LEFT JOIN sys.dm_db_index_usage_stats us ON us.object_id = i.object_id AND us.index_id = i.index_id AND us.database_id = DB_ID()
WHERE OBJECTPROPERTY(i.object_id,'IsUserTable') = 1 AND i.type_desc = 'NONCLUSTERED' AND i.is_primary_key = 0 AND i.is_unique = 0
  AND ISNULL(us.user_seeks,0) + ISNULL(us.user_scans,0) + ISNULL(us.user_lookups,0) = 0
ORDER BY ISNULL(us.user_updates,0) DESC;

-- 7. Biggest tables (helps judge EF013 full loads and EF014 Contains sizes)
SELECT TOP (@top) 'table_size' AS list, t.name table_name, SUM(p.rows) row_count
FROM sys.tables t JOIN sys.partitions p ON p.object_id = t.object_id AND p.index_id IN (0,1)
GROUP BY t.name ORDER BY row_count DESC;

-- 8. Compatibility level (relevant for EF Core 8 OPENJSON, EF 10 json type, EF 11 default 160)
SELECT name, compatibility_level FROM sys.databases WHERE database_id = DB_ID();
