---
categories:
  - Oracle
date:
  created: 2019-11-13T21:26:00
description: >-
  SQL92_SECURITY is set to TRUE by default starting from 12.2.0.1.
  It can lead to ORA-01031 errors thrown while executing valid PL/SQL program units.
tags:
  - 12c
  - Initialization parameter
  - OERR
  - PL/SQL
---

# SQL92\_SECURITY and ORA-01031

[SQL92\_SECURITY](https://docs.oracle.com/en/database/oracle/oracle-database/12.2/refrn/SQL92_SECURITY.html#GUID-E41087C2-250E-4201-908B-79E659B22A4B) has changed its default value to `TRUE` starting from 12.2.0.1: [Upgrade Guide](https://docs.oracle.com/en/database/oracle/oracle-database/12.2/upgrd/changes-in-12c-release-2-upgrade.html#GUID-30855EA7-7194-4E09-A676-37CB74BD4C12).
That might lead to `ORA-01031: insufficient privileges` errors being thrown in runtime as this post demonstrates.

<!-- more -->

Consider the following script:

```sql hl_lines="32 40"
SQL> grant create session, create table, unlimited tablespace to tc_data identified by tc_data;

Grant succeeded.

SQL>
SQL> create table tc_data.t
  2  as
  3  select *
  4    from dual;

Table created.

SQL>
SQL> grant create session, create procedure to tc_app identified by tc_app;

Grant succeeded.

SQL>
SQL> grant delete on tc_data.t to tc_app;

Grant succeeded.

SQL>
SQL> create or replace procedure tc_app.p
  2  is
  3  begin
  4    delete tc_data.t
  5     where dummy = 'X';
  6  end;
  7  /

Procedure created.

SQL>
SQL> exec tc_app.p
BEGIN tc_app.p; END;

*
ERROR at line 1:
ORA-01031: insufficient privileges
ORA-06512: at "TC_APP.P", line 4
ORA-06512: at line 1
```

Although the procedure is valid, it throws an `ORA-01031` error as soon as the statement refers to any table columns including pseudo-columns, such as `ROWID` (I have tested it only for `ROWID`).

I have even seen a case similar to the one below, when the code throws an error depending on its input parameters:

```sql hl_lines="15 22"
SQL> create or replace procedure tc_app.p_collection(p_tbl sys.odcivarchar2list)
  2  is
  3  begin
  4    forall i in 1..p_tbl.count
  5      delete tc_data.t
  6       where dummy = p_tbl(i);
  7  end;
  8  /

Procedure created.

SQL>
SQL> exec tc_app.p_collection(sys.odcivarchar2list())

PL/SQL procedure successfully completed.

SQL> exec tc_app.p_collection(sys.odcivarchar2list('y'))
BEGIN tc_app.p_collection(sys.odcivarchar2list('y')); END;

*
ERROR at line 1:
ORA-01031: insufficient privileges
ORA-06512: at "TC_APP.P_COLLECTION", line 4
ORA-06512: at line 1
```

I can imagine that Oracle has not implemented the behavior when the code does not compile if it is known that there is a missing privilege due to `SQL92_SECURITY=TRUE` - it is just an instance parameter and it can be changed back and forth.
Thus, it would make the status of the objects misleading.
For instance, a valid PL/SQL unit with `SQL92_SECURITY=FALSE` should either become invalid or throw a runtime `ORA-01031` error when `SQL92_SECURITY=TRUE`.
However, it might come in handy to have a PL/SQL warning at least to identify possible missing privileges.
It can also be a good idea to change the scope of the [SQL92\_SECURITY](https://docs.oracle.com/en/database/oracle/oracle-database/12.2/refrn/SQL92_SECURITY.html#GUID-E41087C2-250E-4201-908B-79E659B22A4B) parameter and make it one of the PL/SQL compiler settings of the stored objects shown in [DBA\_PLSQL\_OBJECT\_SETTINGS](https://docs.oracle.com/en/database/oracle/oracle-database/12.2/refrn/ALL_PLSQL_OBJECT_SETTINGS.html#GUID-7EF7B6E3-50B1-43C3-A56E-40955B47C65D).
