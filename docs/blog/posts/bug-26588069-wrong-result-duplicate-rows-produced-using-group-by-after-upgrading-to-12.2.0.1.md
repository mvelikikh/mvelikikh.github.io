---
categories:
  - Oracle
date:
  created: 2019-09-04T21:51:00
description: >-
  Encountered Oracle bug 26588069 - Wrong Result (Duplicate Rows Produced) Using Group By After Upgrading To 12.2.0.1.
tags:
  - 12c
  - Bug
---

# Bug 26588069 - Wrong Result (Duplicate Rows Produced) Using Group By After Upgrading To 12.2.0.1

I have stumbled upon this bug after upgrading one of my databases to 12.2.0.1 when one of application queries started returning extra rows.

<!-- more -->

Here is a simplified test case:

```sql hl_lines="14 15 16"
SQL> create table gby_elim(x varchar2(10) primary key);

Table created.

SQL> insert into gby_elim values ('a');

1 row created.

SQL> insert into gby_elim values ('b');

1 row created.

SQL>
SQL> select length(x), count(*)
  2    from gby_elim
  3   group by length(x);

 LENGTH(X)   COUNT(*)
---------- ----------
         1          1
         1          1
```

The last query should have produced 1 row but it returned 2 rows.

Notice how Oracle eliminated the `GROUP BY` which it should not have done:

```sql
SQL> #0 explain plan for
SQL> /

Explained.

SQL> select * from table(dbms_xplan.display);

PLAN_TABLE_OUTPUT
------------------------------------------------------------------------------
Plan hash value: 1635879943

------------------------------------------------------------------------------
| Id  | Operation         | Name     | Rows  | Bytes | Cost (%CPU)| Time     |
------------------------------------------------------------------------------
|   0 | SELECT STATEMENT  |          |     2 |    14 |     2   (0)| 00:00:01 |
|   1 |  TABLE ACCESS FULL| GBY_ELIM |     2 |    14 |     2   (0)| 00:00:01 |
------------------------------------------------------------------------------
```

The SQL Optimizer trace file:

```
QB before group-by removal:******* UNPARSED QUERY IS *******
SELECT LENGTH("GBY_ELIM"."X") "LENGTH(X)",COUNT(*) "COUNT(*)" FROM "TC"."GBY_ELIM" "GBY_ELIM" GROUP BY LENGTH("GBY_ELIM"."X")
QB before group-by elimination:******* UNPARSED QUERY IS *******
SELECT LENGTH("GBY_ELIM"."X") "LENGTH(X)",COUNT(*) "COUNT(*)" FROM "TC"."GBY_ELIM" "GBY_ELIM" GROUP BY LENGTH("GBY_ELIM"."X")
Registered qb: SEL$47952E7A 0x88af59e8 (ELIMINATION OF GROUP BY SEL$1; SEL$1)
---------------------
QUERY BLOCK SIGNATURE
---------------------
  signature (): qb_name=SEL$47952E7A nbfros=1 flg=0
    fro(0): flg=0 objn=261334 hint_alias="GBY_ELIM"@"SEL$1"

QB after group-by elimination:******* UNPARSED QUERY IS *******
SELECT LENGTH("GBY_ELIM"."X") "LENGTH(X)",1 "COUNT(*)" FROM "TC"."GBY_ELIM" "GBY_ELIM"
Registered qb: SEL$9BB7A81A 0x88af59e8 (ELIMINATION OF GROUP BY SEL$47952E7A; SEL$47952E7A)
---------------------
QUERY BLOCK SIGNATURE
---------------------
  signature (): qb_name=SEL$9BB7A81A nbfros=1 flg=0
    fro(0): flg=0 objn=261334 hint_alias="GBY_ELIM"@"SEL$1"

QB after group-by removal:******* UNPARSED QUERY IS *******
SELECT LENGTH("GBY_ELIM"."X") "LENGTH(X)",1 "COUNT(*)" FROM "TC"."GBY_ELIM" "GBY_ELIM"
```

The plan table from the trace file:

``` hl_lines="38"
----- Explain Plan Dump -----
----- Plan Table -----

============
Plan Table
============
-------------------------------------+-----------------------------------+
| Id  | Operation          | Name    | Rows  | Bytes | Cost  | Time      |
-------------------------------------+-----------------------------------+
| 0   | SELECT STATEMENT   |         |       |       |     2 |           |
| 1   |  TABLE ACCESS FULL | GBY_ELIM|     2 |    14 |     2 |  00:00:01 |
-------------------------------------+-----------------------------------+
Query Block Name / Object Alias(identified by operation id):
------------------------------------------------------------
 1 - SEL$9BB7A81A         / GBY_ELIM@SEL$1
------------------------------------------------------------
Predicate Information:
----------------------

Content of other_xml column
===========================
  db_version     : 12.2.0.1
  parse_schema   : TC
  dynamic_sampling: 2
  plan_hash_full : 619495063
  plan_hash      : 1635879943
  plan_hash_2    : 619495063
  Outline Data:
  /*+
    BEGIN_OUTLINE_DATA
      IGNORE_OPTIM_EMBEDDED_HINTS
      OPTIMIZER_FEATURES_ENABLE('12.2.0.1')
      DB_VERSION('12.2.0.1')
      ALL_ROWS
      OUTLINE_LEAF(@"SEL$9BB7A81A")
      ELIM_GROUPBY(@"SEL$47952E7A")
      OUTLINE(@"SEL$47952E7A")
      ELIM_GROUPBY(@"SEL$1")
      OUTLINE(@"SEL$1")
      FULL(@"SEL$9BB7A81A" "GBY_ELIM"@"SEL$1")
    END_OUTLINE_DATA
  */
```

This is [Bug 26588069 - Wrong Result (Duplicate Rows Produced) Using Group By After Upgrading To 12.2.0.1 (Doc ID 26588069.8)](https://support.oracle.com/rs?type=doc&id=26588069.8) and any workaround mentioned in the aforementioned document will work.
To demonstrate a few:

```sql hl_lines="1 11"
SQL> select /*+ opt_param('_fix_control' '23210039:0')*/
  2         length(x), count(*)
  3    from gby_elim
  4   group by length(x);

 LENGTH(X)   COUNT(*)
---------- ----------
         1          2

SQL>
SQL> select /*+ opt_param('_optimizer_aggr_groupby_elim' 'false')*/
  2         length(x), count(*)
  3    from gby_elim
  4   group by length(x);

 LENGTH(X)   COUNT(*)
---------- ----------
         1          2
```

I can also add my own workaround using the `NO_ELIM_GROUPBY` hint:

```sql hl_lines="1"
SQL> select /*+ no_elim_groupby(@sel$1)*/
  2         length(x), count(*)
  3    from gby_elim
  4   group by length(x);

 LENGTH(X)   COUNT(*)
---------- ----------
         1          2
```

The patch for this bug is also available for most platforms.
