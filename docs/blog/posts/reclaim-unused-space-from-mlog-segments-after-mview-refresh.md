---
categories:
  - Oracle
date:
  created: 2015-08-03T15:26:00
  updated: 2016-05-14T12:31:09
description: >-
  How to reclaim unused space from materialized view log segments after materialized view refresh.
  Patch 11072728 - LNX: MVR: SPACE IS NOT RECLAIMED FROM THE MLOG$ SEGMENTS AFTER THE REFRESH, and _bug11072728_mv_refresh_truncate_log DB parameter
tags:
  - 11g
  - Code symbol
  - Diagnostic event
  - Initialization parameter
  - Performance
---

# Reclaim unused space from MLOG$ segments after materialized view refresh

Materialized view log space is not decreased after materialized view refresh is done.
This post discusses how to reclaim the space.

<!-- more -->

We use fast-refreshable materialized views in some of our databases for reporting purposes.
They work fine most of the time.
However, periodically the materialized view log size is increased due to various reasons.
Such as: bulk data loading, abnormal application activities, or delays with materialized view refresh.
After that, even if a materialized view is refreshed, the materialized view log's high-water mark (HWM) is not reset.
It needs to be reset manually, using commands such as `ALTER TABLE SHRINK/MOVE`.
Without resetting the HWM, the materialized view refresh performance can be poor.

The good news is that there is patch 11072728 available for some platforms that can reset the HWM without manual intervention.
This patch is described in the MOS note [Space Not Reclaimed from MLOG$ Segments After MVIEW Refresh (Doc ID 1941137.1)](https://support.oracle.com/rs?type=doc&id=1941137.1)
According to the note, the fix for bug 11072728 will be provided in the upcoming 12.2 release.
I have already requested that patch for Solaris SPARC64 on top of 11.2.0.4.4/11.2.0.4.6.

Today I decided to look closer on patch 11072728 in one of non-production databases.
I want to be sure that the patch will not harm the production instance.

Reading the bug readme, I found that the fix for the bug is not enabled by default.
You need to set an underscore parameter `_bug11072728_mv_refresh_truncate_log` to 1 to enable it.
It is worth noting that the parameter can be altered on both session and system levels:

```sql
SQL> select isses_modifiable,
  2         issys_modifiable
  3    from v$parameter
  4   where name = '_bug11072728_mv_refresh_truncate_log';

ISSES_MODIFIABLE ISSYS_MODIFIABLE
---------------- ----------------
TRUE             IMMEDIATE
```

I used the following script to setup a test schema:

```sql
SQL> grant connect to tc identified by tc;

Grant succeeded.

SQL> grant alter session to tc;

Grant succeeded.

SQL> grant create materialized view to tc;

Grant succeeded.

SQL> grant create table to tc;

Grant succeeded.

SQL> grant unlimited tablespace to tc;

Grant succeeded.

SQL>
SQL> conn tc/tc
Connected.
SQL>
SQL> create table t
  2  as
  3  select *
  4    from all_users;

Table created.

SQL>
SQL> alter table t add constraint t_pk primary key(username);

Table altered.

SQL>
SQL> create materialized view log on t with primary key;

Materialized view log created.

SQL>
SQL> create materialized view mv_t
  2  refresh fast
  3  as
  4  select *
  5    from t;

Materialized view created.
```

The script above creates a table, a materialized view log on it, and a materialized view.
It can be seen that the materialized view log is empty, and its segment has only 8 blocks allocated:

```sql
SQL> select count(*) from mlog$_t;

  COUNT(*)
----------
         0

SQL>
SQL> select blocks
  2    from user_segments
  3   where segment_name = 'MLOG$_T';

    BLOCKS
----------
         8
```


Let us update the table in a loop, 100 times in total, committing on each iteration:

```sql
SQL> begin
  2    for i in 1..100
  3    loop
  4      update t
  5         set created = created
  6       where username <> 'SYS';
  7      commit;
  8    end loop;
  9  end;
 10  /
```

Confirming that the materialized view log is not empty, and its segment is extended:

```sql
SQL> select count(*) from mlog$_t;

  COUNT(*)
----------
     19400

SQL>
SQL> select blocks
  2    from user_segments
  3   where segment_name = 'MLOG$_T';

    BLOCKS
----------
       104
```


Let us refresh the materialized view now:

```sql
SQL> exec dbms_mview.refresh( 'mv_t', method=>'f')

PL/SQL procedure successfully completed.
```

If patch 11072728 was not applied, or the parameter `_bug11072728_mv_refresh_truncate_log` was not set to 1, then the HWM is not reset and the segment space allocated will stay the same:

```sql
SQL> select count(*) from mlog$_t;

  COUNT(*)
----------
         0

SQL>
SQL> select blocks
  2    from user_segments
  3   where segment_name = 'MLOG$_T';

    BLOCKS
----------
       104
```

In a production system with high DML activity materialized view logs can grow to a much larger size.
Thereby degrading materialized view refresh performance.

As it was said previously, without patch 11072728 you need to reset the HWM manually.
With patch 11072829 applied, there is no need to do it anymore.
Just set the parameter `_bug11072728_mv_refresh_truncate_log` to 1:

```sql
SQL> exec dbms_mview.refresh( 'mv_t', method=>'f')

PL/SQL procedure successfully completed.

SQL>
SQL> select count(*) from mlog$_t;

  COUNT(*)
----------
         0

SQL>
SQL> select blocks
  2    from user_segments
  3   where segment_name = 'MLOG$_T';

    BLOCKS
----------
         8
```

It can be seen that the segment allocated space was decreased.

I was also wondering how exactly it works under the hood.
Therefore, I have set up SQL tracing and event 10704 (enqueue trace) to investigate it:

```sql
SQL> alter session set events 'sql_trace bind=true:10704 level 10';

Session altered.

SQL>
SQL> exec dbms_mview.refresh( 'mv_t', method=>'f')

PL/SQL procedure successfully completed.
```

I used the command below to pick out only interesting lines in the trace file:

```bash
egrep "ksqgtl \*|ksqrcl: [^r]|^truncate|select count\(\*\) from .*MLOG" orcl_ora_18632.trc
```

The description of this command:

- `ksqgtl` - get lock function
- `ksqrcl` - release lock function
- We want to show the truncate and `select count(*) from MLOG` commands.

Below is the output of the `egrep` command in which some lines were skipped for brevity:

```
select count(*) from "TC"."MLOG$_T"
ksqgtl *** TM-001854e4-00000000 mode=6 flags=0x401 timeout=0 ***
select count(*) from "TC"."MLOG$_T"
ksqgtl *** TM-001854e6-00000000 mode=6 flags=0x401 timeout=0 ***
truncate table "TC"."MLOG$_T"
```

These commands were executed after the materialized view update was done.

Looks like that the new algorithm with the materialized view log truncate command works in the following way:

1. execute the old refresh code
1. check count of rows in the materialized view log
1. if zero, lock the master table in exclusive mode nowait (`TM` lock with `timeout=0`)
1. check count of rows in the materialized view log again (because there can be DML between steps 2 and 3)
1. lock the materialized view log in exclusive mode nowait (`TM` lock with `timeout=0`)
1. truncate the materialized view log

Based on this, an open transaction will prevent the truncation of the materialized view log.
And that indirectly confirms my assumptions about internal workings of the new refresh algorithm.
Let us update one row in the table in session 1:

```sql
SQL> -- session 1
SQL> update t
  2     set created=created
  3   where username='SYS';

1 row updated.
```

Now we will check the allocated space of the materialized view log before refresh, perform the actual refresh, and check the space again (in another session):

```sql
SQL> -- session 2
SQL> select blocks
  2    from user_segments
  3   where segment_name = 'MLOG$_T';

    BLOCKS
----------
       104

SQL> exec dbms_mview.refresh( 'mv_t', method=>'f')

PL/SQL procedure successfully completed.
SQL>
SQL> select count(*) from mlog$_t;

  COUNT(*)
----------
         0

SQL>
SQL> select blocks
  2    from user_segments
  3   where segment_name = 'MLOG$_T';

    BLOCKS
----------
       104
```

Thus, it confirms that there was no truncate of the materialized view log.

It seems safe to use patch 11072728 in production environments.
If I face any issue with that patch in production, I will update this post.
