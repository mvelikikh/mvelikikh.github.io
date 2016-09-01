---
categories:
  - Oracle
date:
  created: 2016-09-01T12:18:00
description: >-
  GoldenGate initial load using Direct Bulk Load to SQL*Loader may handle unused columns incorrectly, resulting in loading wrong data or errors during load.
  A possible workaround is to drop unused columns in the destination database before initiating the load.
tags:
  - 12c
  - Bug
  - GoldenGate
  - OERR
---

# Incorrect handling of unused columns during GoldenGate initial load using Direct Bulk Load to SQL*Loader

Today I faced an interesting issue performing a GoldenGate initial load with a Direct Bulk Load to SQL\*Loader.
The issue was related to the incorrect handling of unused columns during such loads and can cause incorrect data getting loaded into a database under certain conditions.

<!-- more -->

I tried to reproduce the issue using one database in my setup but was not able to do that, and had to use two databases instead.
I used Oracle Database 12.1.0.2 with DBBP 12.1.0.2.160419 applied and GoldenGate 12.2.0.1.160419 Patch Set.

I am going to use two database in my test case -  let us call them `SOURCE` and `TARGET`.
Firstly, let us create a test schema with a single table, and populate it with some data:

```sql
DBA@SOURCE> grant create session, create table, unlimited tablespace to tc identified by tc;

Grant succeeded.

DBA@SOURCE> conn tc/tc@source
Connected.
TC@SOURCE>
SQL> create table direct_load(
  2    column1 int,
  3    unused1 int,
  4    column2 int,
  5    column3 int);

Table created.

TC@SOURCE>
TC@SOURCE> insert into direct_load values (1, 0, 2, 3);

1 row created.

TC@SOURCE> commit;

Commit complete.

TC@SOURCE> select *
  2    from direct_load;

   COLUMN1    UNUSED1    COLUMN2    COLUMN3
---------- ---------- ---------- ----------
         1          0          2          3
```


Secondly, set the column `UNUSED1` unused:

```sql
TC@SOURCE> alter table direct_load set unused column unused1;

Table altered.
```

Now I will run the same DDL commands in the `TARGET` database, which is obviously what a GoldenGate server will do if we setup DDL replication:

??? Show

    ```sql
    DBA@TARGET> grant create session, create table, unlimited tablespace to tc identified by tc;

    Grant succeeded.

    DBA@TARGET> conn tc/tc@target
    Connected.
    TC@TARGET> create table direct_load(
      2    column1 int,
      3    unused1 int,
      4    column2 int,
      5    column3 int);

    Table created.

    TC@TARGET>
    TC@TARGET> insert into direct_load values (1, 0, 2, 3);

    1 row created.

    TC@TARGET> commit;

    Commit complete.

    TC@TARGET> select *
      2    from direct_load;

       COLUMN1    UNUSED1    COLUMN2    COLUMN3
    ---------- ---------- ---------- ----------
             1          0          2          3

    TC@TARGET>
    TC@TARGET>  alter table direct_load set unused column unused1;
    ```


Consider the scenario when it was decided to resynchronize data in the `TARGET` database from `SOURCE`.
I am going to remove all rows from the table in the `TARGET` database first:

```sql
TC@TARGET> truncate table direct_load;

Table truncated.
```

Proceed with GoldenGate setup.
I want to use GoldenGate Direct Bulk Load to SQL\*Loader capability to move the data from the `SOURCE` database to `TARGET`.
Let us use `IRTC` and `IETC` as the names of an initial load replicat and extract correspondingly:

```
-- setup initial load replicat
GGSCI (ogg-test) 2> edit params irtc
-- UserIdAlias may be customized accordingly to your environment or simply use a username/password pair
Replicat irtc
AssumeTargetDefs
UserIdAlias target_ogg_replicat
DiscardFile ./dirrpt/irtc.dsc, Purge
-- I want to use Direct Bulk Load
BulkLoad
-- I used PDB "orcl" for my experiments:
Map orcl.tc.*, target orcl.tc.*;

-- setup initial load extract
GGSCI (ogg-test) 149> edit params ietc
Extract ietc
RmtHost ogg-test, MgrPort 7809
RmtTask Replicat, Group irtc
UserIdAlias source_ogg_extract
Table orcl.tc.direct_load;

-- creating GoldenGate processes
GGSCI (ogg-test) 116> add replicat irtc SpecialRun

REPLICAT added.

GGSCI (ogg-test) 117> add extract ietc SourceIsTable

EXTRACT added.
```

The setup is finished.
Right now we can try to perform the initial load:

```
GGSCI (ogg-test) 15> info i*tc, tasks

EXTRACT    IETC      Initialized   2016-09-01 08:54   Status STOPPED
Checkpoint Lag       Not Available
Log Read Checkpoint  Not Available
                     First Record         Record 0
Task                 SOURCEISTABLE

REPLICAT   IRTC      Initialized   2016-09-01 08:54   Status STOPPED
Checkpoint Lag       00:00:00 (updated 00:00:28 ago)
Log Read Checkpoint  Not Available
Task                 SPECIALRUN

GGSCI (ogg-test) 16> start extract ietc

Sending START request to MANAGER ...
EXTRACT IETC starting
```

The load completed pretty soon:

```
GGSCI (ogg-test) 17> info i*tc, tasks

EXTRACT    IETC      Last Started 2016-09-01 08:55   Status STOPPED
Checkpoint Lag       Not Available
Log Read Checkpoint  Table ORCL.TC.DIRECT_LOAD
                     2016-09-01 08:55:27  Record 1
Task                 SOURCEISTABLE

REPLICAT   IRTC      Initialized   2016-09-01 08:54   Status STOPPED
Checkpoint Lag       00:00:00 (updated 00:02:09 ago)
Log Read Checkpoint  Not Available
Task                 SPECIALRUN
```

The `ggserr.log` file does not raise any concerns:

??? Show

    ```
    2016-09-01 08:55:11  INFO    OGG-00987  Oracle GoldenGate Command Interpreter for Oracle:  GGSCI command (velikikh): start extract ietc.
    2016-09-01 08:55:11  INFO    OGG-00963  Oracle GoldenGate Manager for Oracle, mgr.prm:  Command received from GGSCI on host [127.0.0.1]:54562 (START EXTRACT IETC ).
    2016-09-01 08:55:11  INFO    OGG-00960  Oracle GoldenGate Manager for Oracle, mgr.prm:  Access granted (rule #8).
    2016-09-01 08:55:11  INFO    OGG-01017  Oracle GoldenGate Capture for Oracle, ietc.prm:  Wildcard resolution set to IMMEDIATE because SOURCEISTABLE is used.
    2016-09-01 08:55:11  INFO    OGG-00992  Oracle GoldenGate Capture for Oracle, ietc.prm:  EXTRACT IETC starting.
    2016-09-01 08:55:11  INFO    OGG-03059  Oracle GoldenGate Capture for Oracle, ietc.prm:  Operating system character set identified as ISO-8859-1.
    2016-09-01 08:55:11  INFO    OGG-02695  Oracle GoldenGate Capture for Oracle, ietc.prm:  ANSI SQL parameter syntax is used for parameter parsing.
    2016-09-01 08:55:12  INFO    OGG-03522  Oracle GoldenGate Capture for Oracle, ietc.prm:  Setting session time zone to source database time zone 'GMT'.
    2016-09-01 08:55:12  WARNING OGG-00752  Oracle GoldenGate Capture for Oracle, ietc.prm:  Failed to validate table ORCL.TC.DIRECT_LOAD. Likely due to existence of unused column. Please make sure you use sourcedefs in downstream Replicat, or the target table has exactly the same unused columns when using ASSUMETARGETDEFS or DDL replication.
    2016-09-01 08:55:12  WARNING OGG-06439  Oracle GoldenGate Capture for Oracle, ietc.prm:  No unique key is defined for table DIRECT_LOAD. All viable columns will be used to represent the key, but may not guarantee uniqueness. KEYCOLS may be used to define the key.
    2016-09-01 08:55:12  INFO    OGG-06509  Oracle GoldenGate Capture for Oracle, ietc.prm:  Using the following key columns for source table ORCL.TC.DIRECT_LOAD: COLUMN1, COLUMN2, COLUMN3.
    2016-09-01 08:55:12  INFO    OGG-01851  Oracle GoldenGate Capture for Oracle, ietc.prm:  filecaching started: thread ID: 7.
    2016-09-01 08:55:12  INFO    OGG-01815  Oracle GoldenGate Capture for Oracle, ietc.prm:  Virtual Memory Facilities for: COM
        anon alloc: mmap(MAP_ANON)  anon free: munmap
        file alloc: mmap(MAP_SHARED)  file free: munmap
        target directories:
        /export/home/velikikh/oracle/12.2.0.1/ggs/dirtmp.
    2016-09-01 08:55:16  INFO    OGG-00975  Oracle GoldenGate Manager for Oracle, mgr.prm:  EXTRACT IETC starting.
    2016-09-01 08:55:16  INFO    OGG-00993  Oracle GoldenGate Capture for Oracle, ietc.prm:  EXTRACT IETC started.
    2016-09-01 08:55:16  INFO    OGG-00963  Oracle GoldenGate Manager for Oracle, mgr.prm:  Command received from EXTRACT on host [127.0.0.1]:58728 (START REPLICAT IRTC CPU -1 PRI -1 PARAMS ).
    2016-09-01 08:55:16  INFO    OGG-00960  Oracle GoldenGate Manager for Oracle, mgr.prm:  Access granted (rule #8).
    2016-09-01 08:55:16  INFO    OGG-01025  Oracle GoldenGate Delivery for Oracle:  REPLICAT task started by manager (port 7810).
    2016-09-01 08:55:21  INFO    OGG-00963  Oracle GoldenGate Manager for Oracle, mgr.prm:  Command received from RMTTASK on host [::1]:59974 (REPORT 3871 7810).
    2016-09-01 08:55:21  INFO    OGG-00960  Oracle GoldenGate Manager for Oracle, mgr.prm:  Access granted (rule #1).
    2016-09-01 08:55:21  INFO    OGG-00973  Oracle GoldenGate Manager for Oracle, mgr.prm:  Manager started replicat task process (Port 7810).
    2016-09-01 08:55:26  INFO    OGG-01229  Oracle GoldenGate Delivery for Oracle:  Connected to ogg-test:50783.
    2016-09-01 08:55:26  INFO    OGG-00995  Oracle GoldenGate Delivery for Oracle, irtc.prm:  REPLICAT IRTC starting.
    2016-09-01 08:55:26  INFO    OGG-03059  Oracle GoldenGate Delivery for Oracle, irtc.prm:  Operating system character set identified as ISO-8859-1.
    2016-09-01 08:55:26  INFO    OGG-02695  Oracle GoldenGate Delivery for Oracle, irtc.prm:  ANSI SQL parameter syntax is used for parameter parsing.
    2016-09-01 08:55:27  INFO    OGG-02679  Oracle GoldenGate Delivery for Oracle, irtc.prm:  The Replicat process logged on to database ORCL and can only apply to that database.
    2016-09-01 08:55:27  INFO    OGG-06451  Oracle GoldenGate Delivery for Oracle, irtc.prm:  Triggers will be suppressed by default.
    2016-09-01 08:55:27  INFO    OGG-01815  Oracle GoldenGate Delivery for Oracle, irtc.prm:  Virtual Memory Facilities for: COM
        anon alloc: mmap(MAP_ANON)  anon free: munmap
        file alloc: mmap(MAP_SHARED)  file free: munmap
        target directories:
        /export/home/velikikh/oracle/12.2.0.1/ggs/dirtmp.
    2016-09-01 08:55:27  INFO    OGG-00996  Oracle GoldenGate Delivery for Oracle, irtc.prm:  REPLICAT IRTC started.
    2016-09-01 08:55:27  INFO    OGG-03522  Oracle GoldenGate Delivery for Oracle, irtc.prm:  Setting session time zone to source database time zone 'GMT'.
    2016-09-01 08:55:27  INFO    OGG-02911  Oracle GoldenGate Capture for Oracle, ietc.prm:  Processing table ORCL.TC.DIRECT_LOAD.
    2016-09-01 08:55:27  INFO    OGG-06495  Oracle GoldenGate Capture for Oracle, ietc.prm:  OGG created a session pool with SESSIONPOOLMAX 10, SESSIONPOOLMIN 2 and SESSIONPOOLINCR 2.
    2016-09-01 08:55:27  WARNING OGG-02760  Oracle GoldenGate Delivery for Oracle, irtc.prm:  ASSUMETARGETDEFS is ignored because trail file  contains table definitions.
    2016-09-01 08:55:27  INFO    OGG-06506  Oracle GoldenGate Delivery for Oracle, irtc.prm:  Wildcard MAP resolved (entry orcl.tc.*): Map "ORCL"."TC"."DIRECT_LOAD", target orcl.tc."DIRECT_LOAD".
    2016-09-01 08:55:28  WARNING OGG-06439  Oracle GoldenGate Delivery for Oracle, irtc.prm:  No unique key is defined for table DIRECT_LOAD. All viable columns will be used to represent the key, but may not guarantee uniqueness. KEYCOLS may be used to define the key.
    2016-09-01 08:55:28  INFO    OGG-02756  Oracle GoldenGate Delivery for Oracle, irtc.prm:  The definition for table ORCL.TC.DIRECT_LOAD is obtained from the trail file.
    2016-09-01 08:55:28  INFO    OGG-06511  Oracle GoldenGate Delivery for Oracle, irtc.prm:  Using following columns in default map by name: COLUMN1, COLUMN2, COLUMN3.
    2016-09-01 08:55:28  INFO    OGG-06510  Oracle GoldenGate Delivery for Oracle, irtc.prm:  Using the following key columns for target table ORCL.TC.DIRECT_LOAD: COLUMN1, COLUMN2, COLUMN3.
    2016-09-01 08:55:28  INFO    OGG-00178  Oracle GoldenGate Delivery for Oracle, irtc.prm:  owner = "TC", table = "DIRECT_LOAD".
    2016-09-01 08:55:28  INFO    OGG-00991  Oracle GoldenGate Capture for Oracle, ietc.prm:  EXTRACT IETC stopped normally.
    2016-09-01 08:55:33  INFO    OGG-00994  Oracle GoldenGate Delivery for Oracle, irtc.prm:  REPLICAT IRTC stopped normally.
    ```

Yes, there was a warning like this:

```
2016-09-01 08:55:12  WARNING OGG-00752  Oracle GoldenGate Capture for Oracle, ietc.prm:  Failed to validate table ORCL.TC.DIRECT_LOAD. Likely due to existence of unused column. Please make sure you use sourcedefs in downstream Replicat, or the target table has exactly the same unused columns when using ASSUMETARGETDEFS or DDL replication.
```

But I obviously did not violate it as the source and the target table has the same unused columns.
Let us see what was actually loaded into the `TARGET` database:

```sql
TC@TARGET> select * from direct_load;

   COLUMN1    COLUMN2    COLUMN3
---------- ---------- ----------
         1                     2
```

That is definitely not what I wanted to load and that differs from the original table in `SOURCE`:

```sql
TC@SOURCE> select * from direct_load;

   COLUMN1    COLUMN2    COLUMN3
---------- ---------- ----------
         1          2          3
```

Clearly the data from `COLUMN2` got loaded into `COLUMN3`, and I did not get any errors afterwards leaving my database with "wrong" data.
That is the worst case scenario.
Originally I faced a similar issue while I was moving a bunch of data from one database to another using GoldenGate.
The load got ABENDED with `ORA-01840` as in that case `COLUMN3` had a `DATE` datatype which may be easily reproduced by the following code:

```sql
SQL> select to_date('2', 'yyyy-mm-dd hh24:mi:ss') from dual;
select to_date('2', 'yyyy-mm-dd hh24:mi:ss') from dual
               *
ERROR at line 1:
ORA-01840: input value not long enough for date format
```

Of course, if you are lucky, you may get some other datatype conversion errors.
If you are not, you may end up with wrong data in a database and it may take a while before the problem is discovered.

A few words about workarounds.
In this simple scenario, which I have written just for demonstration purposes, it was enough to drop unused columns in the `TARGET` database:

```sql
TC@TARGET> alter table direct_load drop unused columns;

Table altered.
```
