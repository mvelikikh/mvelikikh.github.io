---
categories:
  - Oracle
date:
  created: 2021-11-30T16:53:00
description: >-
  An undocumented parameter read_only is introduced in Oracle Database 21c.
  It allows to enable read-only mode for a user session, preventing any writes.
tags:
  - 21c
  - Initialization parameter
  - OERR
---

# Setting database session to read only in 21c

Oracle introduced a new parameter `read_only` in 21c which is not documented in [Database Reference](https://docs.oracle.com/en/database/oracle/oracle-database/21/refrn/) yet at the time of this writing.
It allows to enable read-only mode for a user session, preventing any writes.
This post demonstrates how it works.

<!-- more -->

```sql
[oracle@db-21 ~]$ sqlplus /nolog @q

SQL*Plus: Release 21.0.0.0.0 - Production on Tue Nov 30 10:39:56 2021
Version 21.4.0.0.0

Copyright (c) 1982, 2021, Oracle.  All rights reserved.

SQL>
SQL> conn tc/tc@db-21/pdb
Connected.
SQL>
SQL> create table t(x int);

Table created.

SQL>
SQL> insert into t values (0);

1 row created.

SQL> commit;

Commit complete.

SQL>
SQL> alter session set read_only=true;

Session altered.

SQL>
SQL> update t
  2     set x=1;
update t
       *
ERROR at line 1:
ORA-16000: database or pluggable database open for read-only access


SQL>
SQL> create table new_tab(x int);
create table new_tab(x int)
*
ERROR at line 1:
ORA-16000: database or pluggable database open for read-only access


SQL>
SQL> select *
  2    from t
  3    for update;
  from t
       *
ERROR at line 2:
ORA-16000: database or pluggable database open for read-only access


SQL>
SQL> lock table t in exclusive mode;
lock table t in exclusive mode
*
ERROR at line 1:
ORA-16000: database or pluggable database open for read-only access


SQL>
SQL> alter session set read_only=false;

Session altered.

SQL>
SQL> update t
  2     set x=1;

1 row updated.

SQL>
SQL> create table new_tab(x int);

Table created.

SQL>
SQL> select *
  2    from t
  3    for update;

         X
----------
         1

SQL>
SQL> lock table t in exclusive mode;

Table(s) Locked.
```

I believe it was originally introduced for Oracle Autonomous Database offerings since it is the only place where it is documented: [Change Autonomous Database Operation Mode to Read/Write Read-Only or Restricted](https://docs.oracle.com/en/cloud/paas/autonomous-database/adbsa/autonomous-read-only-mode.html#GUID-F9417F91-0C56-4899-8595-4279F16EEC7D).
There are no comparable database features that can provide the same functionality at this level of granularity.
A typical usage of this when some application sessions should be set to Read-Only.
We can set `read_only=true` in a logon trigger for that:

```sql
SQL> create or replace trigger logon_trg
  2  after logon on tc.schema
  3  declare
  4  begin
  5    execute immediate 'alter session set read_only=true';
  6  end;
  7  /

Trigger created.

SQL>
SQL> conn tc/tc@db-21/pdb
Connected.
SQL> select *
  2    from t
  3    for update;
select *
*
ERROR at line 1:
ORA-16000: database or pluggable database open for read-only access


SQL>
SQL> conn system/manager@db-21/pdb
Connected.
SQL> select *
  2    from tc.t
  3    for update;

         X
----------
         1
```
