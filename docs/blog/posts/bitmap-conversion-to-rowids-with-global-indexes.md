---
categories:
  - Oracle
date:
  created: 2019-03-17T23:55:00
description: >-
  BITMAP AND operation needs the involved indexes to be local.
  The operation does not happen when one of the indexes is global.
  It is an Oracle limitation, and there is an enhancement request Bug 8787683 : SUPPORT GLOBAL BITMAP INDEXES AND BITMAP CONVERSION ON GLOBAL BTREE INDEXES
tags:
  - 12c
  - 19c
  - Indexing
  - Performance
---

# Bitmap Conversion to `ROWIDs` with Global Indexes

While working with developers on optimizing a query, I discovered a limitation of the `BITMAP AND` operation.

<!-- more -->

Here is an example demonstrating the issue:

```sql hl_lines="28"
SQL> create table t(
  2    part_col int,
  3    a int,
  4    b int)
  5  partition by list(part_col) (
  6    partition values (0)
  7  )
  8  ;

Table created.

SQL>
SQL> exec dbms_stats.gather_table_stats('', 't')

PL/SQL procedure successfully completed.

SQL>
SQL> create index t_a_i on t(a);

Index created.

SQL> create index t_b_i on t(b) local;

Index created.

SQL>
SQL> explain plan for
  2  select /*+ bitmap_tree(t and((a) (b)))*/
  3         *
  4    from t
  5   where a = :1
  6     and b = :2;

Explained.

SQL>
SQL> select * from table(dbms_xplan.display);

PLAN_TABLE_OUTPUT
-----------------------------------------------------------------------------------------------------------------------------
Plan hash value: 1636314338

--------------------------------------------------------------------------------------------------------------------
| Id  | Operation                                  | Name  | Rows  | Bytes | Cost (%CPU)| Time     | Pstart| Pstop |
--------------------------------------------------------------------------------------------------------------------
|   0 | SELECT STATEMENT                           |       |     1 |    39 |     1   (0)| 00:00:01 |       |       |
|*  1 |  TABLE ACCESS BY GLOBAL INDEX ROWID BATCHED| T     |     1 |    39 |     1   (0)| 00:00:01 |     1 |     1 |
|*  2 |   INDEX RANGE SCAN                         | T_A_I |     1 |       |     1   (0)| 00:00:01 |       |       |
--------------------------------------------------------------------------------------------------------------------

Predicate Information (identified by operation id):
---------------------------------------------------

   1 - filter("B"=TO_NUMBER(:2))
   2 - access("A"=TO_NUMBER(:1))

15 rows selected.
```

Surprisingly, the plan shows just one `INDEX RANGE SCAN` operation, and the expected `BITMAP AND` did not happen.

Let us see what we get once we make both indexes local:

```sql hl_lines="41"
SQL> drop index t_a_i;

Index dropped.

SQL> drop index t_b_i;

Index dropped.

SQL> create index t_a_i on t(a) local;

Index created.

SQL> create index t_b_i on t(b) local;

Index created.

SQL>
SQL> explain plan for
  2  select /*+ bitmap_tree(t and((a) (b)))*/
  3         *
  4    from t
  5   where a = :1
  6     and b = :2;

Explained.

SQL>
SQL> select * from table(dbms_xplan.display);

PLAN_TABLE_OUTPUT
-----------------------------------------------------------------------------------------------------------------------------
Plan hash value: 3534803727

--------------------------------------------------------------------------------------------------------------------
| Id  | Operation                                  | Name  | Rows  | Bytes | Cost (%CPU)| Time     | Pstart| Pstop |
--------------------------------------------------------------------------------------------------------------------
|   0 | SELECT STATEMENT                           |       |     1 |    39 |     3   (0)| 00:00:01 |       |       |
|   1 |  PARTITION LIST SINGLE                     |       |     1 |    39 |     3   (0)| 00:00:01 |     1 |     1 |
|   2 |   TABLE ACCESS BY LOCAL INDEX ROWID BATCHED| T     |     1 |    39 |     3   (0)| 00:00:01 |     1 |     1 |
|   3 |    BITMAP CONVERSION TO ROWIDS             |       |       |       |            |          |       |       |
|   4 |     BITMAP AND                             |       |       |       |            |          |       |       |
|   5 |      BITMAP CONVERSION FROM ROWIDS         |       |       |       |            |          |       |       |
|*  6 |       INDEX RANGE SCAN                     | T_A_I |       |       |     1   (0)| 00:00:01 |     1 |     1 |
|   7 |      BITMAP CONVERSION FROM ROWIDS         |       |       |       |            |          |       |       |
|*  8 |       INDEX RANGE SCAN                     | T_B_I |       |       |     1   (0)| 00:00:01 |     1 |     1 |
--------------------------------------------------------------------------------------------------------------------

Predicate Information (identified by operation id):
---------------------------------------------------

   6 - access("A"=TO_NUMBER(:1))
   8 - access("B"=TO_NUMBER(:2))

21 rows selected.
```

Here it is.
Once I made both indexes local, the `BITMAP AND` operation showed up.
Initially, I thought that it might have been related to different `ROWID` formats used for global and local indexes.
I just inserted one row to the table and dumped the leaf block for the global and local indexes:


```
$ grep 'col ' global.trc local.trc
global.trc:col 0; len 2; (2):  c1 02
global.trc:col 1; len 10; (10):  00 01 67 82 02 80 13 69 00 00
local.trc:col 0; len 2; (2):  c1 02
local.trc:col 1; len 6; (6):  02 80 13 69 00 00
```

You see that `col 1` for the local index has a `ROWID` in it: `len 6; (6):  02 80 13 69 00 00`, whereas the corresponding column for the global index has 10 bytes in length: `len 10; (10):  00 01 67 82 02 80 13 69 00 00` in which the leading 4 bytes refer to the object ID.
I also performed additional tests trying all possible combinations of indexes `T_A_I` and `T_B_I` making them global or local.
The only case when I was getting a `BITMAP AND` operation was the case when both indexes were local.
Changing the hint to `INDEX_COMBINE` did not give the desired execution plan.

Having gathered all of those results, I searched My Oracle Support (MOS) and found the explanation: [Bug 8787683 : SUPPORT GLOBAL BITMAP INDEXES AND BITMAP CONVERSION ON GLOBAL BTREE INDEXES](https://support.oracle.com/rs?type=bug&id=8787683).
There is, indeed, an enhancement request raised in 2009.

The problem query was rewritten to combine both indexes early and use filtered `ROWIDs` to access the base table:

```sql hl_lines="35"
SQL> explain plan for
  2  select /*+ unnest(@subq) no_use_hash_aggregation(@subq)*/
  3         *
  4    from t
  5   where rowid in (
  6           select /*+ qb_name(subq)*/
  7                  rid
  8             from (select rowid rid
  9                     from t
 10                    where a = :1
 11                    union all
 12                   select rowid
 13                     from t
 14                    where b = :2)
 15            group by rid
 16            having count(*)=2)
 17  ;

Explained.

SQL>
SQL> select * from table(dbms_xplan.display);

PLAN_TABLE_OUTPUT
-----------------------------------------------------------------------------------------------------------------------------
Plan hash value: 4066617294

--------------------------------------------------------------------------------------------------------
| Id  | Operation                   | Name     | Rows  | Bytes | Cost (%CPU)| Time     | Pstart| Pstop |
--------------------------------------------------------------------------------------------------------
|   0 | SELECT STATEMENT            |          |     1 |    63 |     5  (40)| 00:00:01 |       |       |
|   1 |  NESTED LOOPS               |          |     1 |    63 |     5  (40)| 00:00:01 |       |       |
|   2 |   VIEW                      | VW_NSO_1 |     2 |    24 |     3  (34)| 00:00:01 |       |       |
|*  3 |    FILTER                   |          |       |       |            |          |       |       |
|   4 |     SORT GROUP BY           |          |     1 |    24 |     3  (34)| 00:00:01 |       |       |
|   5 |      VIEW                   |          |     2 |    24 |     2   (0)| 00:00:01 |       |       |
|   6 |       UNION-ALL             |          |       |       |            |          |       |       |
|*  7 |        INDEX RANGE SCAN     | T_A_I    |     1 |    25 |     1   (0)| 00:00:01 |       |       |
|   8 |        PARTITION LIST SINGLE|          |     1 |    25 |     1   (0)| 00:00:01 |     1 |     1 |
|*  9 |         INDEX RANGE SCAN    | T_B_I    |     1 |    25 |     1   (0)| 00:00:01 |     1 |     1 |
|  10 |   TABLE ACCESS BY USER ROWID| T        |     1 |    51 |     1   (0)| 00:00:01 |     1 |     1 |
--------------------------------------------------------------------------------------------------------

Predicate Information (identified by operation id):
---------------------------------------------------

   3 - filter(COUNT(*)=2)
   7 - access("A"=TO_NUMBER(:1))
   9 - access("B"=TO_NUMBER(:2))
```

Notice the `SORT GROUP BY` operation in line 4 - it guarantees that the set of `ROWID`s will be sorted, so that we will never return to a block that was previously visited once we switched to another.

**TL;DR**: the `BITMAP AND` operation has some restrictions when global indexes are involved: [Bug 8787683 : SUPPORT GLOBAL BITMAP INDEXES AND BITMAP CONVERSION ON GLOBAL BTREE INDEXES](https://support.oracle.com/rs?type=bug&id=8787683)
The code was tested against 12.1.0.2 and 19c available on [https://livesql.oracle.com](https://livesql.oracle.com)
