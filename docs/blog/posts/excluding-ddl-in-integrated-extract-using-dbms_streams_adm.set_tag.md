---
categories:
  - Oracle
date:
  created: 2016-10-31T13:27:00
description: >-
  TRANLOGOPTIONS EXCLUDETAG in Oracle GoldenGate Extract parameter files allows to filter out DML statements, but it does not work for DDLs.
  TRANLOGOPTIONS _dbfilterddl needs to be added to not replicate DDL statements with a tag.
tags:
  - GoldenGate
---

# Excluding DDL in Integrated Extract using `DBMS_STREAMS_ADM.SET_TAG`

A couple of months ago I had to configure an Oracle GoldenGate Integrated Extract to exclude specific DDL statements from replication.
Having worked a lot with Oracle Streams, I decided to utilize `DBMS_STREAMS_ADM.SET_TAG` for that task.

<!-- more -->

## Configuration

I found a relevant MOS document [How to exclude ddl in IE (integrated extract) issued from a specific user? (Doc ID 2107293.1)](https://support.oracle.com/rs?type=doc&id=2107293.1) pretty fast.
The document suggested adding `TRANLOGOPTIONS EXCLUDETAG` to an extract parameter file, and then all DDL statements preceding with `DBMS_STREAMS_SET.TAG` should not be replicated.
Unfortunately the provided solution did not work for me.

I used OGG Server 12.2.0.1.160823 on Linux x86-64 (which means that I applied the latest bundle patch available at the moment).
The issue can be easily reproduced.
The database version used in this test was 12.1.0.2.160719.
Here are my extract and replicat parameter files:

``` hl_lines="6"
GGSCI (misha2 as tc_ogg_replicat@db2) 112> view params etag

EXTRACT ETAG

USERIDALIAS db1_tc_ogg_extract
TRANLOGOPTIONS EXCLUDETAG 34
LOGALLSUPCOLS
EXTTRAIL ./dirdat/tc
DDL INCLUDE ALL

TABLE TC.*;

GGSCI (misha2 as tc_ogg_replicat@db2) 113> view params rtag

REPLICAT RTAG

USERIDALIAS db2_tc_ogg_replicat

MAP TC.*, TARGET TC.*;
```

The test schema `TC` will be used for the demonstration, and I setup the extract to exclude any logical change records (LCRs) with tag 34.
Then I am going to create and start the OGG processes with using the following script:

??? Show

    ```
    GGSCI (misha2 as tc_ogg_replicat@db2) 138> alter credentialstore add user tc_ogg_extract@db1 password tc_ogg_extract alias db1_tc_ogg_extract


    Credential store in ./dircrd/ altered.

    GGSCI (misha2 as tc_ogg_replicat@db2) 139> alter credentialstore add user tc_ogg_replicat@db2 password tc_ogg_replicat alias db2_tc_ogg_replicat


    Credential store in ./dircrd/ altered.

    GGSCI (misha2 as tc_ogg_replicat@db2) 140>

    GGSCI (misha2 as tc_ogg_replicat@db2) 140> dblogin useridalias db1_tc_ogg_extract

    Successfully logged into database.

    GGSCI (misha2 as tc_ogg_extract@db1) 141> add extract etag integrated tranlog begin now

    EXTRACT (Integrated) added.


    GGSCI (misha2 as tc_ogg_extract@db1) 142> add exttrail ./dirdat/tc extract etag

    EXTTRAIL added.

    GGSCI (misha2 as tc_ogg_extract@db1) 143> register extract etag database


    2016-10-31 12:46:49  INFO    OGG-02003  Extract ETAG successfully registered with database at SCN 39029510.

    GGSCI (misha2 as tc_ogg_extract@db1) 144>

    GGSCI (misha2 as tc_ogg_extract@db1) 146> dblogin useridalias db2_tc_ogg_replicat

    Successfully logged into database.

    GGSCI (misha2 as tc_ogg_replicat@db2) 147> add replicat rtag , integrated, exttrail ./dirdat/tc

    REPLICAT (Integrated) added.


    GGSCI (misha2 as tc_ogg_replicat@db2) 148> start extract etag

    Sending START request to MANAGER ...
    EXTRACT ETAG starting


    GGSCI (misha2 as tc_ogg_replicat@db2) 149> start replicat rtag

    Sending START request to MANAGER ...
    REPLICAT RTAG starting
    ```

I used two databases in my setup - `db1` and `db2` that I call `SOURCE` and `TARGET` in the rest of this blog post for the sake of clarity.
The extract configured to capture the changes from the `SOURCE` database and write data to trail files.
The replicat reads the trail files and applies the changes to the `TARGET` database.

## Filtering DML

Next I am about to run the following code in `SOURCE` from which the extract captures changes:

??? Show

    ```sql
    TC@SOURCE> create sequence t_seq;

    Sequence created.

    TC@SOURCE>
    TC@SOURCE> create table t(
      2    id  int default t_seq.nextval,
      3    msg varchar2(10))
      4  /

    Table created.

    TC@SOURCE>
    TC@SOURCE> insert into t(msg) values ('NO TAG');

    1 row created.

    TC@SOURCE> commit;

    Commit complete.

    TC@SOURCE>
    TC@SOURCE> exec dbms_streams_adm.set_tag( hextoraw('12'))

    PL/SQL procedure successfully completed.

    TC@SOURCE>
    TC@SOURCE> insert into t(msg) values ('TAG '||rawtohex(dbms_streams_adm.get_tag));

    1 row created.

    TC@SOURCE> commit;

    Commit complete.

    TC@SOURCE>
    TC@SOURCE> exec dbms_streams_adm.set_tag( hextoraw('34'))

    PL/SQL procedure successfully completed.

    TC@SOURCE>
    TC@SOURCE> insert into t(msg) values ('TAG '||rawtohex(dbms_streams_adm.get_tag));

    1 row created.

    TC@SOURCE> commit;

    Commit complete.

    TC@SOURCE>
    TC@SOURCE> exec dbms_streams_adm.set_tag( hextoraw('56'))

    PL/SQL procedure successfully completed.

    TC@SOURCE>
    TC@SOURCE> insert into t(msg) values ('TAG '||rawtohex(dbms_streams_adm.get_tag));

    1 row created.

    TC@SOURCE> commit;

    Commit complete.
    ```

Havind done that, I got the following results in the `SOURCE` database:

```sql hl_lines="7"
TC@SOURCE> select * from t;

        ID MSG
---------- ----------
         1 NO TAG
         2 TAG 12
         3 TAG 34
         4 TAG 56
```


And that is in `TARGET`:

```sql
TC@TARGET> select * from t order by id;

        ID MSG
---------- ----------
         1 NO TAG
         2 TAG 12
         4 TAG 56
```

Notice that an insert of a record with `ID=3, MSG="TAG 34"` was not replicated because we have filtered out that record on the extract side.

## Filtering DDL

`TRANLOGOPTIONS EXCLUDETAG` works flawlessly being executed for DML as it is shown above, but it does not work for DDL:

```sql hl_lines="25 26"
TC@SOURCE> exec dbms_streams_adm.set_tag( hextoraw('12'))

PL/SQL procedure successfully completed.

TC@SOURCE>
TC@SOURCE> alter table t add tag12 int;

Table altered.

TC@SOURCE>
TC@SOURCE> exec dbms_streams_adm.set_tag( hextoraw('34'))

PL/SQL procedure successfully completed.

TC@SOURCE>
TC@SOURCE> alter table t add tag34 int;

Table altered.

TC@SOURCE> describe t
 Name                                      Null?    Type
 ----------------------------------------- -------- ----------------------------
 ID                                                 NUMBER(38)
 MSG                                                VARCHAR2(10)
 TAG12                                              NUMBER(38)
 TAG34                                              NUMBER(38)
```

I have added two columns to the table and the second one, `TAG34`, should not have been replicated.
But in fact, both of the commands were replicated:

```sql
TC@TARGET> describe t
 Name                                      Null?    Type
 ----------------------------------------- -------- ----------------------------
 ID                                                 NUMBER(38)
 MSG                                                VARCHAR2(10)
 TAG12                                              NUMBER(38)
 TAG34                                              NUMBER(38)
```

It means that the aforementioned MOS document [How to exclude ddl in IE (integrated extract) issued from a specific user? (Doc ID 2107293.1)](https://support.oracle.com/rs?type=doc&id=2107293.1) does not work in that configuration which, by the way, I think is quite typical.
Luckily, Oracle Support published another note after we concluded our work on the SR: [EXCLUDETAG Issue With Integrated Extract While Excluding DDL For Specific User (Doc ID 2185538.1)](https://support.oracle.com/rs?type=doc&id=2185538.1).

We need to add the following line to the extract parameter file to get it working: `TRANLOGOPTIONS _dbfilterddl`

``` hl_lines="7"
GGSCI (misha2 as tc_ogg_replicat@db2) 168> view params etag

EXTRACT ETAG

USERIDALIAS db1_tc_ogg_extract
TRANLOGOPTIONS EXCLUDETAG 34
TRANLOGOPTIONS _dbfilterddl
LOGALLSUPCOLS
EXTTRAIL ./dirdat/tc
DDL INCLUDE ALL

TABLE TC.*;
```

Once it is added, the same code that adds two columns worked as it should:

```sql hl_lines="7"
TC@SOURCE> describe t
 Name                                      Null?    Type
 ----------------------------------------- -------- ----------------------------
 ID                                                 NUMBER(38)
 MSG                                                VARCHAR2(10)
 TAG12                                              NUMBER(38)
 TAG34                                              NUMBER(38)

TC@TARGET> describe t
 Name                                      Null?    Type
 ----------------------------------------- -------- ----------------------------
 ID                                                 NUMBER(38)
 MSG                                                VARCHAR2(10)
 TAG12                                              NUMBER(38)
```

It can be seen that the `TAG34` column, being added with tag 34, was not replicated.
There is also a new line in the `ggserr.log` file that was not present when I started the extract without `_dbfilterddl`: `Logmining server DDL filtering enabled.`

??? Show

    ``` hl_lines="21"
    2016-10-31 13:54:33  INFO    OGG-00963  Oracle GoldenGate Manager for Oracle, mgr.prm:  Command received from GGSCI on host [172.16.113.245]:57437 (START EXTRACT ETAG ).
    2016-10-31 13:54:33  INFO    OGG-00960  Oracle GoldenGate Manager for Oracle, mgr.prm:  Access granted (rule #6).
    2016-10-31 13:54:34  INFO    OGG-00992  Oracle GoldenGate Capture for Oracle, etag.prm:  EXTRACT ETAG starting.
    2016-10-31 13:54:34  INFO    OGG-03059  Oracle GoldenGate Capture for Oracle, etag.prm:  Operating system character set identified as UTF-8.
    2016-10-31 13:54:34  INFO    OGG-02695  Oracle GoldenGate Capture for Oracle, etag.prm:  ANSI SQL parameter syntax is used for parameter parsing.
    2016-10-31 13:54:38  INFO    OGG-03522  Oracle GoldenGate Capture for Oracle, etag.prm:  Setting session time zone to source database time zone 'GMT'.
    2016-10-31 13:54:38  WARNING OGG-04033  Oracle GoldenGate Capture for Oracle, etag.prm:   LOGALLSUPCOLS has set the NOCOMPRESSDELETES and GETUPDATEBEFORES parameters on.
    2016-10-31 13:54:38  INFO    OGG-01815  Oracle GoldenGate Capture for Oracle, etag.prm:  Virtual Memory Facilities for: BR
        anon alloc: mmap(MAP_ANON)  anon free: munmap
        file alloc: mmap(MAP_SHARED)  file free: munmap
        target directories:
        /u01/app/oracle/12.2.0.1/ggs/BR/ETAG.
    2016-10-31 13:54:38  INFO    OGG-01851  Oracle GoldenGate Capture for Oracle, etag.prm:  filecaching started: thread ID: 140594853938944.
    2016-10-31 13:54:38  INFO    OGG-00975  Oracle GoldenGate Manager for Oracle, mgr.prm:  EXTRACT ETAG starting.
    2016-10-31 13:54:38  INFO    OGG-01815  Oracle GoldenGate Capture for Oracle, etag.prm:  Virtual Memory Facilities for: COM
        anon alloc: mmap(MAP_ANON)  anon free: munmap
        file alloc: mmap(MAP_SHARED)  file free: munmap
        target directories:
        /u01/app/oracle/12.2.0.1/ggs/dirtmp.
    2016-10-31 13:54:58  WARNING OGG-02045  Oracle GoldenGate Capture for Oracle, etag.prm:  Database does not have streams_pool_size initialization parameter configured.
    2016-10-31 13:54:59  INFO    OGG-02248  Oracle GoldenGate Capture for Oracle, etag.prm:  Logmining server DDL filtering enabled.
    2016-10-31 13:55:08  INFO    OGG-02068  Oracle GoldenGate Capture for Oracle, etag.prm:  Integrated capture successfully attached to logmining server OGG$CAP_ETAG using OGGCapture API.
    2016-10-31 13:55:08  INFO    OGG-02089  Oracle GoldenGate Capture for Oracle, etag.prm:  Source redo compatibility version is: 12.1.0.2.0.
    2016-10-31 13:55:08  INFO    OGG-02086  Oracle GoldenGate Capture for Oracle, etag.prm:  Integrated Dictionary will be used.
    2016-10-31 13:55:09  WARNING OGG-02905  Oracle GoldenGate Capture for Oracle, etag.prm:  Replication of OID column in object tables may diverge.
    2016-10-31 13:55:09  INFO    OGG-00993  Oracle GoldenGate Capture for Oracle, etag.prm:  EXTRACT ETAG started.
    ```

## tl;dr

[EXCLUDETAG](http://docs.oracle.com/goldengate/c1221/gg-winux/GWURF/GUID-FEC2FCA4-127D-4A67-A66D-0203BA2DCE2E.htm#GWURF1197) parameter does not work when a tag is set using `DBMS_STREAMS_ADM.SET_TAG` in OGG 12.2.0.1.160823.
It prevents replicating only DML commands and does not restrict DDL commands from being replicated.

We can use an underscore parameter `_dbfilterddl` in the extract parameter file like in the following line:

```
TRANLOGOPTIONS _dbfilterddl
```

This way we restrict both DDL and DML commands from being replicated when the appropriate tag is set (or any in case we use `EXCLUDETAG +` in the extract parameter file).
