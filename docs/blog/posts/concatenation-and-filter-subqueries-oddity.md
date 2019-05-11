---
categories:
  - Oracle
date:
  created: 2019-05-11T22:32:00
description: >-
  A case when the concatenation transformation with filter subqueries over-reports executions statistics.
  In particular, plan lines related to filter subqueries are wrongly reported as being executed.
  The new 12.2 OR-Expansion transformation is not susceptible to that issue.
tags:
  - 12c
  - 18c
  - 19c
  - Performance
---

# Concatenation and filter subqueries oddity

While investigating a poor query performance issue, I came across the following Real-Time SQL Monitoring report from a 12.1 database.

<!-- more -->

```sql hl_lines="23"
Global Stats
========================================================================================
| Elapsed |   Cpu   |    IO    | Concurrency | PL/SQL  | Fetch | Buffer | Read | Read  |
| Time(s) | Time(s) | Waits(s) |  Waits(s)   | Time(s) | Calls |  Gets  | Reqs | Bytes |
========================================================================================
|    3041 |     299 |     2742 |        0.00 |      29 |    21 |    27M |  10M |  79GB |
========================================================================================

SQL Plan Monitoring Details (Plan Hash Value=511311330)
========================================================================================================================================================================================================
| Id |                    Operation                     |      Name       |  Rows   | Cost  |   Time    | Start  | Execs |   Rows   | Read  | Read  |  Mem  | Activity |        Activity Detail        |
|    |                                                  |                 | (Estim) |       | Active(s) | Active |       | (Actual) | Reqs  | Bytes | (Max) |   (%)    |          (# samples)          |
========================================================================================================================================================================================================
|  0 | SELECT STATEMENT                                 |                 |         |       |      2822 |    +93 |     1 |     2044 |       |       |       |     1.65 | Cpu (39)                      |
|    |                                                  |                 |         |       |           |        |       |          |       |       |       |          | db file sequential read (9)   |
|  1 |   HASH GROUP BY                                  |                 |       1 |       |         1 |  +2914 |     1 |     2044 |       |       |    1M |          |                               |
|  2 |    CONCATENATION                                 |                 |         |       |      2911 |     +4 |     1 |        0 |       |       |       |          |                               |
|  3 |     FILTER                                       |                 |         |       |           |        |     1 |          |       |       |       |          |                               |
|  4 |      FILTER                                      |                 |         |       |           |        |     1 |          |       |       |       |          |                               |
|  5 |       PARTITION LIST SINGLE                      |                 |       1 |   34M |           |        |       |          |       |       |       |          |                               |
|  6 |        TABLE ACCESS BY LOCAL INDEX ROWID BATCHED | DRIVING_TAB     |       1 |   34M |           |        |       |          |       |       |       |          |                               |
|  7 |         INDEX RANGE SCAN                         | DRIVING_TAB_I   |     36M |  368K |           |        |       |          |       |       |       |          |                               |
|  8 |      INDEX RANGE SCAN                            | DICT_PK         |       1 |     3 |      2911 |     +4 |  334K |     304K |  1169 |   9MB |       |     0.24 | Cpu (5)                       |
|    |                                                  |                 |         |       |           |        |       |          |       |       |       |          | db file sequential read (2)   |
|  9 |     FILTER                                       |                 |         |       |      2911 |     +4 |     1 |    42816 |       |       |       |     0.03 | Cpu (1)                       |
| 10 |      FILTER                                      |                 |         |       |      2911 |     +4 |     1 |     450K |       |       |       |          |                               |
| 11 |       PARTITION LIST SINGLE                      |                 |       1 |   19M |      2911 |     +4 |     1 |     450K |       |       |       |          |                               |
| 12 |        TABLE ACCESS BY LOCAL INDEX ROWID BATCHED | DRIVING_TAB     |       1 |   19M |      2915 |     +0 |     1 |     450K |   10M |  79GB |       |    88.71 | Cpu (72)                      |
|    |                                                  |                 |         |       |           |        |       |          |       |       |       |          | db file parallel read (2453)  |
|    |                                                  |                 |         |       |           |        |       |          |       |       |       |          | db file scattered read (5)    |
|    |                                                  |                 |         |       |           |        |       |          |       |       |       |          | db file sequential read (55)  |
| 13 |         INDEX RANGE SCAN                         | DRIVING_TAB_I   |     20M | 63566 |      2911 |     +4 |     1 |      25M | 78518 | 613MB |       |     8.30 | Cpu (5)                       |
|    |                                                  |                 |         |       |           |        |       |          |       |       |       |          | db file sequential read (237) |
| 14 |      INDEX RANGE SCAN                            | DICT_PK         |       1 |     3 |      2911 |     +4 |  334K |     304K |       |       |       |          |                               |
========================================================================================================================================================================================================
```

It is quite unusual that line 8 has any number of executions and rows at all as there are no rows returned from line 4-7.
It is also suspicious that the certain activity columns precisely matches line 14.

I decided to take a look at that query using row source executions statistics:

```sql hl_lines="12"
----------------------------------------------------------------------------------------------------------------------------------------------------------------
| Id  | Operation                                      | Name            | Starts | E-Rows | A-Rows |   A-Time   | Buffers | Reads  |  OMem |  1Mem | Used-Mem |
----------------------------------------------------------------------------------------------------------------------------------------------------------------
|   0 | SELECT STATEMENT                               |                 |      1 |        |   2044 |00:48:34.11 |      26M|     10M|       |       |          |
|   1 |  HASH GROUP BY                                 |                 |      1 |      1 |   2044 |00:48:34.11 |      26M|     10M|  1553K|   956K| 1364K (0)|
|   2 |   CONCATENATION                                |                 |      1 |        |  42816 |00:44:40.63 |      26M|     10M|       |       |          |
|*  3 |    FILTER                                      |                 |      1 |        |      0 |00:00:00.01 |       0 |      0 |       |       |          |
|*  4 |     FILTER                                     |                 |      1 |        |      0 |00:00:00.01 |       0 |      0 |       |       |          |
|   5 |      PARTITION LIST SINGLE                     |                 |      0 |      1 |      0 |00:00:00.01 |       0 |      0 |       |       |          |
|*  6 |       TABLE ACCESS BY LOCAL INDEX ROWID BATCHED| DRIVING_TAB     |      0 |      1 |      0 |00:00:00.01 |       0 |      0 |       |       |          |
|*  7 |        INDEX RANGE SCAN                        | DRIVING_TAB_I   |      0 |     35M|      0 |00:00:00.01 |       0 |      0 |       |       |          |
|*  8 |     INDEX RANGE SCAN                           | DICT_PK         |    333K|      1 |    304K|00:00:18.49 |    1610K|   1173 |       |       |          |
|*  9 |    FILTER                                      |                 |      1 |        |  42816 |00:44:40.57 |      26M|     10M|       |       |          |
|* 10 |     FILTER                                     |                 |      1 |        |    449K|00:47:48.59 |      25M|     10M|       |       |          |
|  11 |      PARTITION LIST SINGLE                     |                 |      1 |      1 |    449K|00:47:47.97 |      25M|     10M|       |       |          |
|* 12 |       TABLE ACCESS BY LOCAL INDEX ROWID BATCHED| DRIVING_TAB     |      1 |      1 |    449K|00:47:47.34 |      25M|     10M|       |       |          |
|* 13 |        INDEX RANGE SCAN                        | DRIVING_TAB_I   |      1 |     19M|     24M|00:03:59.62 |   79436 |  78518 |       |       |          |
|* 14 |     INDEX RANGE SCAN                           | DICT_PK         |    333K|      1 |    304K|00:00:18.49 |    1610K|   1173 |       |       |          |
----------------------------------------------------------------------------------------------------------------------------------------------------------------
```

Again, it does not make any sense that line 8 is reported as being executed.
The number of logical reads does not add up either.
`A-Time` of `INDEX RANGE SCAN` `DICT_PK` is the same in lines 8 and 14, so that I would chalk it up to a statistics reporting bug.

I constructed the following test case used to reproduce the issue and tested it in 12.2, 18.3, 19.2 with the same results:

```sql
create table t_driving (status char(1), driving_to_inner_id int);
insert into t_driving values ('A', 1);
insert into t_driving values ('B', 2);
create table t_inner(id int);
insert into t_inner select 1 from dual connect by level<=10;

var status varchar2(1)='B'

begin
  for test_rec in (
    select /*+ use_concat(or_predicates(1)) gather_plan_statistics no_unnest(@inner)*/
           *
      from t_driving
     where (:status='B' and status = 'B' or :status='A' and status = 'A')
       and not exists (
             select /*+ qb_name(inner) */
                    null
               from t_inner
              where id = driving_to_inner_id
           )
  )
  loop
    null;
  end loop;
  for plan_rec in (select * from table(dbms_xplan.display_cursor( format=> 'allstats last')))
  loop
    dbms_output.put_line(plan_rec.plan_table_output);
  end loop;
end;
/
```

Here is the output of the last block highlighting the plan execution details:

```sql hl_lines="16"
SQL_ID  4n8swkt3cv3sh, child number 0
-------------------------------------
SELECT /*+ use_concat(or_predicates(1)) gather_plan_statistics
no_unnest(@inner)*/ * FROM T_DRIVING WHERE (:B1 ='B' AND STATUS = 'B'
OR :B1 ='A' AND STATUS = 'A') AND NOT EXISTS ( SELECT /*+
qb_name(inner) */ NULL FROM T_INNER WHERE ID = DRIVING_TO_INNER_ID )
Plan hash value: 3020335025
--------------------------------------------------------------------------------------------
| Id  | Operation            | Name      | Starts | E-Rows | A-Rows |   A-Time   | Buffers |
--------------------------------------------------------------------------------------------
|   0 | SELECT STATEMENT     |           |      1 |        |      1 |00:00:00.01 |      14 |
|   1 |  CONCATENATION       |           |      1 |        |      1 |00:00:00.01 |      14 |
|*  2 |   FILTER             |           |      1 |        |      0 |00:00:00.01 |       0 |
|*  3 |    FILTER            |           |      1 |        |      0 |00:00:00.01 |       0 |
|*  4 |     TABLE ACCESS FULL| T_DRIVING |      0 |      1 |      0 |00:00:00.01 |       0 |
|*  5 |    TABLE ACCESS FULL | T_INNER   |      1 |      1 |      0 |00:00:00.01 |       7 |
|*  6 |   FILTER             |           |      1 |        |      1 |00:00:00.01 |      14 |
|*  7 |    FILTER            |           |      1 |        |      1 |00:00:00.01 |       7 |
|*  8 |     TABLE ACCESS FULL| T_DRIVING |      1 |      1 |      1 |00:00:00.01 |       7 |
|*  9 |    TABLE ACCESS FULL | T_INNER   |      1 |      1 |      0 |00:00:00.01 |       7 |
--------------------------------------------------------------------------------------------
Predicate Information (identified by operation id):
---------------------------------------------------
2 - filter( IS NULL)
3 - filter(:B1='A')
4 - filter("STATUS"='A')
5 - filter("ID"=:B1)
6 - filter( IS NULL)
7 - filter(:B1='B')
8 - filter(("STATUS"='B' AND (LNNVL(:B1='A') OR LNNVL("STATUS"='A'))))
9 - filter("ID"=:B1)
```

The total number of buffers is 14, which is correct.
However, line 5 has also contributed to 7 buffers somehow.
Thus there should have been 21 buffers overall.
If line 4 is not executed, as it has starts 0, how come that line 5 is being executed?

I rechecked all the numbers against `V$SQL_PLAN_STATISTICS_ALL`, `V$SQLAREA_PLAN_HASH` and other views.
The total executions details, such as buffers, were fine - they were all reported as 14.
The only issue was with line 5 - it should have not been reported as being executed or generating any number of logical I/O.
I believe that is a reporting bug - there should be no starts for line 5 at all.

I was curious how new 12.2 OR-Expansion transformation would behave.
Although I knew it could be forced by using the `OR_EXPAND` hint, I was struggling to get it work, so that I had to resort to optimizer traces to find out why my hints were not honored by the optimizer.
I found the following lines in the trace file that helped solve that issue:

``` hl_lines="5"
ORE: Predicate chain after QB validity check - SEL$1
(:B1='B' AND "T_DRIVING"."STATUS"='B' OR :B2='A' AND "T_DRIVING"."STATUS"='A') AND  NOT EXISTS (SELECT /*+ NO_UNNES
T QB_NAME ("INNER") */ 0 FROM "T_INNER" "T_INNER")
ORE: Checking validity of disjunct chain
ORE: Bypassed for disjunct chain: No Index or Partition driver found.
ORE: # conjunction chain - 1
ORE: No state generated.
```

So there is 'No Index or Partition driver found' - that is something that I can work with.
It is interesting enough that the Concatenation transformation does not have those restrictions as far as I am aware.
At least, it can be forced for the same query with the same objects.

I recreated the driving table using the following commands:

```sql
drop table t_driving;
create table t_driving (
  status char(1),
  driving_to_inner_id int)
partition by list(status) (
  partition values ('A'),
  partition values ('B'));
insert into t_driving values ('A', 1);
insert into t_driving values ('B', 2);
```

Then I ran the query below:

```sql
begin
  for test_rec in (
    select /*+ or_expand gather_plan_statistics no_unnest(@inner)*/
           *
      from t_driving
     where (:status='B' and status = 'B' or :status='A' and status = 'A')
       and not exists (
             select /*+ qb_name(inner) */
                    null
               from t_inner
              where id = driving_to_inner_id
           )
  )
  loop
    null;
  end loop;
  for plan_rec in (select * from table(dbms_xplan.display_cursor( format=> 'allstats last')))
  loop
    dbms_output.put_line(plan_rec.plan_table_output);
  end loop;
end;
/
```

It had the following execution plan:

```sql
SQL_ID  16q8nc7mcy3b0, child number 0
-------------------------------------
SELECT /*+ or_expand gather_plan_statistics no_unnest(@inner)*/ * FROM
T_DRIVING WHERE (:B1 ='B' AND STATUS = 'B' OR :B1 ='A' AND STATUS =
'A') AND NOT EXISTS ( SELECT /*+ qb_name(inner) */ NULL FROM T_INNER
WHERE ID = DRIVING_TO_INNER_ID )
Plan hash value: 1055582790
-------------------------------------------------------------------------------------------------------
| Id  | Operation                 | Name            | Starts | E-Rows | A-Rows |   A-Time   | Buffers |
-------------------------------------------------------------------------------------------------------
|   0 | SELECT STATEMENT          |                 |      1 |        |      1 |00:00:00.01 |      44 |
|   1 |  VIEW                     | VW_ORE_95B37148 |      1 |      2 |      1 |00:00:00.01 |      44 |
|   2 |   UNION-ALL               |                 |      1 |        |      1 |00:00:00.01 |      44 |
|*  3 |    FILTER                 |                 |      1 |        |      1 |00:00:00.01 |      44 |
|*  4 |     FILTER                |                 |      1 |        |      1 |00:00:00.01 |      37 |
|   5 |      PARTITION LIST SINGLE|                 |      1 |      1 |      1 |00:00:00.01 |      37 |
|   6 |       TABLE ACCESS FULL   | T_DRIVING       |      1 |      1 |      1 |00:00:00.01 |      37 |
|*  7 |     TABLE ACCESS FULL     | T_INNER         |      1 |      1 |      0 |00:00:00.01 |       7 |
|*  8 |    FILTER                 |                 |      1 |        |      0 |00:00:00.01 |       0 |
|*  9 |     FILTER                |                 |      1 |        |      0 |00:00:00.01 |       0 |
|  10 |      PARTITION LIST SINGLE|                 |      0 |      1 |      0 |00:00:00.01 |       0 |
|* 11 |       TABLE ACCESS FULL   | T_DRIVING       |      0 |      1 |      0 |00:00:00.01 |       0 |
|* 12 |     TABLE ACCESS FULL     | T_INNER         |      0 |      1 |      0 |00:00:00.01 |       0 |
-------------------------------------------------------------------------------------------------------
Predicate Information (identified by operation id):
---------------------------------------------------
3 - filter( IS NULL)
4 - filter(:B1='B')
7 - filter("ID"=:B1)
8 - filter( IS NULL)
9 - filter(:B1='A')
11 - filter((LNNVL(:B1='B') OR LNNVL("STATUS"='B')))
12 - filter("ID"=:B1)
```

Notice that there are no executions in line 10 to 12 - that is how it should be.

**TL;DR**: a Concatenation transformation with filter subqueries may over-report actual execution statistics, so that the totals, such as Buffers, are fine, however, the plan lines related to filter subqueries are reported as being executed and having the same execution statistics as their corresponding lines in other concatenation branches.
Those subqueries are not really executed but just are reported as being so.
Thankfully, the 12.2 OR-Expansion transformation is not susceptible to that issue - the execution statistics are reported back as zero for those subqueries which are not actually executed because they are eliminated in the parent filter branches.

The code is this article has been tested against 12.2, 18.3, and 19.2.
