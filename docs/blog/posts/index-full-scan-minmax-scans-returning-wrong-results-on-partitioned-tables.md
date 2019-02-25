---
categories:
  - Oracle
date:
  created: 2019-02-25T04:25:00
description: >-
  Index full scan min/max may return wrong results on partitioned tables due to an Oracle bug.
  Fix control 16346018 can be used to avoid the issue.
tags:
  - 12c
  - Bug
  - Indexing
  - Initialization parameter
---

# Index full scan min/max scans returning wrong results on partitioned tables

A developer has recently shown me an interesting wrong results issue in one of our 12.1.0.2 databases.
Having investigated it, I identified the root cause of that issue and constructed a simple test case that can be used to reproduce it.

<!-- more -->

Let us setup some sample data - a list-partitioned table with just two rows and a global index:

```sql
SQL> create table t (
  2    id,
  3    part_key,
  4    constraint t_pk primary key(id))
  5  partition by list(part_key) (
  6    partition values ('KEY1'),
  7    partition values ('KEY2'))
  8  as
  9  select 1, 'KEY1' from dual union all
 10  select 2, 'KEY2' from dual;

Table created.

SQL>
SQL> col part_key for a8
SQL> select *
  2    from t;

        ID PART_KEY
---------- --------
         1 KEY1
         2 KEY2
```

Here are the queries returning wrong results:

```sql hl_lines="7 15"
SQL> select max(id)
  2    from t
  3   where part_key = 'KEY1';

   MAX(ID)
----------
         2

SQL> select min(id)
  2    from t
  3   where part_key = 'KEY2';

   MIN(ID)
----------
         1
```

They should have returned 1 and 2 correspondingly.
Things definitely went awry.

In such a scenario, I always try to figure out how exactly the optimizer comes up with the result.
The execution plan is a good place to start:

```sql
SQL> select * from table(dbms_xplan.display);

PLAN_TABLE_OUTPUT
-----------------------------------------------------------------------------------------------
Plan hash value: 2094033419

-----------------------------------------------------------------------------------
| Id  | Operation                  | Name | Rows  | Bytes | Cost (%CPU)| Time     |
-----------------------------------------------------------------------------------
|   0 | SELECT STATEMENT           |      |     1 |    19 |     2   (0)| 00:00:01 |
|   1 |  SORT AGGREGATE            |      |     1 |    19 |            |          |
|   2 |   INDEX FULL SCAN (MIN/MAX)| T_PK |     1 |    19 |            |          |
-----------------------------------------------------------------------------------

Note
-----
   - dynamic statistics used: dynamic sampling (level=2)

13 rows selected.
```

Aha!
There is no way for the optimizer to answer that query by using that execution plan.
Where is the `PART_KEY` predicate?
It seems to have been completely lost there.

A quick search on MOS got me a candidate issue: [Bug 22913528 - wrong results with partition pruning and min/max scans (Doc ID 22913528.8)](https://support.oracle.com/rs?type=doc&id=22913528.8)
That document mentions a workaround which I successfully implemented:

```sql
SQL> select /*+ opt_param('_fix_control' '16346018:0')*/
  2         max(id)
  3    from t
  4   where part_key = 'KEY1';

   MAX(ID)
----------
         1

SQL>
```

The plan of that query is below:

```sql hl_lines="12 13"
SQL> select * from table(dbms_xplan.display);

PLAN_TABLE_OUTPUT
-----------------------------------------------------------------------------------------------
Plan hash value: 2831600127

-----------------------------------------------------------------------------------------------
| Id  | Operation              | Name | Rows  | Bytes | Cost (%CPU)| Time     | Pstart| Pstop |
-----------------------------------------------------------------------------------------------
|   0 | SELECT STATEMENT       |      |     1 |    19 |     2   (0)| 00:00:01 |       |       |
|   1 |  SORT AGGREGATE        |      |     1 |    19 |            |          |       |       |
|   2 |   PARTITION LIST SINGLE|      |     1 |    19 |     2   (0)| 00:00:01 |     1 |     1 |
|   3 |    TABLE ACCESS FULL   | T    |     1 |    19 |     2   (0)| 00:00:01 |     1 |     1 |
-----------------------------------------------------------------------------------------------

Note
-----
   - dynamic statistics used: dynamic sampling (level=2)

14 rows selected.
```

The MOS document says that this issue has been fixed in the 12.1.0.2.190115 (Jan 2019) Database Proactive Bundle Patch.
