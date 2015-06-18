---
categories:
  - Oracle
date:
  created: 2015-06-18T12:42:00
  updated: 2016-05-14T12:33:05
description: >-
  Encountered a case when function-based index changes its column's data type after a rebuild.
  It turns out to be an Oracle bug
tags:
  - 11g
  - 9i
  - Bug
  - Indexing
---

# Function-Based index changed its definition after a rebuild

One of our developers has discovered a problem when an index column's data type changed after the index was rebuilt.

<!-- more -->

He asked me for help with that issue.
Here is a demo script:

```sql
SQL> create table t(
  2    x int,
  3    y int);

Table created.

SQL> create index t_i on t(
  2    decode(x, 1, to_number(null), y));

Index created.

SQL> exec dbms_stats.gather_table_stats( '', 't')

PL/SQL procedure successfully completed.
```

I create a function-based index with one column.
The index's column is defined to show the `Y` column (with type `INT`) if the `X` column is not equal to 1 (or null).

According to the documentation of the [DECODE](http://docs.oracle.com/database/121/SQLRF/functions057.htm#SQLRF00631) function:

> Oracle automatically converts the return value to the same data type as the first result.
> <br/>
> If the first result has the data type CHAR or if the first result is null, then Oracle converts the return value to the data type VARCHAR2.

Notice that the index column's data type is a `NUMBER`:

```sql
SQL> select column_name
  2    from user_ind_columns
  3   where index_name = 'T_I';

COLUMN_NAME
------------------------------
SYS_NC00003$

SQL> select data_type
  2    from user_tab_cols
  3   where table_name = 'T'
  4     and column_name = 'SYS_NC00003$';

DATA_TYPE
------------------------------
NUMBER
```

The developer has found that his query does not use the index:

```sql hl_lines="19 25"
SQL> explain plan for
  2  select *
  3    from t
  4   where decode(x, 1, to_number(null), y) = to_number(:1);

Explained.

SQL>
SQL> @?/rdbms/admin/utlxpls

PLAN_TABLE_OUTPUT
--------------------------------------------------------------------------
Plan hash value: 2153619298

--------------------------------------------------------------------------
| Id  | Operation         | Name | Rows  | Bytes | Cost (%CPU)| Time     |
--------------------------------------------------------------------------
|   0 | SELECT STATEMENT  |      |     1 |    26 |     2   (0)| 00:00:01 |
|*  1 |  TABLE ACCESS FULL| T    |     1 |    26 |     2   (0)| 00:00:01 |
--------------------------------------------------------------------------

Predicate Information (identified by operation id):
---------------------------------------------------

   1 - filter(DECODE("X",1,TO_NUMBER(NULL),"Y")=TO_NUMBER(:1))
```

However, the index is used after changing the query to the following:

```sql hl_lines="4 20 26"
SQL> explain plan for
  2  select *
  3    from t
  4   where decode(x, 1, null, y) = to_number(:1);

Explained.

SQL>
SQL> @?/rdbms/admin/utlxpls

PLAN_TABLE_OUTPUT
--------------------------------------------------------------------------------------------
Plan hash value: 2858887366

--------------------------------------------------------------------------------------------
| Id  | Operation                           | Name | Rows  | Bytes | Cost (%CPU)| Time     |
--------------------------------------------------------------------------------------------
|   0 | SELECT STATEMENT                    |      |     1 |    39 |     1   (0)| 00:00:01 |
|   1 |  TABLE ACCESS BY INDEX ROWID BATCHED| T    |     1 |    39 |     1   (0)| 00:00:01 |
|*  2 |   INDEX RANGE SCAN                  | T_I  |     1 |       |     1   (0)| 00:00:01 |
--------------------------------------------------------------------------------------------

Predicate Information (identified by operation id):
---------------------------------------------------

   2 - access(DECODE("X",1,NULL,TO_CHAR("Y"))=TO_NUMBER(:1))
```

Why does this happen?
The index's expression is not what was in the `CREATE INDEX` statement:

```sql
SQL> select column_expression
  2    from user_ind_expressions
  3   where index_name = 'T_I';

COLUMN_EXPRESSION
------------------------------
DECODE("X",1,NULL,"Y")
```

It looks like Oracle is "clever enough" to change the index expression from `DECODE(X, 1, TO_NUMBER(NULL), Y)` to `DECODE("X", 1, NULL, "Y")`.
This leads to unexpected results after rebuilding the index:

```sql
alter index t_i rebuild;
```

All of a sudden the index column's data type becomes `VARCHAR2` after that!

```sql hl_lines="8"
SQL> select data_type
  2    from user_tab_cols
  3   where table_name = 'T'
  4     and column_name = 'SYS_NC00003$';

DATA_TYPE
------------------------------
VARCHAR2
```

The query starts using a full table scan whereas previously it was using an index:

```sql hl_lines="19 25"
SQL> explain plan for
  2  select *
  3    from t
  4   where decode(x, 1, null, y) = to_number(:1);

Explained.

SQL>
SQL> @?/rdbms/admin/utlxpls

PLAN_TABLE_OUTPUT
---------------------------------------------------------------------------
Plan hash value: 2153619298

--------------------------------------------------------------------------
| Id  | Operation         | Name | Rows  | Bytes | Cost (%CPU)| Time     |
--------------------------------------------------------------------------
|   0 | SELECT STATEMENT  |      |     1 |    48 |     2   (0)| 00:00:01 |
|*  1 |  TABLE ACCESS FULL| T    |     1 |    48 |     2   (0)| 00:00:01 |
--------------------------------------------------------------------------

Predicate Information (identified by operation id):
---------------------------------------------------

   1 - filter(TO_NUMBER(DECODE("X",1,NULL,TO_CHAR("Y")))=TO_NUMBER(:1))
```

The `INDEX` hint did not help either:

```sql hl_lines="2 19 25"
SQL> explain plan for
  2  select /*+ index(t t_i)*/*
  3    from t
  4   where decode(x, 1, null, y) = to_number(:1);

Explained.

SQL>
SQL> @?/rdbms/admin/utlxpls

PLAN_TABLE_OUTPUT
--------------------------------------------------------------------------
Plan hash value: 2153619298

--------------------------------------------------------------------------
| Id  | Operation         | Name | Rows  | Bytes | Cost (%CPU)| Time     |
--------------------------------------------------------------------------
|   0 | SELECT STATEMENT  |      |     1 |    48 |     2   (0)| 00:00:01 |
|*  1 |  TABLE ACCESS FULL| T    |     1 |    48 |     2   (0)| 00:00:01 |
--------------------------------------------------------------------------

Predicate Information (identified by operation id):
---------------------------------------------------

   1 - filter(TO_NUMBER(DECODE("X",1,NULL,TO_CHAR("Y")))=TO_NUMBER(:1))
```

Notice there is a `TO_NUMBER` conversion at line 1:

```
   1 - filter(TO_NUMBER(DECODE("X",1,NULL,TO_CHAR("Y")))=TO_NUMBER(:1))
```

Thus, the index becomes used for a rewritten query with an explicit `TO_CHAR` conversion:

```sql hl_lines="4 20 26"
SQL> explain plan for
  2  select *
  3    from t
  4   where decode(x, 1, null, y) = to_char(:1);

Explained.

SQL>
SQL> @?/rdbms/admin/utlxpls

PLAN_TABLE_OUTPUT
--------------------------------------------------------------------------------------------
Plan hash value: 2858887366

--------------------------------------------------------------------------------------------
| Id  | Operation                           | Name | Rows  | Bytes | Cost (%CPU)| Time     |
--------------------------------------------------------------------------------------------
|   0 | SELECT STATEMENT                    |      |     1 |    48 |     1   (0)| 00:00:01 |
|   1 |  TABLE ACCESS BY INDEX ROWID BATCHED| T    |     1 |    48 |     1   (0)| 00:00:01 |
|*  2 |   INDEX RANGE SCAN                  | T_I  |     1 |       |     1   (0)| 00:00:01 |
--------------------------------------------------------------------------------------------

Predicate Information (identified by operation id):
---------------------------------------------------

   2 - access(DECODE("X",1,NULL,TO_CHAR("Y"))=:1)
```

To workaround this issue, we could use an index on virtual columns.
Alternatively, the `TO_NUMBER(NULL)` to NULL conversion can be prevented by changing `TO_NUMBER(NULL)` to `CAST(NULL as NUMBER)`, or other similar expressions.

I have opened an SR with Oracle and they told me that this is due to:
[Bug 17871767: FUNCTION BASE INDEX DEFINITION CHANGED ON 11.2, ADDED A TO\_CHAR FUNCTION](https://support.oracle.com/rs?type=bug&id=17871767)
That bug is still under work and has not been resolved yet.

It turns out this issue with function-based indexes has been present for a long time.
I have reproduced it on 9.2.0.6 at least.
