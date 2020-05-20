---
categories:
  - Oracle
date:
  created: 2020-05-21T00:39:00
description: >-
  An example showing that OR Expansion kicks in when there is a virtual column or index present on certain columns.
tags:
  - 12c
  - 18c
  - Diagnostic event
  - Performance
---

# OR Expansion and Virtual Columns

The following test case can be used to demonstrate a little peculiarity of the OR Expansion transformation, that was introduced in 12.2.

<!-- more -->

It is important to note that the issue is not present in 19c - I have reproduced it only on 12.2.0.1.190416 and 18c.
The listings that I am using in this article are taken from 18c.

Let's run the following script to build the test data:

??? "or\_expand\_setup.sql"

    ```sql
    --8<-- "or-expansion-and-virtual-columns/or_expand_setup.sql"
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

In a nutshell, it is a list-partitioned table with a local index.
**90%** of the rows are in the `PROCESSED` status, whereas `PENDING` and `UNPROCESSED` statuses account only for **9%** and **1%** correspondingly.

Next, I am going to run a simple query and check its plan with and without a virtual column on the `STATUS` column:

```sql
 select --+ gather_plan_statistics or_expand(@sel$1 (1) (2))
        count(pad1)
   from t1
  where part_key = :part_key
    and (:param = 'WAITING' and status = 'UNPROCESSED'
         or
         :param = 'ALL' and status <> 'PENDING');
```

The variables `PARAM` and `PART_KEY` are set as follows:

```
var part_key varchar2(10)='P1'
var param    varchar2(12)='WAITING'
```

Thus, I am going to query a single partition to get the rows in the `UNPROCESSED` status from it.

Here is the result of the script `or_expand_test_no_vcol.sql` without the virtual column first:

??? "or\_expand\_test\_no\_vcol.sql"

    ```sql
    --8<-- "or-expansion-and-virtual-columns/or_expand_test_no_vcol.sql"
    ```

```sql hl_lines="4" title="or_expand_test_no_vcol.sql output"
SQL> @or_expand_test_no_vcol
SQL> set def on lin 124 pages 100
SQL>
SQL> -- alter table t1 add lower_status varchar2(128) generated always as (lower(status)) virtual;
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
new   1: alter session set tracefile_identifier='20200520_181304'

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
An uncaught error happened in prepare_sql_statement : ORA-01403: no data found

Plan hash value: 1293629841

-----------------------------------------------------------------------------------------
| Id  | Operation              | Name | Starts | E-Rows | A-Rows |   A-Time   | Buffers |
-----------------------------------------------------------------------------------------
|   0 | SELECT STATEMENT       |      |      1 |        |      1 |00:00:00.02 |    7831 |
|   1 |  SORT AGGREGATE        |      |      1 |      1 |      1 |00:00:00.02 |    7831 |
|   2 |   PARTITION LIST SINGLE|      |      1 |    920 |   1000 |00:00:00.01 |    7831 |
|*  3 |    TABLE ACCESS FULL   | T1   |      1 |    920 |   1000 |00:00:00.01 |    7831 |
-----------------------------------------------------------------------------------------

Outline Data
-------------

  /*+
      BEGIN_OUTLINE_DATA
      IGNORE_OPTIM_EMBEDDED_HINTS
      OPTIMIZER_FEATURES_ENABLE('18.1.0')
      DB_VERSION('18.1.0')
      ALL_ROWS
      OUTLINE_LEAF(@"SEL$1")
      FULL(@"SEL$1" "T1"@"SEL$1")
      END_OUTLINE_DATA
  */

Predicate Information (identified by operation id):
---------------------------------------------------

   3 - filter((((:PARAM='ALL' AND "STATUS"<>'PENDING') OR
              ("STATUS"='UNPROCESSED' AND :PARAM='WAITING')) AND "PART_KEY"=:PART_KEY))


35 rows selected.

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
/u01/app/oracle/diag/rdbms/orcl/orcl/trace/orcl_ora_2137_20200520_181304.trc
```

I highlighted the commented `ALTER TABLE ADD COLUMN` command.
I am going to refer to it below.

It is worth noting that the OR Expansion transformation has not been performed and the trace file contains a clue:

``` hl_lines="25 26 27"
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

!!! info "Off topic"

    I came across that `ORE: Bypassed for disjunct chain: No Index or Partition driver found.` message in one of my previous posts: [Concatenation and filter subqueries oddity](concatenation-and-filter-subqueries-oddity.md).

What can go wrong if we now uncomment the aforementioned `ALTER TABLE ADD COLUMN` command?
Let's run the script `or_expand_test_vcol.sql` to find out.

??? "or\_expand\_test\_vcol.sql"

    ```sql
    --8<-- "or-expansion-and-virtual-columns/or_expand_test_vcol.sql"
    ```

```sql hl_lines="4" title="or_expand_test_vcol.sql output"
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
new   1: alter session set tracefile_identifier='20200520_181319'

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
An uncaught error happened in prepare_sql_statement : ORA-01403: no data found

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
      OPTIMIZER_FEATURES_ENABLE('18.1.0')
      DB_VERSION('18.1.0')
      ALL_ROWS
      OUTLINE_LEAF(@"SET$9162BF3C_2")
      OUTLINE_LEAF(@"SET$9162BF3C_1")
      OUTLINE_LEAF(@"SET$9162BF3C")
      OR_EXPAND(@"SEL$1" (1) (2))
      OUTLINE_LEAF(@"SEL$BA8ECEFB")
      OUTLINE(@"SEL$1")
      NO_ACCESS(@"SEL$BA8ECEFB" "VW_ORE_BA8ECEFB"@"SEL$BA8ECEFB")
      INDEX_RS_ASC(@"SET$9162BF3C_1" "T1"@"SET$9162BF3C_1" ("T1"."STATUS"))
      BATCH_TABLE_ACCESS_BY_ROWID(@"SET$9162BF3C_1" "T1"@"SET$9162BF3C_1")
      FULL(@"SET$9162BF3C_2" "T1"@"SET$9162BF3C_2")
      END_OUTLINE_DATA
  */

Predicate Information (identified by operation id):
---------------------------------------------------

   4 - filter(:PARAM='WAITING')
   6 - filter("PART_KEY"=:PART_KEY)
   7 - access("STATUS"='UNPROCESSED')
   8 - filter(:PARAM='ALL')
  10 - filter(("STATUS"<>'PENDING' AND "PART_KEY"=:PART_KEY AND (LNNVL(:PARAM='WAITING') OR
              LNNVL("STATUS"='UNPROCESSED'))))


54 rows selected.

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
/u01/app/oracle/diag/rdbms/orcl/orcl/trace/orcl_ora_2137_20200520_181319.trc
```

The relevant section of the trace file is as follows:

``` hl_lines="25 27 28"
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

ORE: # conjunction chain - 2
ORE: Checking validity of disjunct chain

ORE:  Predicate list
P1 : "T1"."PART_KEY"=:B1
P2 : :B1='WAITING'
P3 : "T1"."STATUS"='UNPROCESSED'
P4 : :B1='ALL'
P5 : "T1"."STATUS"<>'PENDING'

 DNF Matrix (Before sorting OR branches)
            P1  P2  P3  P4  P5
CNJ (#1) :   1   1   1   0   0

CNJ (#2) :   1   0   0   1   1
```

I have made the following observations regarding this issue:

- The virtual column should be on the `STATUS` column.
  Neither `PART_KEY`, nor `PAD1` works - they both result in the absence of OR Expansion.
- The OR Expansion transformation kicks in if there are extended statistics on the `STATUS` column, such as: `SYS_OP_COMBINED_HASH(STATUS, PART_KEY)`.
- Unsurprisingly, there is OR Expansion when there is an FBI, such as:
  ```sql
  create index t1_lower_status_i on t1(lower(status)) local;
  ```
- The full outline of the query with OR Expansion does not lead to the OR Expansion transformation in the examples from this article where there was no OR Expansion.
- Once again, **^^19c behaves differently^^** - there is no OR Expansion in the given examples when 12.2 and 18c performs it.
  I am going to talk about in the next blog post.

Although I do expect OR Expansion in the queries from this article, I am not able to make a connection between OR Expansion and virtual columns/extended statistics/FBIs in the provided examples.
Hence, this issue is a bit mixed bag for me: I would love to have OR Expansion - the examples were designed after real application queries after all (they benefit from OR Expansion) - it might as well be a bug that was fixed in 19c.
Time will tell.

I have raised an SR to follow up on this issue: [SR 3-22449907431 : OR-Expansion does not work following 19.5 upgrade](https://support.oracle.com/rs?type=sr&id=3-22449907431).
Hopefully, Oracle Support will explain it one day - we have not made any progress during last 2 months which has become customary while working with Oracle Support.
