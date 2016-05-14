---
categories:
  - Oracle
date:
  created: 2015-11-30T12:53:00
  updated: 2016-05-14T12:30:00
description: >-
  An investigation why V$SQL_PLAN_MONITOR.STARTS is higher than expected.
  It turns out to be due to nested loop join batching and table prefetching.
tags:
  - 12c
  - Initialization parameter
---

# `V$SQL_PLAN_MONITOR.STARTS` is higher than expected due to NLJ batching/Prefetching

Recently one of our developers asked me to explain why `V$SQL_PLAN_MONITOR.STARTS` is higher than expected for one particular query.

<!-- more -->

Here is a problem query (some columns are hidden to preserve readability):

```sql
SQL Plan Monitoring Details (Plan Hash Value=40624586)
================================================================================================================================================
| Id |                Operation                |        Name        | Execs |   Rows   | Read  | Read  | Activity |      Activity Detail       |
|    |                                         |                    |       | (Actual) | Reqs  | Bytes |   (%)    |        (# samples)         |
================================================================================================================================================
|  0 | SELECT STATEMENT                        |                    |     1 |        0 |       |       |          |                            |
|  1 |   NESTED LOOPS                          |                    |     1 |        0 |       |       |          |                            |
|  2 |    NESTED LOOPS                         |                    |     1 |    62594 |       |       |          |                            |
|  3 |     TABLE ACCESS BY INDEX ROWID BATCHED | MAIN_TABLE         |     1 |    62594 | 22777 | 178MB |    25.89 | Cpu (1)                    |
|    |                                         |                    |       |          |       |       |          | db file parallel read (28) |
|  4 |      INDEX RANGE SCAN                   | MAIN_TABLE_I       |     1 |    62594 |    25 | 200KB |          |                            |
|  5 |     INDEX UNIQUE SCAN                   | CHILD_TABLE_PK     |  109K |    62594 | 63798 | 498MB |    71.43 | Cpu (2)                    |
|    |                                         |                    |       |          |       |       |          | db file parallel read (78) |
|  6 |    TABLE ACCESS BY INDEX ROWID          | CHILD_TABLE        |  105K |        0 |  1402 |  11MB |     1.79 | db file parallel read (2)  |
================================================================================================================================================
```

You can see that the query obtained 62K rows at step 3, but notice a number of "Execs" at step 5: 109K. It is almost twice as higher than 62K.
The number of rows (`Rows (Actual)`) is correct, though.
I checked the relevant columns in the `V$SQL_PLAN_MONITOR` view (`STARTS/OUTPUT_ROWS`) and verified that there is no discrepancy between the `V$SQL_PLAN_MONITOR` view and the `DBMS_SQLTUNE.REPORT_SQL_MONITOR` output.

I investigated this issue further and constructed a simple test case which can be used to reproduce the issue.

```sql
SQL> create table fact
  2  as
  3  select date '2015-08-01' + trunc(level/4)/86400 fact_date,
  4         lpad('x', 240, 'x') padding,
  5         mod(level, 100000) dim_id
  6    from dual
  7    connect by level<=4*86400;

Table created.

SQL>
SQL> exec dbms_stats.gather_table_stats( '', 'fact')

PL/SQL procedure successfully completed.

SQL>
SQL> create table dim
  2  as
  3  select trunc(dbms_random.value(1,100000)) id,
  4         lpad('x', 340, 'x') padding
  5    from dual
  6    connect by level<=2*86400;

Table created.

SQL>
SQL> create index dim_i on dim(id);

Index created.

SQL>
SQL> exec dbms_stats.gather_table_stats( '', 'dim')

PL/SQL procedure successfully completed.
```

The script creates two tables, `FACT` and `DIM`, populates them with sample data, and gathers statistics.
Let us flush the buffer cache and execute the test query:

```sql hl_lines="1 6"
SQL> alter system flush buffer_cache;

System altered.

SQL>
SQL> select /*+ monitor leading(f) use_nl(d) full(f)*/
  2         count(f.padding),
  3         count(d.padding)
  4    from fact f,
  5         dim d
  6   where f.fact_date between to_date('01.08.2015 12:00', 'dd.mm.yyyy hh24:mi') and to_date('01.08.2015 12:10', 'dd.mm.yyyy hh24:mi')
  7     and d.id = f.dim_id;


COUNT(F.PADDING) COUNT(D.PADDING)
---------------- ----------------
            4214             4214

1 row selected.

SQL>
```

Obtain the `DBMS_SQLTUNE` report for the last query:

??? Show

    ```sql hl_lines="23 25"
    SQL> select dbms_sqltune.report_sql_monitor from dual;


    REPORT_SQL_MONITOR
    -----------------------------------------------------------------------------------------------------------------------------------------------------------
    SQL Monitoring Report

    SQL Text
    ------------------------------
    select /*+ monitor leading(f) use_nl(d) full(f)*/ count(f.padding), count(d.padding) from fact f, dim d where f.fact_date between to_date('01.08.2015 12:00

    .. skip..

    SQL Plan Monitoring Details (Plan Hash Value=85884857)
    ===========================================================================================================================================================
    | Id |            Operation            | Name  |  Rows   | Cost  |   Time    | Start  | Execs |   Rows   | Read | Read  | Activity |   Activity Detail    |
    |    |                                 |       | (Estim) |       | Active(s) | Active |       | (Actual) | Reqs | Bytes |   (%)    |     (# samples)      |
    ===========================================================================================================================================================
    |  0 | SELECT STATEMENT                |       |         |       |        10 |    +14 |     1 |        1 |      |       |          |                      |
    |  1 |   SORT AGGREGATE                |       |       1 |       |        10 |    +14 |     1 |        1 |      |       |          |                      |
    |  2 |    NESTED LOOPS                 |       |         |       |        10 |    +14 |     1 |     4214 |      |       |          |                      |
    |  3 |     NESTED LOOPS                |       |    5025 | 11890 |        10 |    +14 |     1 |     4214 |      |       |          |                      |
    |  4 |      TABLE ACCESS FULL          | FACT  |    2408 |  3535 |        23 |     +1 |     1 |     2404 |  109 | 100MB |     8.70 | Cpu (1)              |
    |    |                                 |       |         |       |           |        |       |          |      |       |          | direct path read (1) |
    |  5 |      INDEX RANGE SCAN           | DIM_I |       2 |     1 |        10 |    +14 |  2539 |     4214 |  562 |   4MB |          |                      |
    |  6 |     TABLE ACCESS BY INDEX ROWID | DIM   |       2 |     4 |        22 |     +2 |  7582 |     4214 | 2810 |  22MB |    91.30 | Cpu (21)             |
    ===========================================================================================================================================================
    ```

Thus, the issue was reproduced: step 4 of the plan generated 2402 rows, but the number of executions at line 5 is 2539 which is slightly greater than 2402.
It was not by accident that I flushed the buffer cache before executing the query as it can be seen further.

If I run the same query again, the `DBMS_SQLTUNE.REPORT_SQL_MONITOR` report shows that the number of executions in line 5 equals to the number of rows in line 4:

```sql hl_lines="10 11"
SQL Plan Monitoring Details (Plan Hash Value=85884857)
======================================================================================================================================================
| Id |            Operation            | Name  |  Rows   | Cost  |   Time    | Start  | Execs |   Rows   | Read | Read  | Activity | Activity Detail |
|    |                                 |       | (Estim) |       | Active(s) | Active |       | (Actual) | Reqs | Bytes |   (%)    |   (# samples)   |
======================================================================================================================================================
|  0 | SELECT STATEMENT                |       |         |       |         1 |     +0 |     1 |        1 |      |       |          |                 |
|  1 |   SORT AGGREGATE                |       |       1 |       |         1 |     +0 |     1 |        1 |      |       |          |                 |
|  2 |    NESTED LOOPS                 |       |         |       |         1 |     +0 |     1 |     4214 |      |       |          |                 |
|  3 |     NESTED LOOPS                |       |    5025 | 11890 |         1 |     +0 |     1 |     4214 |      |       |          |                 |
|  4 |      TABLE ACCESS FULL          | FACT  |    2408 |  3535 |         1 |     +0 |     1 |     2404 |  108 | 100MB |          |                 |
|  5 |      INDEX RANGE SCAN           | DIM_I |       2 |     1 |         1 |     +0 |  2404 |     4214 |      |       |          |                 |
|  6 |     TABLE ACCESS BY INDEX ROWID | DIM   |       2 |     4 |         1 |     +0 |  4214 |     4214 |      |       |          |                 |
======================================================================================================================================================
```

That makes me think that the difference between executions and rows were caused by nested loop join batching and table prefetching.
Is it possible to prove this?

First, let us see how the `physical reads cache prefetch` statistic gets changed after executing the query:

```sql
SQL> select n.name, s.value
  2    from v$statname n, v$mystat s
  3   where n.name like '%prefetch%'
  4     and s.statistic#=n.statistic#
  5     and s.value>0
  6   order by n.name;


NAME                                VALUE
------------------------------ ----------
physical reads cache prefetch      127987

1 row selected.

SQL>
SQL> select /*+ monitor leading(f) use_nl(d) full(f)*/
  2         count(f.padding),
  3         count(d.padding)
  4    from fact f,
  5         dim d
  6   where f.fact_date between to_date('01.08.2015 12:00', 'dd.mm.yyyy hh24:mi') and to_date('01.08.2015 12:10', 'dd.mm.yyyy hh24:mi')
  7     and d.id = f.dim_id;


COUNT(F.PADDING) COUNT(D.PADDING)
---------------- ----------------
            4214             4214

1 row selected.

SQL>
SQL> select n.name, s.value
  2    from v$statname n, v$mystat s
  3   where n.name like '%prefetch%'
  4     and s.statistic#=n.statistic#
  5     and s.value>0
  6   order by n.name;


NAME                                VALUE
------------------------------ ----------
physical reads cache prefetch      131321

1 row selected.
```

The `physical reads cache prefetch` statistic gets increased by 3334 blocks (131321-127987).

Secondly, once `nls_batching` is disabled, there is no difference between executions and rows:

??? Show

    ```sql
    SQL> alter system flush buffer_cache;

    System altered.

    SQL>
    SQL> select n.name, s.value
      2    from v$statname n, v$mystat s
      3   where n.name like '%prefetch%'
      4     and s.statistic#=n.statistic#
      5     and s.value>0
      6   order by n.name;


    NAME                                VALUE
    ------------------------------ ----------
    physical reads cache prefetch      137989

    1 row selected.

    SQL>
    SQL> select /*+ monitor leading(f) use_nl(d) full(f) opt_param('_nlj_batching_enabled' 0)*/
      2         count(f.padding),
      3         count(d.padding)
      4    from fact f,
      5         dim d
      6   where f.fact_date between to_date('01.08.2015 12:00', 'dd.mm.yyyy hh24:mi') and to_date('01.08.2015 12:10', 'dd.mm.yyyy hh24:mi')
      7     and d.id = f.dim_id;


    COUNT(F.PADDING) COUNT(D.PADDING)
    ---------------- ----------------
                4214             4214

    1 row selected.

    SQL>
    SQL> select n.name, s.value
      2    from v$statname n, v$mystat s
      3   where n.name like '%prefetch%'
      4     and s.statistic#=n.statistic#
      5     and s.value>0
      6   order by n.name;


    NAME                                VALUE
    ------------------------------ ----------
    physical reads cache prefetch      137989

    1 row selected.

    SQL>
    SQL> select dbms_sqltune.report_sql_monitor from dual;


    REPORT_SQL_MONITOR
    -----------------------------------------------------------------------------------------------------------------------------------------------------------------
    SQL Monitoring Report

    SQL Text
    ------------------------------
    select /*+ monitor leading(f) use_nl(d) full(f) opt_param('_nlj_batching_enabled' 0)*/ count(f.padding), count(d.padding) from fact f, dim d where f.fact_date be
     and d.id = f.dim_id

    .. skip ..

    SQL Plan Monitoring Details (Plan Hash Value=1381503666)
    =================================================================================================================================================================
    | Id |           Operation            | Name  |  Rows   | Cost  |   Time    | Start  | Execs |   Rows   | Read | Read  | Activity |       Activity Detail       |
    |    |                                |       | (Estim) |       | Active(s) | Active |       | (Actual) | Reqs | Bytes |   (%)    |         (# samples)         |
    =================================================================================================================================================================
    |  0 | SELECT STATEMENT               |       |         |       |         1 |     +2 |     1 |        1 |      |       |          |                             |
    |  1 |   SORT AGGREGATE               |       |       1 |       |         1 |     +2 |     1 |        1 |      |       |          |                             |
    |  2 |    TABLE ACCESS BY INDEX ROWID | DIM   |       2 |     4 |         2 |     +1 |     1 |     4214 | 3360 |  26MB |   100.00 | db file sequential read (2) |
    |  3 |     NESTED LOOPS               |       |    5025 | 11890 |         1 |     +2 |     1 |     6619 |      |       |          |                             |
    |  4 |      TABLE ACCESS FULL         | FACT  |    2408 |  3535 |         1 |     +2 |     1 |     2404 |  109 | 100MB |          |                             |
    |  5 |      INDEX RANGE SCAN          | DIM_I |       2 |     1 |         1 |     +2 |  2404 |     4214 |   12 | 98304 |          |                             |
    =================================================================================================================================================================


    1 row selected.
    ```

Alternatively, to obtain a classic nested loop join plan, the `no_nlj_prefetch` hint can be added:

??? Show

    ```sql

    SQL> alter system flush buffer_cache;

    System altered.

    SQL>
    SQL> select n.name, s.value
      2    from v$statname n, v$mystat s
      3   where n.name like '%prefetch%'
      4     and s.statistic#=n.statistic#
      5     and s.value>0
      6   order by n.name;


    NAME                                VALUE
    ------------------------------ ----------
    physical reads cache prefetch      137989

    1 row selected.

    SQL>
    SQL> select /*+ monitor leading(f) use_nl(d) full(f) opt_param('_nlj_batching_enabled' 0) no_nlj_prefetch(d)*/
      2         count(f.padding),
      3         count(d.padding)
      4    from fact f,
      5         dim d
      6   where f.fact_date between to_date('01.08.2015 12:00', 'dd.mm.yyyy hh24:mi') and to_date('01.08.2015 12:10', 'dd.mm.yyyy hh24:mi')
      7     and d.id = f.dim_id;


    COUNT(F.PADDING) COUNT(D.PADDING)
    ---------------- ----------------
                4214             4214

    1 row selected.

    SQL>
    SQL> select n.name, s.value
      2    from v$statname n, v$mystat s
      3   where n.name like '%prefetch%'
      4     and s.statistic#=n.statistic#
      5     and s.value>0
      6   order by n.name;


    NAME                                VALUE
    ------------------------------ ----------
    physical reads cache prefetch      137989

    1 row selected.

    SQL>
    SQL> select dbms_sqltune.report_sql_monitor from dual;


    REPORT_SQL_MONITOR
    ------------------------------------------------------------------------------------------------------------------------------------------------------------------
    SQL Monitoring Report

    SQL Text
    ------------------------------
    select /*+ monitor leading(f) use_nl(d) full(f) opt_param('_nlj_batching_enabled' 0) no_nlj_prefetch(d)*/ count(f.padding), count(d.padding) from fact f, dim d wh
    d.mm.yyyy hh24:mi') and d.id = f.dim_id

    .. skip ..

    SQL Plan Monitoring Details (Plan Hash Value=676372893)
    ==================================================================================================================================================================
    | Id |            Operation            | Name  |  Rows   | Cost  |   Time    | Start  | Execs |   Rows   | Read | Read  | Activity |       Activity Detail       |
    |    |                                 |       | (Estim) |       | Active(s) | Active |       | (Actual) | Reqs | Bytes |   (%)    |         (# samples)         |
    ==================================================================================================================================================================
    |  0 | SELECT STATEMENT                |       |         |       |         1 |     +2 |     1 |        1 |      |       |          |                             |
    |  1 |   SORT AGGREGATE                |       |       1 |       |         1 |     +2 |     1 |        1 |      |       |          |                             |
    |  2 |    NESTED LOOPS                 |       |    5025 | 11890 |         1 |     +2 |     1 |     4214 |      |       |          |                             |
    |  3 |     TABLE ACCESS FULL           | FACT  |    2408 |  3535 |         1 |     +2 |     1 |     2404 |  109 | 100MB |          |                             |
    |  4 |     TABLE ACCESS BY INDEX ROWID | DIM   |       2 |     4 |         2 |     +2 |  2404 |     4214 | 3360 |  26MB |    66.67 | Cpu (1)                     |
    |    |                                 |       |         |       |           |        |       |          |      |       |          | db file sequential read (1) |
    |  5 |      INDEX RANGE SCAN           | DIM_I |       2 |     1 |         1 |     +2 |  2404 |     4214 |   12 | 98304 |          |                             |
    ==================================================================================================================================================================
    ```

I searched for similar issues on MOS and found [Bug 13634445 : V$SQL\_PLAN\_MONITOR AND NL BATCHING IN 11G](https://support.oracle.com/rs?type=bug&id=13634445) which has status 92 "Closed, Not a Bug".

Another interesting observation is that by adding the `gather_plan_statistics` hint  the prefetching is disabled for the query resolving the `V$SQL_PLAN_MONITOR` "discrepancy".

??? Show

    ```sql

    SQL> alter system flush buffer_cache;

    System altered.

    SQL>
    SQL> select /*+ monitor leading(f) use_nl(d) full(f) gather_plan_statistics*/
      2         count(f.padding),
      3         count(d.padding)
      4    from fact f,
      5         dim d
      6   where f.fact_date between to_date('01.08.2015 12:00', 'dd.mm.yyyy hh24:mi') and to_date('01.08.2015 12:10', 'dd.mm.yyyy hh24:mi')
      7     and d.id = f.dim_id;


    COUNT(F.PADDING) COUNT(D.PADDING)
    ---------------- ----------------
                4214             4214

    1 row selected.

    SQL>
    SQL> select dbms_sqltune.report_sql_monitor from dual;


    REPORT_SQL_MONITOR
    ------------------------------------------------------------------------------------------------------------------------------------------------------------------
    SQL Monitoring Report

    SQL Text
    ------------------------------
    select /*+ monitor leading(f) use_nl(d) full(f) gather_plan_statistics*/ count(f.padding), count(d.padding) from fact f, dim d where f.fact_date between to_date('
    dim_id

    ..skip..

    SQL Plan Monitoring Details (Plan Hash Value=85884857)
    ==================================================================================================================================================================
    | Id |            Operation            | Name  |  Rows   | Cost  |   Time    | Start  | Execs |   Rows   | Read | Read  | Activity |       Activity Detail       |
    |    |                                 |       | (Estim) |       | Active(s) | Active |       | (Actual) | Reqs | Bytes |   (%)    |         (# samples)         |
    ==================================================================================================================================================================
    |  0 | SELECT STATEMENT                |       |         |       |         8 |     +2 |     1 |        1 |      |       |          |                             |
    |  1 |   SORT AGGREGATE                |       |       1 |       |         8 |     +2 |     1 |        1 |      |       |          |                             |
    |  2 |    NESTED LOOPS                 |       |         |       |         8 |     +2 |     1 |     4214 |      |       |          |                             |
    |  3 |     NESTED LOOPS                |       |    5025 | 11890 |         8 |     +2 |     1 |     4214 |      |       |          |                             |
    |  4 |      TABLE ACCESS FULL          | FACT  |    2408 |  3535 |         9 |     +1 |     1 |     2404 |  109 | 100MB |    11.11 | direct path read (1)        |
    |  5 |      INDEX RANGE SCAN           | DIM_I |       2 |     1 |         8 |     +2 |  2404 |     4214 |   12 | 98304 |          |                             |
    |  6 |     TABLE ACCESS BY INDEX ROWID | DIM   |       2 |     4 |         8 |     +2 |  4214 |     4214 | 3360 |  26MB |    88.89 | db file sequential read (8) |
    ==================================================================================================================================================================
    ```
