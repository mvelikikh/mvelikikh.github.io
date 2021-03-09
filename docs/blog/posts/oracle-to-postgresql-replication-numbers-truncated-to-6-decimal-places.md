---
categories:
  - Oracle
date:
  created: 2021-03-09T02:17:00
description: >-
  GoldenGate replication from Oracle Database to PostgreSQL truncated some numbers.
  This post explains the cause and offers a couple of workarounds: using a different data type, or setting UnboundedNumericScale in odbc.ini.
tags:
  - GoldenGate
---

# Oracle to PostgreSQL Replication: Numbers Truncated to 6 Decimal Places

I configured an initial load from Oracle to PostgreSQL, and found that some numbers were truncated after the load, e.g. Oracle number `123.0123456789` happened to be `123.012346` in PostgreSQL.
Let us find out how to avoid this.

<!-- more -->


## Setup

### Source: Oracle 	Goldengate 19.1.0.0.4

```
GGSCI (ogg-hub as c##ggadmin@orcl/CDB$ROOT) 9> versions

Operating System:
Linux
Version #2 SMP Fri Mar 29 17:05:02 PDT 2019, Release 4.1.12-124.26.7.el7uek.x86_64
Node: ogg-hub
Machine: Linux

Database:
Oracle Database 19c Enterprise Edition Release 19.0.0.0.0 - Production
```

### Target: Oracle GoldenGate 19.1.0.0.200714 for PostgreSQL

```
GGSCI (ogg-hub as ggadmin@testdb) 8> versions

Operating System:
Linux
Version #2 SMP Fri Mar 29 17:05:02 PDT 2019, Release 4.1.12-124.26.7.el7uek.x86_64
Node: ogg-hub
Machine: Linux

Database:
PostgreSQL
Version 12.06.0000 PostgreSQL 12.6
ODBC Version 03.52.0000
Driver Information:
GGpsql25.so
Version 07.16.0353 (B0519, U0369)
ODBC Version 03.52
```

### odbc.ini

```ini
[ODBC Data Sources]
testdb=PostgreSQL on testdb

[ODBC]
IANAAppCodePage=106
InstallDir=/u01/app/oracle/product/19/ogg_pg_home1

[testdb]
Driver=/u01/app/oracle/product/19/ogg_pg_home1/lib/GGpsql25.so
Description=PostgreSQL 12.6
Database=testdb
HostName=postgres
PortNumber=5432
TransactionErrorBehavior=2
```

### Initial Data

There is a table in the Oracle database:

```sql
SQL> create table tc.test(
  2    id int primary key,
  3    n1 number,
  4    n2 number);

Table created.

SQL>
SQL> insert into tc.test values (0, 123.0123456789, 123.0123456789);

1 row created.

SQL> commit;

Commit complete.

SQL>
SQL> select * from tc.test;

             ID              N1              N2
--------------- --------------- ---------------
              0  123.0123456789  123.0123456789
```

The corresponding PostgreSQL table is this:

```sql
testdb=# create table tc.test(
testdb(#   id bigint primary key,
testdb(#   n1 numeric,
testdb(#   n2 numeric(38,10));
CREATE TABLE
testdb=# \d tc.test
                     Table "tc.test"
 Column |      Type      | Collation | Nullable | Default
--------+----------------+-----------+----------+---------
 id     | bigint         |           | not null |
 n1     | numeric        |           |          |
 n2     | numeric(38,10) |           |          |
Indexes:
    "test_pkey" PRIMARY KEY, btree (id)
```

## GoldenGate Initial Load Processes

### Extract

```
GGSCI (ogg-hub) 1> view params einit

EXTRACT einit
USERIDALIAS oggadmin
RMTHOST ogg-hub, MGRPORT 7810
RMTTASK REPLICAT, GROUP rinit

TABLE pdb.tc.test;
```

### Replicat

```
GGSCI (ogg-hub) 1> view params rinit

REPLICAT rinit
SETENV (PGCLIENTENCODING="UTF8")
SETENV (ODBCINI="/home/ogg/pg/odbc.ini" )
TARGETDB testdb, USERIDALIAS ggadmin
DISCARDFILE ./dirrpt/rinit.dsc, PURGE

MAP pdb.*.*, TARGET *.*;
```

## Performing Initial Load

### Extract

```
GGSCI (ogg-hub) 1> start extract einit

Sending START request to MANAGER ...
EXTRACT EINIT starting
```

### Replicat Report File

```
***********************************************************************
               Oracle GoldenGate Delivery for PostgreSQL
 Version 19.1.0.0.200714 OGGCORE_19.1.0.0.0OGGBP_PLATFORMS_200628.2141
   Linux, x64, 64bit (optimized), PostgreSQL on Jun 29 2020 04:06:46

Copyright (C) 1995, 2019, Oracle and/or its affiliates. All rights reserved.

                    Starting at 2021-03-08 18:05:04
***********************************************************************

Operating System Version:
Linux
Version #2 SMP Fri Mar 29 17:05:02 PDT 2019, Release 4.1.12-124.26.7.el7uek.x86_64
Node: ogg-hub
Machine: x86_64
                         soft limit   hard limit
Address Space Size   :    unlimited    unlimited
Heap Size            :    unlimited    unlimited
File Size            :    unlimited    unlimited
CPU Time             :    unlimited    unlimited

Process id: 15745

Description:

***********************************************************************
**            Running with the following parameters                  **
***********************************************************************

2021-03-08 18:05:09  INFO    OGG-03059  Operating system character set identified as UTF-8.

2021-03-08 18:05:09  INFO    OGG-02695  ANSI SQL parameter syntax is used for parameter parsing.

2021-03-08 18:05:09  INFO    OGG-02095  Successfully set environment variable PGCLIENTENCODING=UTF8.

2021-03-08 18:05:09  INFO    OGG-02095  Successfully set environment variable ODBCINI=/home/ogg/pg/odbc.ini.

2021-03-08 18:05:09  INFO    OGG-01360  REPLICAT is running in Remote Task mode.
REPLICAT rinit
SETENV (PGCLIENTENCODING="UTF8")
SETENV (ODBCINI="/home/ogg/pg/odbc.ini" )
TARGETDB testdb, USERIDALIAS ggadmin

2021-03-08 18:05:09  INFO    OGG-03036  Database character set identified as UTF-8. Locale: en_US.UTF-8.

2021-03-08 18:05:09  INFO    OGG-03037  Session character set identified as UTF-8.
DISCARDFILE ./dirrpt/rinit.dsc, purge
MAP pdb.*.*, TARGET *.*;

2021-03-08 18:05:09  INFO    OGG-01815  Virtual Memory Facilities for: COM
    anon alloc: mmap(MAP_ANON)  anon free: munmap
    file alloc: mmap(MAP_SHARED)  file free: munmap
    target directories:
    /u01/app/oracle/product/19/ogg_pg_home1/dirtmp.

2021-03-08 18:05:09  INFO    OGG-25340
Database Version:
PostgreSQL
Version 12.06.0000 PostgreSQL 12.6
ODBC Version 03.52.0000

Driver Information:
GGpsql25.so
Version 07.16.0353 (B0519, U0369)
ODBC Version 03.52.

2021-03-08 18:05:09  INFO    OGG-25341
Database Language and Character Set:
SERVER_ENCODING = "UTF8"
LC_CTYPE        = "en_US.UTF-8"
TIMEZONE        = "Europe/Dublin".

***********************************************************************
**                     Run Time Messages                             **
***********************************************************************


2021-03-08 18:05:10  INFO    OGG-06506  Wildcard MAP resolved (entry pdb.*.*): MAP "PDB"."TC"."TEST", TARGET "TC"."TEST".

2021-03-08 18:05:10  INFO    OGG-02756  The definition for table PDB.TC.TEST is obtained from the trail file.

2021-03-08 18:05:10  INFO    OGG-06511  Using following columns in default map by name: id, n1, n2.

2021-03-08 18:05:10  INFO    OGG-06510  Using the following key columns for target table tc.test: id.
```

### PostgreSQL

```sql hl_lines="4 12"
testdb=# select * from tc.test;
 id |     n1     |       n2
----+------------+----------------
  0 | 123.012346 | 123.0123456789
(1 row)

testdb=# \d tc.test
                     Table "tc.test"
 Column |      Type      | Collation | Nullable | Default
--------+----------------+-----------+----------+---------
 id     | bigint         |           | not null |
 n1     | numeric        |           |          |
 n2     | numeric(38,10) |           |          |
Indexes:
    "test_pkey" PRIMARY KEY, btree (id)
```

It can be seen that the column `n1` has value `123.012346` rather than the expected value `123.0123456789`.
It is also worth noting that the column `n2` defined as `numeric(38,10)` has the proper value as it is in the source Oracle database.

## Thoughts and Fix

The issue itself is that the number was truncated to 6 decimal places.
It is quite easy to find the same issue was already reported in 2018, but it is still not resolved: [Golden Gate truncating decimal places for number data type post migration](https://community.oracle.com/mosc/discussion/4126912/golden-gate-truncating-decimal-places-for-number-data-type-post-migration).

Firstly, when I encountered that issue, I tried to identify what component is causing this: GoldenGate for Oracle, GoldenGate for PostgreSQL, or maybe PostgreSQL itself.
GoldenGate for PostgreSQL uses Progress DataDirect driver that has an interesting setting: [Unbounded Numeric Scale](https://media.datadirect.com/download/docs/odbc/allodbc/index.html#page/odbc%2Funbounded-numeric-scale.html%23) that has the default value of **6**.
Well it looked like something.
I added that parameter to `odbc.ini`:

```ini hl_lines="8"
[testdb]
Driver=/u01/app/oracle/product/19/ogg_pg_home1/lib/GGpsql25.so
Description=PostgreSQL 12.6
Database=testdb
HostName=ora
PortNumber=5432
TransactionErrorBehavior=2
UnboundedNumericScale=10
```

Having rerun the load from scratch, I finally got the correct number in PostgreSQL:

```sql hl_lines="4"
testdb=# select * from tc.test;
 id |       n1       |       n2
----+----------------+----------------
  0 | 123.0123456789 | 123.0123456789
(1 row)
```

## Conclusion

The ODBC driver used by GoldenGate truncates unbounded numeric columns to 6 decimal places by default.
Thankfully, there is an option to alter it: [Unbounded Numeric Scale](https://media.datadirect.com/download/docs/odbc/allodbc/index.html#page/odbc%2Funbounded-numeric-scale.html%23).
I am disposed to think that it is usually more reliable to specify a certain scale in the target database than relying on such settings.
