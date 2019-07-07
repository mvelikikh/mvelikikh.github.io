---
categories:
  - Oracle
date:
  created: 2019-07-07T01:05:00
description: >-
  An example when filter pushdown with lateral views leads to poor performance.
  Two workarounds are shown: outer join the lateral view and evaluate the filter condition as early as possible, or set _optimizer_filter_pushdown to false.
tags:
  - 19c
  - Initialization parameter
  - Performance
---

# Lateral views and filter predicate pushdown

That is another optimizer issue I came across this week while working with developers on tuning application queries.

<!-- more -->

Let us create two tables for this demo:

```sql
SQL> create table t_parent
  2  as
  3  select level id
  4    from dual
  5    connect by level<=10;

Table created.

SQL>
SQL> alter table t_parent
  2    add constraint t_parent_pk primary key(id);

Table altered.

SQL>
SQL> create table t_child
  2  as
  3  select level parent_id, dummy a, dummy b
  4    from dual
  5    connect by level<=10;

Table created.

SQL>
SQL> alter table t_child
  2    add constraint t_child_parent_fk foreign key(parent_id) references t_parent;

Table altered.

SQL>
SQL> create index t_child_parent_fk_i on t_child(parent_id);

Index created.
```

The following query was run by the application (it is an oversimplified version of the actual query):

```sql
select id,
       (select count(a) from t_child where parent_id = id) a_count,
       (select count(b) from t_child where parent_id = id) b_count
  from t_parent
 where 1 = :need_to_run;
```

The variable `NEED_TO_RUN` is to define whether the actual query should be executed.
The query was coming from an APEX application.
When the APEX page loads, it sets that `NEED_TO_RUN` variable to 0 or `NULL` and fires the query - it is not supposed to return anything.
Only after the user clicks on a certain tab, it leads to setting that `NEED_TO_RUN` variable to 1 and the query is re-executed - this time it might return some rows.

Let us see how it works:

```sql hl_lines="36 45"
SQL> var need_to_run number
SQL>
SQL> select /*+ gather_plan_statistics*/
  2         id,
  3         (select count(a) from t_child where parent_id = id) a_count,
  4         (select count(b) from t_child where parent_id = id) b_count
  5    from t_parent
  6   where 1 = :need_to_run;

no rows selected

SQL>
SQL> select * from table(dbms_xplan.display_cursor( format=> 'allstats last'));

PLAN_TABLE_OUTPUT
-------------------------------------------------------------------------------------------------------------------
SQL_ID  bk2mgzbdury0m, child number 0
-------------------------------------
select /*+ gather_plan_statistics*/        id,        (select count(a)
from t_child where parent_id = id) a_count,        (select count(b)
from t_child where parent_id = id) b_count   from t_parent  where 1 =
:need_to_run

Plan hash value: 2339616900

------------------------------------------------------------------------------------------------------------
| Id  | Operation                            | Name                | Starts | E-Rows | A-Rows |   A-Time   |
------------------------------------------------------------------------------------------------------------
|   0 | SELECT STATEMENT                     |                     |      1 |        |      0 |00:00:00.01 |
|   1 |  SORT AGGREGATE                      |                     |      0 |      1 |      0 |00:00:00.01 |
|   2 |   TABLE ACCESS BY INDEX ROWID BATCHED| T_CHILD             |      0 |      1 |      0 |00:00:00.01 |
|*  3 |    INDEX RANGE SCAN                  | T_CHILD_PARENT_FK_I |      0 |      1 |      0 |00:00:00.01 |
|   4 |  SORT AGGREGATE                      |                     |      0 |      1 |      0 |00:00:00.01 |
|   5 |   TABLE ACCESS BY INDEX ROWID BATCHED| T_CHILD             |      0 |      1 |      0 |00:00:00.01 |
|*  6 |    INDEX RANGE SCAN                  | T_CHILD_PARENT_FK_I |      0 |      1 |      0 |00:00:00.01 |
|*  7 |  FILTER                              |                     |      1 |        |      0 |00:00:00.01 |
|   8 |   INDEX FULL SCAN                    | T_PARENT_PK         |      0 |     10 |      0 |00:00:00.01 |
------------------------------------------------------------------------------------------------------------

Predicate Information (identified by operation id):
---------------------------------------------------

   3 - access("PARENT_ID"=:B1)
   6 - access("PARENT_ID"=:B1)
   7 - filter(1=:NEED_TO_RUN)


30 rows selected.
```

Oracle just evaluates the filter condition in line 7 and does not go any further.
The query is in fact accesses the `T_CHILD` table twice using the same access method, so that I suggested instead of querying it twice to query it just once.
The whole query was a little bit complex with several outer joins and a lateral view seemed to be a good fit.

The same query rewritten for using a lateral view is below:

```sql hl_lines="36 45"
SQL> select /*+ gather_plan_statistics*/p.id,
  2         c.a_count,
  3         c.b_count
  4    from t_parent p,
  5         lateral(
  6           select count(a) a_count,
  7                  count(b) b_count
  8             from t_child
  9            where parent_id = p.id
 10         ) c
 11   where 1 = :need_to_run;

no rows selected

SQL>
SQL> select * from table(dbms_xplan.display_cursor( format=> 'allstats last'));

PLAN_TABLE_OUTPUT
---------------------------------------------------------------------------------------------------------------------------
SQL_ID  g6pqun59pf178, child number 0
-------------------------------------
select /*+ gather_plan_statistics*/p.id,        c.a_count,
c.b_count   from t_parent p,        lateral(          select count(a)
a_count,                 count(b) b_count            from t_child
    where parent_id = p.id        ) c  where 1 = :need_to_run

Plan hash value: 1581593935

-------------------------------------------------------------------------------------------------------------------------
| Id  | Operation                               | Name                | Starts | E-Rows | A-Rows |   A-Time   | Buffers |
-------------------------------------------------------------------------------------------------------------------------
|   0 | SELECT STATEMENT                        |                     |      1 |        |      0 |00:00:00.01 |       5 |
|   1 |  NESTED LOOPS                           |                     |      1 |     10 |      0 |00:00:00.01 |       5 |
|   2 |   INDEX FULL SCAN                       | T_PARENT_PK         |      1 |     10 |     10 |00:00:00.01 |       1 |
|   3 |   VIEW                                  | VW_LAT_A18161FF     |     10 |      1 |      0 |00:00:00.01 |       4 |
|*  4 |    FILTER                               |                     |     10 |        |      0 |00:00:00.01 |       4 |
|   5 |     SORT AGGREGATE                      |                     |     10 |      1 |     10 |00:00:00.01 |       4 |
|   6 |      TABLE ACCESS BY INDEX ROWID BATCHED| T_CHILD             |     10 |      1 |     10 |00:00:00.01 |       4 |
|*  7 |       INDEX RANGE SCAN                  | T_CHILD_PARENT_FK_I |     10 |      1 |     10 |00:00:00.01 |       3 |
-------------------------------------------------------------------------------------------------------------------------

Predicate Information (identified by operation id):
---------------------------------------------------

   4 - filter(1=:NEED_TO_RUN)
   7 - access("PARENT_ID"="P"."ID")


28 rows selected.
```

There are a few remarkable things happened here:

- The filter is pushed down to the lateral view
- Both `T_PARENT_TABLE` and `T_CHILD` tables are accessed first, then the filter is evaluated
- Even when we have that filter in line 4, why bother to run any rowsources beneath it?

In case of my real query, that was a drastic change causing a severe performance impact.

The query with a lateral view was transformed into this:

```sql hl_lines="8"
Final query after transformations:******* UNPARSED QUERY IS *******
SELECT "P"."ID" "ID","VW_LAT_A18161FF"."A_COUNT_0" "A_COUNT","VW_LAT_A18161FF"."B_COUNT_1" "B_COUNT"
  FROM "TC"."T_PARENT" "P",
       LATERAL( (
         SELECT COUNT("T_CHILD"."A") "A_COUNT_0",COUNT("T_CHILD"."B") "B_COUNT_1"
           FROM "TC"."T_CHILD" "T_CHILD"
          WHERE "T_CHILD"."PARENT_ID"="P"."ID"
         HAVING 1=:B1)) "VW_LAT_A18161FF"
```

Hence, that filter `1 = :NEED_TO_RUN` has been pushed down to that lateral view and became the `HAVING 1=:B1` condition.

The solution is quite simple.
The query has been rewritten like this:

```sql hl_lines="10"
select /*+ gather_plan_statistics*/p.id,
       c.a_count,
       c.b_count
  from t_parent p,
       lateral(
         select count(a) a_count,
                count(b) b_count
           from t_child
          where parent_id = p.id
       )(+) c
 where 1 = :need_to_run;
```

It has the following execution plan in which the filter predicate is evaluated as early as possible:

```sql hl_lines="5 18"
----------------------------------------------------------------------------------------------------------------
| Id  | Operation                                | Name                | Starts | E-Rows | A-Rows |   A-Time   |
----------------------------------------------------------------------------------------------------------------
|   0 | SELECT STATEMENT                         |                     |      1 |        |      0 |00:00:00.01 |
|*  1 |  FILTER                                  |                     |      1 |        |      0 |00:00:00.01 |
|   2 |   MERGE JOIN OUTER                       |                     |      0 |     10 |      0 |00:00:00.01 |
|   3 |    INDEX FULL SCAN                       | T_PARENT_PK         |      0 |     10 |      0 |00:00:00.01 |
|   4 |    BUFFER SORT                           |                     |      0 |      1 |      0 |00:00:00.01 |
|   5 |     VIEW                                 | VW_LAT_A18161FF     |      0 |      1 |      0 |00:00:00.01 |
|   6 |      SORT AGGREGATE                      |                     |      0 |      1 |      0 |00:00:00.01 |
|   7 |       TABLE ACCESS BY INDEX ROWID BATCHED| T_CHILD             |      0 |      1 |      0 |00:00:00.01 |
|*  8 |        INDEX RANGE SCAN                  | T_CHILD_PARENT_FK_I |      0 |      1 |      0 |00:00:00.01 |
----------------------------------------------------------------------------------------------------------------

Predicate Information (identified by operation id):
---------------------------------------------------

   1 - filter(1=:NEED_TO_RUN)
   8 - access("PARENT_ID"="P"."ID")
```

There is also an option to set `_optimizer_filter_pushdown` to `false`, however, we went for the first solution and replaced `LATERAL(query)` with `LATERAL(query)(+)`.
That is another example when the optimizer gets overly aggressive in rewritting a query, so that in this particular case it outsmarted itself.
