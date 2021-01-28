---
categories:
  - Oracle
date:
  created: 2021-01-28T01:52:00
description: >-
  The post demonstrates that the SYS user can create extended data types columns even when MAX_STRING_SIZE is standard.
tags:
  - 12c
  - 18c
  - 19c
  - Initialization parameter
  - LOB
  - OERR
---

# SYS and Extended Data Types

It is a widely known fact that Oracle supports a maximum size of 32,767 bytes for the `VARCHAR2`, `NVARCHAR2`, and `RAW` data types ([Extended Data Types](https://docs.oracle.com/en/database/oracle/oracle-database/19/sqlrf/Data-Types.html#GUID-8EFA29E9-E8D8-40A6-A43E-954908C954A4)) provided that `MAX_STRING_SIZE = EXTENDED`.
What I recently discovered is that `SYS` can create such columns even when `MAX_STRING_SIZE = STANDARD`.

<!-- more -->

It is possible in 12.2, 18c, 19c.
I am unsure about 12.1 since I do not have any of those at the moment.

Firstly, let us try to create a table with a `VARCHAR2(32767)` column as a non-`SYS` user:

```sql hl_lines="7 20"
SQL> conn tc/tc@localhost/pdb2
Connected.
SQL> sho parameter max_string_size

NAME                                 TYPE        VALUE
------------------------------------ ----------- ------------------------------
max_string_size                      string      STANDARD
SQL> select banner_full from v$version;

BANNER_FULL
--------------------------------------------------------------------------------
Oracle Database 19c Enterprise Edition Release 19.0.0.0.0 - Production
Version 19.10.0.0.0


SQL> create table t(c varchar2(32767));
create table t(c varchar2(32767))
                          *
ERROR at line 1:
ORA-00910: specified length too long for its datatype
```

It fails as expected.

Now I try the same as `SYS` - I also switch to my root container to verify that `MAX_STRING_SIZE = STANDARD` everywhere:

```sql hl_lines="36"
SQL> conn sys/Oracle123@localhost/orcl2 as sysdba
Connected.
SQL> alter session set container=cdb$root;

Session altered.

SQL> sho parameter max_string_size

NAME                                 TYPE        VALUE
------------------------------------ ----------- ------------------------------
max_string_size                      string      STANDARD
SQL> alter session set container=pdb2;

Session altered.

SQL> sho parameter max_string_size

NAME                                 TYPE        VALUE
------------------------------------ ----------- ------------------------------
max_string_size                      string      STANDARD
SQL> select banner_full from v$version;

BANNER_FULL
--------------------------------------------------------------------------------
Oracle Database 19c Enterprise Edition Release 19.0.0.0.0 - Production
Version 19.10.0.0.0


SQL> create table t(c varchar2(32767));

Table created.

SQL> desc t
 Name                                      Null?    Type
 ----------------------------------------- -------- ----------------------------
 C                                                  VARCHAR2(32767)
```

Let us try to run a DML command:

```sql hl_lines="1 9"
SQL> insert into t values (lpad('x',32767,'x'));

1 row created.

SQL> select length(c) from t;

 LENGTH(C)
----------
      4000
```

Although it was possible to create a 32K column, somewhere between `LPAD` and the data layer I still got 4,000 bytes only.

But is it limited to 4,000 bytes?
Not really as the example below demonstrates:

```sql hl_lines="73 81 88"
SQL> update t
  2     set c=c||'y';

1 row updated.

SQL> select length(c) from t;

 LENGTH(C)
----------
      4001

SQL>
SQL> update t
  2     set c=c||c;

1 row updated.

SQL> select length(c) from t;

 LENGTH(C)
----------
      8002

SQL>
SQL> update t
  2     set c=c||c;

1 row updated.

SQL> select length(c) from t;

 LENGTH(C)
----------
     16004

SQL>
SQL> update t
  2     set c=c||c;

1 row updated.

SQL> select length(c) from t;

 LENGTH(C)
----------
     32008

SQL>
SQL> update t
  2     set c=c||c;
update t
*
ERROR at line 1:
ORA-01489: result of string concatenation is too long


SQL> select length(c) from t;

 LENGTH(C)
----------
     32008

SQL>
SQL> update t
  2     set c=c||lpad('x',759,'x');

1 row updated.

SQL> select length(c) from t;

 LENGTH(C)
----------
     32767

SQL>
SQL> update t
  2     set c=c||'x';
update t
       *
ERROR at line 1:
ORA-01489: result of string concatenation is too long


SQL> select length(c) from t;

 LENGTH(C)
----------
     32767
```

As expected Oracle stores the column as a LOB under the hood:

```sql hl_lines="23"
SQL> select dbms_metadata.get_ddl('TABLE', 'T') from dual;

DBMS_METADATA.GET_DDL('TABLE','T')
--------------------------------------------------------------------------------

  CREATE TABLE "SYS"."T"
   (    "C" VARCHAR2(32767)
   ) PCTFREE 10 PCTUSED 40 INITRANS 1 MAXTRANS 255
 NOCOMPRESS LOGGING
  STORAGE(INITIAL 65536 NEXT 1048576 MINEXTENTS 1 MAXEXTENTS 2147483645
  PCTINCREASE 0 FREELISTS 1 FREELIST GROUPS 1
  BUFFER_POOL DEFAULT FLASH_CACHE DEFAULT CELL_FLASH_CACHE DEFAULT)
  TABLESPACE "SYSTEM"


SQL>
SQL> select column_name, segment_name, index_name, securefile
  2    from user_lobs
  3   where table_name='T';

COLUMN_NAME SEGMENT_NAME              INDEX_NAME                SECUREFILE
----------- ------------------------- ------------------------- ----------
C           SYS_LOB0000023954C00001$$ SYS_IL0000023954C00001$$  NO
```

Turns out that Oracle uses that internally:

```sql
SQL> drop table t;

Table dropped.

SQL>
SQL> select table_name, column_name, data_length
  2    from user_tab_cols
  3   where data_type = 'VARCHAR2'
  4     and data_length > 4000;

TABLE_NAME                COLUMN_NAME          DATA_LENGTH
------------------------- -------------------- -----------
OPATCH_SQL_PATCHES        NODE_NAMES                 32000
SYSDBIMFS_METADATA$       VALUE                       4096
SCHEDULER$_CREDENTIAL     KEY                        32767
V_$DIAG_LOG_EXT           SUPPLEMENTAL_DETAILS        4003
```

Originally I discovered that Oracle uses `VARCHAR2(32767)` in its scripts which threw me into a tizzy since the scripts were running without errors in `MAX_STRING_SIZE = STANDARD` databases.
It is yet another confirmation that it is not a good idea to use `SYS` to do things.
`SYS` is [a "special" user](https://asktom.oracle.com/pls/apex/f?p=100:11:0::::P11_QUESTION_ID:18785088712670).
