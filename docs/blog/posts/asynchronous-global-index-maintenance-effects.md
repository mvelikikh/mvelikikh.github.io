---
categories:
  - Oracle
date:
  created: 2016-05-14T12:29:00
description: >-
  Queries can switch from index full scan (min/max) to index fast full scan after dropping a table partition due to asynchronous global index maintenance.
  It can cause performance issues and the ALTER INDEX COALESCE CLEANUP statement needs to be run to get rid of the orphaned entries in the index, changing the queries execution plan back to index full scan (min/max).
tags:
  - 12c
  - Indexing
  - Performance
---

# Asynchronous Global Index Maintenance effects

I think Asynchronous Global Index Maintenance is one of the most exciting features in Oracle Database 12c.
This post is about one particular case when that feature can cause performance issues.

<!-- more -->

Let us create some test data:

```sql
SQL> create table t
  2  partition by range(owner)
  3  (
  4    partition values less than ('SYS'),
  5    partition values less than (maxvalue)
  6  )
  7  as
  8  select *
  9    from dba_objects;
SQL>
SQL> create index t_name_i on t(object_name);
```

Consider the following query:

```sql hl_lines="17"
SQL> explain plan for
  2  select max(object_name)
  3    from t;
SQL> select *
  2    from table(dbms_xplan.display);


PLAN_TABLE_OUTPUT
---------------------------------------------------------------------------------------
Plan hash value: 2886567490

---------------------------------------------------------------------------------------
| Id  | Operation                  | Name     | Rows  | Bytes | Cost (%CPU)| Time     |
---------------------------------------------------------------------------------------
|   0 | SELECT STATEMENT           |          |     1 |    25 |     3   (0)| 00:00:01 |
|   1 |  SORT AGGREGATE            |          |     1 |    25 |            |          |
|   2 |   INDEX FULL SCAN (MIN/MAX)| T_NAME_I |     1 |    25 |     3   (0)| 00:00:01 |
---------------------------------------------------------------------------------------
```

It is quite simple and the queries like that are common in my environment.
For instance, they are used to monitor application activities: `select max(date_column) from some_table` and the stuff alike.

Now I am going to drop a partition of that table:

```sql
SQL> alter table t drop partition for ('X') update indexes;
```

The index is marked as having orphaned entries after that:

```sql hl_lines="8"
SQL> select index_name, orphaned_entries
  2    from ind
  3   where table_name='T';


INDEX_NAME                     ORPHANED_
------------------------------ ---------
T_NAME_I                       YES
```

Which causes an important change in the execution plan:

```sql hl_lines="17 23"
SQL> explain plan for
  2  select max(object_name)
  3    from t;
SQL> select *
  2    from table(dbms_xplan.display);


PLAN_TABLE_OUTPUT
-----------------------------------------------------------------------------------
Plan hash value: 3249307143

----------------------------------------------------------------------------------
| Id  | Operation             | Name     | Rows  | Bytes | Cost (%CPU)| Time     |
----------------------------------------------------------------------------------
|   0 | SELECT STATEMENT      |          |     1 |    25 |   148   (1)| 00:00:01 |
|   1 |  SORT AGGREGATE       |          |     1 |    25 |            |          |
|*  2 |   INDEX FAST FULL SCAN| T_NAME_I | 96566 |  2357K|   148   (1)| 00:00:01 |
----------------------------------------------------------------------------------

Predicate Information (identified by operation id):
---------------------------------------------------

   2 - filter(TBL$OR$IDX$PART$NUM("T",0,8,0,"T".ROWID)=1)
```

The filter clearly was occured due to orphaned index entries which is confirmed by looking into the CBO trace file (event 10053):

```
Added Filter for Orphaned Entries of Index T_NAME_I:
TBL$OR$IDX$PART$NUM("T",0,8,0,"T".ROWID)=1
```

The index fast full scan would cause a huge amount of I/O being executed against large indexes.
For instance, some queries started scanning multi-gigabyte indexes in my database after I had dropped one small partition while executing periodic maintenance tasks.

Of course, in such a case Global Index Maintenance can not be delayed and the index synchronization procedure must be executed ASAP:

```sql hl_lines="1 9 25"
SQL> alter index t_name_i coalesce cleanup;
SQL> select index_name, orphaned_entries
  2    from ind
  3   where table_name='T';


INDEX_NAME                     ORPHANED_
------------------------------ ---------
T_NAME_I                       NO
SQL> explain plan for
  2  select max(object_name)
  3    from t;
SQL> select * from table(dbms_xplan.display);


PLAN_TABLE_OUTPUT
---------------------------------------------------------------------------------------
Plan hash value: 2886567490

---------------------------------------------------------------------------------------
| Id  | Operation                  | Name     | Rows  | Bytes | Cost (%CPU)| Time     |
---------------------------------------------------------------------------------------
|   0 | SELECT STATEMENT           |          |     1 |    25 |     3   (0)| 00:00:01 |
|   1 |  SORT AGGREGATE            |          |     1 |    25 |            |          |
|   2 |   INDEX FULL SCAN (MIN/MAX)| T_NAME_I |     1 |    25 |     3   (0)| 00:00:01 |
---------------------------------------------------------------------------------------
```
