---
categories:
  - Oracle
date:
  created: 2021-02-03T02:27:00
description: >-
  19.10 introduces a fix control 19138896 allowing to update a non key-preserved table.
  This post demonstrates this.
tags:
  - 19c
  - OERR
---

# Updating non Key-Preserved Table

There used to be the `BYPASS_UJVC` hint that allowed to update a non key-preserved table.
It is still there, but it must have stopped working around 11.2.
It turns out that Oracle introduced a fix control that seems to be doing the same in 19.10.

<!-- more -->

## Demonstration

Here is a short demonstration of this fix control.

```sql hl_lines="72 80"
SQL> select banner_full from v$version;

BANNER_FULL
----------------------------------------------------------------------------------------------------
Oracle Database 19c Enterprise Edition Release 19.0.0.0.0 - Production
Version 19.10.0.0.0


SQL>
SQL> col fix_control for a90
SQL>
SQL> select xmltype.createxml(cursor(
  2           select *
  3             from v$system_fix_control
  4            where bugno = 19138896)) fix_control
  5    from dual;

FIX_CONTROL
------------------------------------------------------------------------------------------
<?xml version="1.0"?>
<ROWSET>
  <ROW>
    <BUGNO>19138896</BUGNO>
    <VALUE>0</VALUE>
    <SQL_FEATURE>QKSFM_DML_19138896</SQL_FEATURE>
    <DESCRIPTION>allow update of join view without key preserved property</DESCRIPTION>
    <EVENT>0</EVENT>
    <IS_DEFAULT>1</IS_DEFAULT>
    <CON_ID>3</CON_ID>
  </ROW>
</ROWSET>


SQL>
SQL> create table t1 (
  2    pk_col int,
  3    t1_col varchar2(30));

Table created.

SQL>
SQL> create table t2 (
  2    pk_col int,
  3    t2_col varchar2(30));

Table created.

SQL>
SQL> insert into t1 values (1, 't1_1');

1 row created.

SQL> insert into t1 values (2, 't1_2');

1 row created.

SQL>
SQL> insert into t2 values (2, 't2_2');

1 row created.

SQL> insert into t2 values (3, 't2_3');

1 row created.

SQL>
SQL> commit;

Commit complete.

SQL>
SQL> select * from t1;

    PK_COL T1_COL
---------- ------------------------------
         1 t1_1
         2 t1_2

SQL>
SQL> select * from t2;

    PK_COL T2_COL
---------- ------------------------------
         2 t2_2
         3 t2_3
```

Let us try to update all rows in `T2` with the matching value from `T1`:

```sql hl_lines="8"
SQL> update (select t2_col, t1_col
  2            from t1, t2
  3           where t2.pk_col = t1.pk_col)
  4     set t2_col = t1_col;
   set t2_col = t1_col
       *
ERROR at line 4:
ORA-01779: cannot modify a column which maps to a non key-preserved table
```

Cannot do that.
`BYPASS_UJVC` does not work either.

```sql hl_lines="9"
SQL> update --+ bypass_ujvc
  2         (select t2_col, t1_col
  3            from t1, t2
  4           where t2.pk_col = t1.pk_col)
  5     set t2_col = t1_col;
   set t2_col = t1_col
       *
ERROR at line 5:
ORA-01779: cannot modify a column which maps to a non key-preserved table
```

Now with fix control 19138896:

```sql
SQL> update --+ opt_param('_fix_control' '19138896:1')
  2         (select t2_col, t1_col
  3            from t1, t2
  4           where t2.pk_col = t1.pk_col)
  5     set t2_col = t1_col;

1 row updated.

SQL>
SQL> select *
  2    from t2;

    PK_COL T2_COL
---------- ------------------------------
         2 t1_2
         3 t2_3

SQL>
SQL> roll
Rollback complete.
```

If I try to add a duplicate row to `T1` making this update non-deterministic, so that there is an attempt to update a row from `T2` more than once, I get an error:

```sql hl_lines="13"
SQL> insert into t1 values (2, 't1_22');

1 row created.

SQL> update --+ opt_param('_fix_control' '19138896:1')
  2         (select t2_col, t1_col
  3            from t1, t2
  4           where t2.pk_col = t1.pk_col)
  5     set t2_col = t1_col;
          from t1, t2
               *
ERROR at line 3:
ORA-30926: unable to get a stable set of rows in the source tables
```

## Conclusion

Altrough I generally prefer either rewriting such statements to `MERGE` or adding missing constraints, the fix control 19138896 brings another option to the table.
It also has certain advantages, to name a few:

- There is no need to rewrite the query.
  The fix control can be added through an SQL patch, for example.

- The fix control can be set at the session or instance levels.
