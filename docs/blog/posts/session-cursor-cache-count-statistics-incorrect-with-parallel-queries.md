---
categories:
  - Oracle
date:
  created: 2015-05-21T10:01:00
  updated: 2015-06-17T00:00:00
description: >-
  Found a case when there were high session cursor cache count statistics for parallel queries.
  The issue was resolved by an Oracle patch 21135007: SESSION CURSOR CACHE COUNT STATISTICS IS INCORRECT
tags:
  - 11g
  - Bug
  - PX
---

# Session cursor cache count statistics incorrect with parallel queries

I have recently investigated an issue with high `session cursor cache count` statistics in one of 11.2.0.4 databases.
I found that some of sessions have extremely high values of these statistics.

<!-- more -->

## Investigation

```sql hl_lines="12 13 14"
SQL> select s.sid, ss.value, s.logon_time, s.service_name, s.program
  2    from v$session s,
  3         v$statname sn,
  4         v$sesstat ss
  5   where sn.name='session cursor cache count'
  6     and ss.statistic#=sn.statistic#
  7     and ss.value > 100
  8     and s.sid=ss.sid;

       SID      VALUE LOGON_TIME          SERVICE_NAME PROGRAM
---------- ---------- ------------------- ------------ ----------------
       485        255 19.05.2015 02:47:52 dp_task      JDBC Thin Client
       705      12774 19.05.2015 02:47:51 dp_task      JDBC Thin Client
       800        267 19.05.2015 02:47:51 dp_task      JDBC Thin Client
```

the `session_cached_cursors` parameter has a default value of 50.
My first thought was that the sessions changed the `session_cached_cursors` parameter.
To confirm this hypothesis, I executed the following oradebug command:

```
oradebug dump modified_parameters 1
```

Looking into the trace file:

```
Received ORADEBUG command (#1) 'dump modified_parameters 1' from process 'Unix process pid: 13761, image: <none>'
DYNAMICALLY MODIFIED PARAMETERS:
  nls_language             = AMERICAN
  nls_territory            = AMERICA
  log_archive_dest_state_3 = ENABLE
  service_names            = drep_dp_stat, drep_dp_task, drep_ora_at, drep_dp_core

*** 2015-05-14 10:44:20.744
Finished processing ORADEBUG command (#1) 'dump modified_parameters 1'
```

So `session_cached_cursors` parameter wasn't changed by the session.
At the next step I decided to dump all cursors cached by the session:

```
oradebug dump cursordump 1
```

Here is the relevant portion of trace file:

``` hl_lines="6"
----- Session Cached Cursor Dump -----
----- Generic Session Cached Cursor Dump -----
-----------------------------------------------------------
-------------- Generic Session Cached Cursors Dump --------
-----------------------------------------------------------
hash table=ffffffff79d34228 cnt=50 LRU=ffffffff79d245f0 cnt=49 hit=64510 max=50 NumberOfTypes=6
```

From the above, there was no doubt that the `session cursor cache count` statistic is lying.
I opened an SR with Oracle and the support engineer pointed to a [Bug 5713223 : 'SESSION CURSOR CACHE COUNT' OF V$SYSSTAT IS NOT CURRENT VALUE](https://support.oracle.com/rs?type=bug&id=5713223).
This bug was opened in 2006 for 10.2 version and is still not resolved yet.

I have a couple of SRs with Oracle in which I wait for the resolution of such long lived bugs.
So, I decided to further diagnose this issue and provide additional information to the Oracle Support.

All of the sessions are using the `dp_task` database service.
I created this service for a reporting application that executes a bunch of heavy SQL.

I wrote a simple job that takes a snapshot of `v$session`, `v$sesstat` on periodic interval.
On the next day I checked the generated data and found a couple of suspicious SQL statements for further investigation.

Most of the SQLs used some combination of: PARALLEL/MATERIALIZE hints, and pipelined table functions.
Deeping into this further, I found that the incorrect statistics are due to the PARALLEL hint.

## Reproduction

I created a simple test case that can be used to reproduce the issue.

??? Show
    ```sql
    create table t as select * from dba_objects;

    sho parameter session_cached_cursors

    select s.value
      from v$statname n,
           v$mystat s
     where n.name = 'session cursor cache count'
       and s.statistic#=n.statistic#;

    select /*+ parallel(4)*/count(distinct owner) from t;

    select s.value
      from v$statname n,
           v$mystat s
     where n.name = 'session cursor cache count'
       and s.statistic#=n.statistic#;

    select /*+ parallel(4)*/count(distinct owner) from t;
    ```

Here is a SQL*Plus output of the script execution:

```sql hl_lines="5 15 33"
SQL> sho parameter session_cached_cursors

NAME                                 TYPE                              VALUE
------------------------------------ --------------------------------- ------------------------------
session_cached_cursors               integer                           50
SQL>
SQL> select s.value
  2    from v$statname n,
  3         v$mystat s
  4   where n.name = 'session cursor cache count'
  5     and s.statistic#=n.statistic#;

     VALUE
----------
        49

SQL>
SQL> select /*+ parallel(4)*/count(distinct owner) from t;

COUNT(DISTINCTOWNER)
--------------------
                  59

SQL>
SQL> select s.value
  2    from v$statname n,
  3         v$mystat s
  4   where n.name = 'session cursor cache count'
  5     and s.statistic#=n.statistic#;

     VALUE
----------
        58
```

Notice that the `session cursor cache count` statistic is 49 before the parallel query is run and 58 after.
After I executed the parallel query multiple times checking statistics at each step, I found that each query execution leads to an increase of the `session cursor cache count` statistics by `2*parallel_degree`.

```sql hl_lines="1 15 17 32"
SQL> select /*+ parallel(4)*/count(distinct owner) from t;

COUNT(DISTINCTOWNER)
--------------------
                  59
SQL>
SQL> select s.value
  2    from v$statname n,
  3         v$mystat s
  4   where n.name = 'session cursor cache count'
  5     and s.statistic#=n.statistic#;

     VALUE
----------
        98
SQL>
SQL> select /*+ parallel(8)*/count(distinct owner) from t;

COUNT(DISTINCTOWNER)
--------------------
                  59

SQL>
SQL> select s.value
  2    from v$statname n,
  3         v$mystat s
  4   where n.name = 'session cursor cache count'
  5     and s.statistic#=n.statistic#;

     VALUE
----------
       114
SQL>
```

The good news is that the issue is not reproduced in 12.1.0.2.
I hope that Oracle support resolve this issue in 11.2.0.4 too.

## Update 17.06.2015

Oracle released a new patch [21135007: SESSION CURSOR CACHE COUNT STATISTICS IS INCORRECT](https://updates.oracle.com/ARULink/PatchSearch/process_form?bug=21135007).
I applied it to the 11.2.0.4 environment and can confirm that it works as expected.
Now the `session cursor cache count` statistics are correct in the problem scenario.
