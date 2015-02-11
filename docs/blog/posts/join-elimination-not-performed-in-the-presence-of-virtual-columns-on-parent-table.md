---
categories:
  - Oracle
date:
  created: 2015-02-11T16:26:00
description: >-
  Found a case when a query joining parent and child tables did not eliminate the parent table when it seemingly could.
  It turns out it was a known Oracle bug 12739252 JOIN ELIMINATION IS NOT DONE WHEN JOINING TABLE HAVE VIRTUAL COLUMN
tags:
  - 11g
  - Bug
---

# Join elimination not performed in the presence of virtual columns on parent table

Found a case when a query joining parent and child tables did not eliminate the parent table when it seemingly could.

<!-- more -->

Here is a simplified version of the poorly written SQL query performing an unnecessary join between PARENT/CHILD tables:

```sql
SQL> select * from table(dbms_xplan.display_cursor( '23hbmd0xxv7p0'));

PLAN_TABLE_OUTPUT
----------------------------------------------------------------------------------------------------
SQL_ID  23hbmd0xxv7p0, child number 0
-------------------------------------
SELECT P.ID FROM PARENT P, CHILD C WHERE P.ID = :B1 AND P.ID = C.PARENT_ID

Plan hash value: 3267741206

----------------------------------------------------------------------------------------------------
| Id  | Operation                    | Name                | Rows  | Bytes | Cost (%CPU)| Time     |
----------------------------------------------------------------------------------------------------
|   0 | SELECT STATEMENT             |                     |       |       |     5 (100)|          |
|   1 |  NESTED LOOPS                |                     |     2 |    36 |     5   (0)| 00:00:01 |
|*  2 |   INDEX UNIQUE SCAN          | PARENT_ID_PK        |     1 |     6 |     2   (0)| 00:00:01 |
|   3 |   TABLE ACCESS BY INDEX ROWID| CHILD               |     2 |    24 |     3   (0)| 00:00:01 |
|*  4 |    INDEX RANGE SCAN          | CHILD_PARENT_FK_IDX |     2 |       |     2   (0)| 00:00:01 |
----------------------------------------------------------------------------------------------------

Predicate Information (identified by operation id):
---------------------------------------------------

   2 - access("P"."ID"=:B1)
   4 - access("C"."PARENT_ID"=:B1)
```

PARENT table has a primary key enabled and validated.
CHILD table has a foreign key, which is also enabled and validated, referencing PARENT.
Without obvious reason JOIN ELIMINATION is not done when expected.
We are using Oracle database version 11.2.0.3.11 (PSU 11 applied).

I investigated this issue further and found that this is due to the presence of virtual columns on PARENT table.
There is a simple test case below used to reproduce this issue (I copied this test case with a little modification from [Excellent Christian Antognini site](http://antognini.ch/2010/01/join-elimination/)):

```sql
SQL> CREATE TABLE t1 (
  2    id NUMBER NOT NULL,
  3    n NUMBER,
  4    pad VARCHAR2(4000),
  5    pad_virt varchar2(4000) generated always as (substr(pad,1,10)) virtual,
  6    CONSTRAINT t1_pk PRIMARY KEY(id)
  7  );
SQL>
SQL> CREATE TABLE t2 (
  2    id NUMBER NOT NULL,
  3    t1_id NUMBER NOT NULL,
  4    n NUMBER,
  5    pad VARCHAR2(4000),
  6    CONSTRAINT t2_pk PRIMARY KEY(id),
  7    CONSTRAINT t2_t1_fk FOREIGN KEY (t1_id) REFERENCES t1
  8  );
SQL>
SQL> CREATE OR REPLACE VIEW v AS
  2  SELECT t1.id AS t1_id, t1.n AS t1_n, t2.id AS t2_id, t2.n AS t2_n
  3    FROM t1, t2
  4   WHERE t1.id = t2.t1_id;
```

Let us select rows only from the child table:

```sql
SQL> EXPLAIN PLAN FOR SELECT t2_id, t2_n FROM v;
SQL>
SQL> select * from table(dbms_xplan.display);

PLAN_TABLE_OUTPUT
-----------------------------------------------------------------------------
Plan hash value: 733458710

----------------------------------------------------------------------------
| Id  | Operation          | Name  | Rows  | Bytes | Cost (%CPU)| Time     |
----------------------------------------------------------------------------
|   0 | SELECT STATEMENT   |       |     1 |    52 |     2   (0)| 00:00:01 |
|   1 |  NESTED LOOPS      |       |     1 |    52 |     2   (0)| 00:00:01 |
|   2 |   TABLE ACCESS FULL| T2    |     1 |    39 |     2   (0)| 00:00:01 |
|*  3 |   INDEX UNIQUE SCAN| T1_PK |     1 |    13 |     0   (0)| 00:00:01 |
----------------------------------------------------------------------------

Predicate Information (identified by operation id):
---------------------------------------------------

   3 - access("T1"."ID"="T2"."T1_ID")
```

The join is not eliminated. It is eliminated after dropping the virtual column, though:

```sql
SQL> ALTER TABLE t1 DROP COLUMN pad_virt;
SQL>
SQL> EXPLAIN PLAN FOR SELECT t2_id, t2_n FROM v;
SQL>
SQL> select * from table(dbms_xplan.display);

PLAN_TABLE_OUTPUT
---------------------------------------------------------------------------
Plan hash value: 2904382265

--------------------------------------------------------------------------
| Id  | Operation         | Name | Rows  | Bytes | Cost (%CPU)| Time     |
--------------------------------------------------------------------------
|   0 | SELECT STATEMENT  |      |     1 |    39 |     2   (0)| 00:00:01 |
|   1 |  TABLE ACCESS FULL| T2   |     1 |    39 |     2   (0)| 00:00:01 |
--------------------------------------------------------------------------
```

I could not find any obvious reason for this behavior in the 10053 trace file. But it looks like the problem is known since 2011 at the very least: [Bug 12739252 : JOIN ELIMINATION IS NOT DONE WHEN JOINING TABLE HAVE VIRTUAL COLUMN](https://support.oracle.com/rs?type=doc&id=12739252.8).
The good news is that the issue is not reproduced in 11.2.0.4.4.
