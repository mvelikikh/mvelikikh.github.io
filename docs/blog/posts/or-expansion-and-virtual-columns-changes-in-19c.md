---
categories:
  - Oracle
date:
  created: 2020-06-09T01:31:00
description: >-
  This blog post demonstrates a specific example in which OR Expansion fails to produce the desired execution plan, leading to a suboptimal execution.
  By way of contrast, concatenation results in the more optimal execution plan, performing as effectively as OR Expansion did before 19c.
tags:
  - 19c
  - Diagnostic event
  - Performance
---

# OR Expansion and Virtual Columns: Changes in 19c

This post is a continuation of a previous one: [OR Expansion and Virtual Columns](or-expansion-and-virtual-columns.md).
The last post demonstrated that OR Expansion can somehow be affected by virtual columns in such a way that queries that did not perform OR Expansion can start using it as soon as a virtual column is created.
Both an FBI and extended statistics lead to the same result provided that a certain column used in the query is included in them.
This time around, I am going to take a look at how 19c has changed that.

<!-- more -->

Firstly, I am going to recreate my initial table:

??? "or\_expand\_setup.sql"

    ```sql
    --8<-- "or-expansion-and-virtual-columns-changes-in-19c/or_expand_setup.sql"
    ```

```sql title="or_expand_setup.sql output"
SQL> @or_expand_setup
SQL> drop table t1;

Table dropped.

SQL>
SQL> create table t1 (
  2    part_key varchar2(8),
  3    status   varchar2(12),
  4    pad1     char(500)
  5  )
  6  partition by list(part_key) (
  7    partition values ('P1'),
  8    partition values (default)
  9  )
 10  ;

Table created.

SQL>
SQL>
SQL> insert into t1
  2  select 'P1', status, 'X'
  3    from (select 90 pct, 'PROCESSED' status from dual union all
  4          select 1, 'UNPROCESSED' from dual union all
  5          select 9, 'PENDING' from dual) params,
  6         lateral(
  7           select level
  8             from dual
  9             connect by level <= params.pct * 1000
 10         ) duplicator;

100000 rows created.

SQL>
SQL> commit;

Commit complete.

SQL>
SQL> create index t1_status_i on t1(status) local;

Index created.

SQL>
SQL> select status,
  2         count(*),
  3         round(ratio_to_report(count(*)) over () * 100, 2) pct
  4    from t1
  5   group by status
  6   order by 1;

STATUS         COUNT(*)        PCT
------------ ---------- ----------
PENDING            9000          9
PROCESSED         90000         90
UNPROCESSED        1000          1
```


Secondly, I am running the `or_expand_test_vcol.sql` script which was previously performed OR Expansion in both 12.2 and 18c:

??? "or\_expand\_test\_vcol.sql"

    ```sql
    --8<-- "or-expansion-and-virtual-columns-changes-in-19c/or_expand_test_vcol.sql"
    ```

```sql title="or_expand_test_vcol.sql output"
SQL> @or_expand_test_vcol
SQL> set def on lin 124 pages 100
SQL>
SQL> alter table t1 add lower_status varchar2(128) generated always as (lower(status)) virtual;

Table altered.

SQL>
SQL> exec dbms_stats.gather_table_stats( '', 't1', method_opt => 'for all columns size 254')

PL/SQL procedure successfully completed.

SQL>
SQL> col tfi old_v tfi nopri
SQL>
SQL> select to_char(sysdate, 'yyyymmdd_hh24miss') tfi from dual;

SQL>
SQL> alter session set tracefile_identifier='&tfi.';
old   1: alter session set tracefile_identifier='&tfi.'
new   1: alter session set tracefile_identifier='20200608_180223'

Session altered.

SQL>
SQL> alter session set events 'trace[sql_optimizer.*]';

Session altered.

SQL>
SQL>
SQL> var part_key varchar2(10)='P1'
SQL> var param    varchar2(12)='WAITING'
SQL>
SQL> select --+ gather_plan_statistics or_expand(@sel$1 (1) (2))
  2         count(pad1)
  3    from t1
  4   where part_key = :part_key
  5     and (:param = 'WAITING' and status = 'UNPROCESSED'
  6          or
  7          :param = 'ALL' and status <> 'PENDING');

COUNT(PAD1)
-----------
       1000

SQL>
SQL> select *
  2    from dbms_xplan.display_cursor(format=> 'allstats last outline');

PLAN_TABLE_OUTPUT
----------------------------------------------------------------------------------------------------------------------------
SQL_ID  fq8b3jumk131t, child number 0
-------------------------------------
select --+ gather_plan_statistics or_expand(@sel$1 (1) (2))
count(pad1)   from t1  where part_key = :part_key    and (:param =
'WAITING' and status = 'UNPROCESSED'         or         :param = 'ALL'
and status <> 'PENDING')

Plan hash value: 1293629841

-----------------------------------------------------------------------------------------
| Id  | Operation              | Name | Starts | E-Rows | A-Rows |   A-Time   | Buffers |
-----------------------------------------------------------------------------------------
|   0 | SELECT STATEMENT       |      |      1 |        |      1 |00:00:00.03 |    7826 |
|   1 |  SORT AGGREGATE        |      |      1 |      1 |      1 |00:00:00.03 |    7826 |
|   2 |   PARTITION LIST SINGLE|      |      1 |    920 |   1000 |00:00:00.03 |    7826 |
|*  3 |    TABLE ACCESS FULL   | T1   |      1 |    920 |   1000 |00:00:00.03 |    7826 |
-----------------------------------------------------------------------------------------

Outline Data
-------------

  /*+
      BEGIN_OUTLINE_DATA
      IGNORE_OPTIM_EMBEDDED_HINTS
      OPTIMIZER_FEATURES_ENABLE('19.1.0')
      DB_VERSION('19.1.0')
      ALL_ROWS
      OUTLINE_LEAF(@"SEL$1")
      FULL(@"SEL$1" "T1"@"SEL$1")
      END_OUTLINE_DATA
  */

Predicate Information (identified by operation id):
---------------------------------------------------

   3 - filter((((:PARAM='ALL' AND "STATUS"<>'PENDING') OR
              ("STATUS"='UNPROCESSED' AND :PARAM='WAITING')) AND "PART_KEY"=:PART_KEY))


38 rows selected.

SQL>
SQL> alter session set events 'trace[sql_optimizer.*] off';

Session altered.

SQL>
SQL> col value for a80
SQL>
SQL> select value
  2    from v$diag_info
  3   where name='Default Trace File';

VALUE
--------------------------------------------------------------------------------
/u01/app/oracle/diag/rdbms/orcl/orcl/trace/orcl_ora_7253_20200608_180223.trc
```

As the output above demonstrates, there is no OR Expansion anymore.
The trace file [orcl\_ora\_7253\_20200608\_180223.trc](or-expansion-and-virtual-columns-changes-in-19c/orcl_ora_7253_20200608_180223.trc) shows the following:

``` hl_lines="26"
***********************************
Cost-Based OR Expansion
***********************************
ORE: Trying CBQT OR expansion before unnesting
ORE: Checking validity of OR Expansion for query block SEL$1 (#1)
ORE: Predicate chain before QB validity check - SEL$1
"T1"."PART_KEY"=:B1 AND (:B2='WAITING' AND "T1"."STATUS"='UNPROCESSED' OR :B3='ALL' AND "T1"."STATUS"<>'PENDING')

ORE: Predicate chain after QB validity check - SEL$1
"T1"."PART_KEY"=:B1 AND (:B2='WAITING' AND "T1"."STATUS"='UNPROCESSED' OR :B3='ALL' AND "T1"."STATUS"<>'PENDING')
OR Expansion on query block SEL$1 (#1)
ORE: Checking validity of OR Expansion for query block SEL$1 (#1)
ORE: Predicate chain before QB validity check - SEL$1
"T1"."PART_KEY"=:B1 AND (:B2='WAITING' AND "T1"."STATUS"='UNPROCESSED' OR :B3='ALL' AND "T1"."STATUS"<>'PENDING')

ORE: Predicate chain after QB validity check - SEL$1
"T1"."PART_KEY"=:B1 AND (:B2='WAITING' AND "T1"."STATUS"='UNPROCESSED' OR :B3='ALL' AND "T1"."STATUS"<>'PENDING')
ORE: Using search type: linear
ORE: Checking validity of OR Expansion for query block SEL$1 (#1)
ORE: Predicate chain before QB validity check - SEL$1
"T1"."PART_KEY"=:B1 AND (:B2='WAITING' AND "T1"."STATUS"='UNPROCESSED' OR :B3='ALL' AND "T1"."STATUS"<>'PENDING')

ORE: Predicate chain after QB validity check - SEL$1
"T1"."PART_KEY"=:B1 AND (:B2='WAITING' AND "T1"."STATUS"='UNPROCESSED' OR :B3='ALL' AND "T1"."STATUS"<>'PENDING')
ORE: Checking validity of disjunct chain
ORE: Bypassed for disjunct chain: No Index or Partition driver found.
ORE: # conjunction chain - 1
ORE: No state generated.
```

It is worth noting that even a full outline does not lead to the desired plan.
That is how I discovered that issue initially.
The query in question did have an SQL Plan Baseline which stopped being reproducible following a 19c upgrade.

A straightforward way to get the desired execution plan is to rewrite the initial query as follows:

??? "or\_expand\_test\_rewrite.sql"

    ```sql
    --8<-- "or-expansion-and-virtual-columns-changes-in-19c/or_expand_test_rewrite.sql"
    ```

```sql hl_lines="12 14" title="or_expand_test_rewrite.sql output"
SQL> @or_expand_test_rewrite

..skip..

SQL> var part_key varchar2(10)='P1'
SQL> var param    varchar2(12)='WAITING'
SQL>
SQL> select --+ gather_plan_statistics or_expand(@sel$1 (1) (2))
  2         count(pad1)
  3    from t1
  4   where 1 = 1
  5     and (part_key = :part_key and :param = 'WAITING' and status = 'UNPROCESSED'
  6          or
  7          part_key = :part_key||'' and :param = 'ALL' and status <> 'PENDING');

COUNT(PAD1)
-----------
       1000

SQL>
SQL> select *
  2    from dbms_xplan.display_cursor(format=> 'allstats last outline');

PLAN_TABLE_OUTPUT
----------------------------------------------------------------------------------------------------------------------------
SQL_ID  99zvump911bc7, child number 0
-------------------------------------
select --+ gather_plan_statistics or_expand(@sel$1 (1) (2))
count(pad1)   from t1  where 1 = 1    and (part_key = :part_key and
:param = 'WAITING' and status = 'UNPROCESSED'         or
part_key = :part_key||'' and :param = 'ALL' and status <> 'PENDING')

Plan hash value: 3973059565

----------------------------------------------------------------------------------------------------------------------------
| Id  | Operation                                      | Name            | Starts | E-Rows | A-Rows |   A-Time   | Buffers |
----------------------------------------------------------------------------------------------------------------------------
|   0 | SELECT STATEMENT                               |                 |      1 |        |      1 |00:00:00.01 |      83 |
|   1 |  SORT AGGREGATE                                |                 |      1 |      1 |      1 |00:00:00.01 |      83 |
|   2 |   VIEW                                         | VW_ORE_BA8ECEFB |      1 |  91982 |   1000 |00:00:00.01 |      83 |
|   3 |    UNION-ALL                                   |                 |      1 |        |   1000 |00:00:00.01 |      83 |
|*  4 |     FILTER                                     |                 |      1 |        |   1000 |00:00:00.01 |      83 |
|   5 |      PARTITION LIST SINGLE                     |                 |      1 |    999 |   1000 |00:00:00.01 |      83 |
|*  6 |       TABLE ACCESS BY LOCAL INDEX ROWID BATCHED| T1              |      1 |    999 |   1000 |00:00:00.01 |      83 |
|*  7 |        INDEX RANGE SCAN                        | T1_STATUS_I     |      1 |   1000 |   1000 |00:00:00.01 |       6 |
|*  8 |     FILTER                                     |                 |      1 |        |      0 |00:00:00.01 |       0 |
|   9 |      PARTITION LIST SINGLE                     |                 |      0 |  90983 |      0 |00:00:00.01 |       0 |
|* 10 |       TABLE ACCESS FULL                        | T1              |      0 |  90983 |      0 |00:00:00.01 |       0 |
----------------------------------------------------------------------------------------------------------------------------

Outline Data
-------------

  /*+
      BEGIN_OUTLINE_DATA
      IGNORE_OPTIM_EMBEDDED_HINTS
      OPTIMIZER_FEATURES_ENABLE('19.1.0')
      DB_VERSION('19.1.0')
      ALL_ROWS
      OUTLINE_LEAF(@"SET$2A13AF86_2")
      OUTLINE_LEAF(@"SET$2A13AF86_1")
      OUTLINE_LEAF(@"SET$2A13AF86")
      OUTLINE_LEAF(@"SEL$9162BF3C")
      OR_EXPAND(@"SEL$1" (1) (2))
      OUTLINE(@"SEL$1")
      NO_ACCESS(@"SEL$9162BF3C" "VW_ORE_BA8ECEFB"@"SEL$BA8ECEFB")
      INDEX_RS_ASC(@"SET$2A13AF86_1" "T1"@"SET$2A13AF86_1" ("T1"."STATUS"))
      BATCH_TABLE_ACCESS_BY_ROWID(@"SET$2A13AF86_1" "T1"@"SET$2A13AF86_1")
      FULL(@"SET$2A13AF86_2" "T1"@"SET$2A13AF86_2")
      END_OUTLINE_DATA
  */

Predicate Information (identified by operation id):
---------------------------------------------------

   4 - filter(:PARAM='WAITING')
   6 - filter("PART_KEY"=:PART_KEY)
   7 - access("STATUS"='UNPROCESSED')
   8 - filter(:PARAM='ALL')
  10 - filter(("STATUS"<>'PENDING' AND "PART_KEY"=:PART_KEY||'' AND (LNNVL("PART_KEY"=:PART_KEY) OR
              LNNVL(:PARAM='WAITING') OR LNNVL("STATUS"='UNPROCESSED'))))


57 rows selected.

SQL>
SQL> alter session set events 'trace[sql_optimizer.*] off';

Session altered.

SQL>
SQL> col value for a80
SQL>
SQL> select value
  2    from v$diag_info
  3   where name='Default Trace File';

VALUE
--------------------------------------------------------------------------------
/u01/app/oracle/diag/rdbms/orcl/orcl/trace/orcl_ora_7253_20200608_180825.trc
```

The corresponding trace file is: [orcl\_ora\_7253\_20200608\_180825.trc](or-expansion-and-virtual-columns-changes-in-19c/orcl_ora_7253_20200608_180825.trc).
Evidently, this rewrite can be applied in a limited number of cases.

Thankfully, the old OR Expansion transformation, aka concatenation, works just fine for this example which is demonstrated in the listing below:

??? "or\_expand\_test\_use\_concat.sql"

    ```sql
    --8<-- "or-expansion-and-virtual-columns-changes-in-19c/or_expand_test_use_concat.sql"
    ```

```sql hl_lines="40" title="or_expand_test_use_concat.sql output"
SQL> @or_expand_test_use_concat

..skip..

SQL> var part_key varchar2(10)='P1'
SQL> var param    varchar2(12)='WAITING'
SQL>
SQL> select --+ gather_plan_statistics use_concat(or_predicates(2))
  2         count(pad1)
  3    from t1
  4   where part_key = :part_key
  5     and (:param = 'WAITING' and status = 'UNPROCESSED'
  6          or
  7          :param = 'ALL' and status <> 'PENDING');

COUNT(PAD1)
-----------
       1000

SQL>
SQL> select *
  2    from dbms_xplan.display_cursor(format=> 'allstats last outline');

PLAN_TABLE_OUTPUT
----------------------------------------------------------------------------------------------------------------------------
SQL_ID  cygpq5hyy2uu2, child number 0
-------------------------------------
select --+ gather_plan_statistics use_concat(or_predicates(2))
count(pad1)   from t1  where part_key = :part_key    and (:param =
'WAITING' and status = 'UNPROCESSED'         or         :param = 'ALL'
and status <> 'PENDING')

Plan hash value: 496678280

-----------------------------------------------------------------------------------------------------------------------
| Id  | Operation                                     | Name        | Starts | E-Rows | A-Rows |   A-Time   | Buffers |
-----------------------------------------------------------------------------------------------------------------------
|   0 | SELECT STATEMENT                              |             |      1 |        |      1 |00:00:00.01 |      83 |
|   1 |  SORT AGGREGATE                               |             |      1 |      1 |      1 |00:00:00.01 |      83 |
|   2 |   CONCATENATION                               |             |      1 |        |   1000 |00:00:00.01 |      83 |
|*  3 |    FILTER                                     |             |      1 |        |      0 |00:00:00.01 |       0 |
|   4 |     PARTITION LIST SINGLE                     |             |      0 |  90992 |      0 |00:00:00.01 |       0 |
|*  5 |      TABLE ACCESS FULL                        | T1          |      0 |  90992 |      0 |00:00:00.01 |       0 |
|*  6 |    FILTER                                     |             |      1 |        |   1000 |00:00:00.01 |      83 |
|   7 |     PARTITION LIST SINGLE                     |             |      1 |    990 |   1000 |00:00:00.01 |      83 |
|*  8 |      TABLE ACCESS BY LOCAL INDEX ROWID BATCHED| T1          |      1 |    990 |   1000 |00:00:00.01 |      83 |
|*  9 |       INDEX RANGE SCAN                        | T1_STATUS_I |      1 |    990 |   1000 |00:00:00.01 |       6 |
-----------------------------------------------------------------------------------------------------------------------

Outline Data
-------------

  /*+
      BEGIN_OUTLINE_DATA
      IGNORE_OPTIM_EMBEDDED_HINTS
      OPTIMIZER_FEATURES_ENABLE('19.1.0')
      DB_VERSION('19.1.0')
      ALL_ROWS
      OUTLINE_LEAF(@"SEL$1")
      OUTLINE_LEAF(@"SEL$1_1")
      USE_CONCAT(@"SEL$1" OR_PREDICATES(2))
      OUTLINE_LEAF(@"SEL$1_2")
      FULL(@"SEL$1_1" "T1"@"SEL$1")
      INDEX_RS_ASC(@"SEL$1_2" "T1"@"SEL$1_2" ("T1"."STATUS"))
      BATCH_TABLE_ACCESS_BY_ROWID(@"SEL$1_2" "T1"@"SEL$1_2")
      END_OUTLINE_DATA
  */

Predicate Information (identified by operation id):
---------------------------------------------------

   3 - filter(:PARAM='ALL')
   5 - filter(("STATUS"<>'PENDING' AND "PART_KEY"=:PART_KEY))
   6 - filter(:PARAM='WAITING')
   8 - filter("PART_KEY"=:PART_KEY)
   9 - access("STATUS"='UNPROCESSED')
       filter((LNNVL(:PARAM='ALL') OR LNNVL("STATUS"<>'PENDING')))


53 rows selected.

SQL>
SQL> alter session set events 'trace[sql_optimizer.*] off';

Session altered.

SQL>
SQL> col value for a80
SQL>
SQL> select value
  2    from v$diag_info
  3   where name='Default Trace File';

VALUE
--------------------------------------------------------------------------------
/u01/app/oracle/diag/rdbms/orcl/orcl/trace/orcl_ora_7253_20200608_181301.trc
```

The corresponding trace file is: [orcl\_ora\_7253\_20200608\_181301.trc](or-expansion-and-virtual-columns-changes-in-19c/orcl_ora_7253_20200608_181301.trc).

This blog post demonstrates a specific example in which OR Expansion fails to produce the desired execution plan, leading to a suboptimal execution.
By way of contrast, concatenation results in the execution plan I was seeking, performing as effectively as OR Expansion did before 19c.
It is my hope that Oracle will fix this issue eventually, which I am trying to get done in [SR 3-22449907431 : OR-Expansion does not work following 19.5 upgrade](https://support.oracle.com/rs?type=sr&id=3-22449907431).
