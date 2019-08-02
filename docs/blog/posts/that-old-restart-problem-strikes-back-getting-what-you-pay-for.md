---
categories:
  - Oracle
date:
  created: 2019-08-02T22:49:00
description: >-
  DML statement restarts can happen for partitioned tables too, but they are handled differently without significant performance penalty.
tags:
  - Diagnostic event
  - OERR
  - Performance
---

# That Old Restart Problem Strikes Back: Getting What You Pay for

During my previous research, I was also testing the same `UPDATE` statement against a partitioned table.
I was slightly puzzled that I did not observe any statement restarts in the performance statistics, even after I updated tens of millions of rows in the partitioned table.
It turns out that there are still statement restarts there, however, they do not lead to such dreadful ramifications when a table is being read three times.

<!-- more -->

The previous article in this series:

1. [That Old Restart Problem Strikes Back: Setting the Stage](that-old-restart-problem-strikes-back-setting-the-stage.md)

## Investigation

!!! note "Disclaimer"

    Please bear in mind, I am talking about statement restarts happening without any concurrent activity in this series of articles.
    Statement restarts when several sessions are involved can result in reading a table being modified several times under these circumstances (I would refer to [the excellent Tanel Poder's video on this subject](https://www.youtube.com/watch?v=jSvk0lxPjzY)).

For this demo, I am going to create a partitioned table with one partition (that is right, one is enough) and populate it with the same data that I used in my previous post:

```sql
SQL> create table big_part(
  2    id int,
  3    pad char(100),
  4    val int)
  5  partition by hash(id)
  6  partitions 1;

Table created.

SQL>
SQL> insert /*+ append*/
  2    into big_part
  3  select rownum,
  4         'x',
  5         case
  6           when rownum <= 10000000 - 100000
  7           then 0
  8           else 1
  9         end
 10    from xmltable('1 to 10000000');

10000000 rows created.

SQL>
SQL> commit;

Commit complete.

SQL>
SQL> select partition_name, blocks, bytes/power(2,20) mbytes
  2    from user_segments
  3   where segment_name = 'BIG_PART';

PARTITION_NAME      BLOCKS     MBYTES
--------------- ---------- ----------
SYS_P3408           159744       1248

SQL>
SQL> select val, count(*)
  2    from big_part
  3   group by val
  4   order by val;

       VAL   COUNT(*)
---------- ----------
         0    9900000
         1     100000
```

Let us update the table:

```sql
SQL> alter session set events 'trace[dml]:sql_trace wait=true';

Session altered.

SQL>
SQL> select name, value
  2    from v$mystat natural join v$statname
  3   where name in ('db block gets', 'consistent gets')
  4   order by name;

NAME                                                                  VALUE
---------------------------------------------------------------- ----------
consistent gets                                                        2472
db block gets                                                             6

SQL>
SQL> update big_part
  2     set val = val + 1
  3   where val = 1;

100000 rows updated.

SQL>
SQL> select name, value
  2    from v$mystat natural join v$statname
  3   where name in ('db block gets', 'consistent gets')
  4   order by name;

NAME                                                                  VALUE
---------------------------------------------------------------- ----------
consistent gets                                                      161286
db block gets                                                        103448
```

We performed ***160K*** consistent gets and ***100K*** current gets which is perfectly fine for a ***160K*** table.

The SQL Monitoring report does not contain anything unusual:

```sql
SQL> select dbms_sqltune.report_sql_monitor('2k4ggcsqqwjgb') from dual;

DBMS_SQLTUNE.REPORT_SQL_MONITOR('2K4GGCSQQWJGB')
--------------------------------------------------------------------------------------------------------------------------------------------------------------
SQL Monitoring Report

SQL Text
------------------------------
update big_part set val = val + 1 where val = 1

Global Information
------------------------------
 Status              :  DONE
 Instance ID         :  1
 Session             :  TC (44:11676)
 SQL ID              :  2k4ggcsqqwjgb
 SQL Execution ID    :  16777218
 Execution Started   :  08/01/2019 09:26:06
 First Refresh Time  :  08/01/2019 09:26:10
 Last Refresh Time   :  08/01/2019 09:26:14
 Duration            :  8s
 Module/Action       :  SQL*Plus/-
 Service             :  pdb
 Program             :  sqlplus.exe

Global Stats
======================================================================
| Elapsed |   Cpu   |    IO    | Application | Buffer | Read | Read  |
| Time(s) | Time(s) | Waits(s) |  Waits(s)   |  Gets  | Reqs | Bytes |
======================================================================
|    7.80 |    3.04 |     4.76 |        0.00 |   262K | 5211 |   1GB |
======================================================================

SQL Plan Monitoring Details (Plan Hash Value=1296248929)
==============================================================================================================================================================
| Id |        Operation         |   Name   |  Rows   | Cost  |   Time    | Start  | Execs |   Rows   | Read | Read  | Activity |       Activity Detail       |
|    |                          |          | (Estim) |       | Active(s) | Active |       | (Actual) | Reqs | Bytes |   (%)    |         (# samples)         |
==============================================================================================================================================================
|  0 | UPDATE STATEMENT         |          |         |       |         3 |     +6 |     1 |        0 |      |       |          |                             |
|  1 |   UPDATE                 | BIG_PART |         |       |         4 |     +5 |     1 |        0 | 2724 |  21MB |    42.86 | Cpu (1)                     |
|    |                          |          |         |       |           |        |       |          |      |       |          | db file sequential read (2) |
|  2 |    PARTITION HASH SINGLE |          |    157K | 43213 |         3 |     +6 |     1 |     100K |      |       |          |                             |
|  3 |     TABLE ACCESS FULL    | BIG_PART |    157K | 43213 |         8 |     +1 |     1 |     100K | 2487 |   1GB |    57.14 | direct path read (4)        |
==============================================================================================================================================================
```

The exact amount of data read is ***1259MB*** and our single partition is ***1248MB*** in size:

```sql
SQL> select physical_read_bytes/power(2,20) read_mbytes
  2    from v$sql_monitor
  3   where sql_id = '2k4ggcsqqwjgb'
  4     and sql_exec_id = 16777218
  5     and sid = sys_context('userenv', 'sid');

READ_MBYTES
-----------
   1259.625
```

The same update took ***16*** seconds and read ***3.6G*** for a non-partitioned table, so that this partitioned table update is twice as faster and reads three times less data.

It might have seen as if there were no statement restarts but it would be a misconception.
The relevant entries from the trace file are below:

```sql hl_lines="19 21"
PARSING IN CURSOR #140643497507696 len=51 dep=0 uid=138 oct=6 lid=138 tim=2670664237436 hv=762201579 ad='ba7d5268' sqlid='2k4ggcsqqwjgb'
update big_part
   set val = val + 1
 where val = 1
END OF STMT
PARSE #140643497507696:c=42246,e=64115,p=14,cr=291,cu=0,mis=1,r=0,dep=0,og=1,plh=1296248929,tim=2670664237436
updSetExecCmpColInfo: not RHS: objn=136464, cid=3
  kduukcmpf=0x7fea236d560a, kduukcmpl=0x7fea236d5608, kduukcmpp=(nil)
updThreePhaseExe: objn=136464 phase=NOT LOCKED
updaul: phase is NOT LOCKED snap oldsnap env: (scn: 0x8000.02777f0c  xid: 0x0000.000.00000000  uba: 0x00000000.0000.00  statement num=0  parent xid: xid: 0x0000.000.00000000  scn: 0x0000.00000000  97sch: scn: 0x0000.00000000  mascn: (scn: 0x8000.02777ef6) env: (scn: 0x0000.00000000  xid: 0x0000.000.00000000  uba: 0x00000000.0000.00  statement num=0  parent xid: xid: 0x0000.000.00000000  scn: 0x0000.00000000  512sch: scn: 0x0000.00000000  mascn: (scn: 0x0000.00000000)
..
updrow: kauupd objn:136465 table:0 rowMigrated:FALSE  rowid 00021511.098b274b.34 code 0
updrow: objn=136464 phase=NOT LOCKED
updrow: kauupd objn:136465 table:0 rowMigrated:FALSE  rowid 00021511.098b274b.35 code 0
updrow: objn=136464 phase=NOT LOCKED
updrow: kauupd objn:136465 table:0 rowMigrated:FALSE  rowid 00021511.098b274b.36 code 0
.. a lot of updrow calls ..
..
updrow: objn=136464 error=1551
updrow: qecinvsub objn=136464
updrow: setting ROW_RETRY objn=136464
updrow: retry_this_row: ROW_RETRY set, objn= 136464 phase=NOT LOCKED
updrow: kauupd objn:136465 table:0 rowMigrated:FALSE  rowid 00021511.098b27ab.37 code 0
updrow: objn=136464 phase=NOT LOCKED
..
STAT #140643497507696 id=1 cnt=0 pid=0 pos=1 obj=0 op='UPDATE  BIG_PART (cr=158523 pr=161232 pw=0 str=1 time=7769538 us)'
STAT #140643497507696 id=2 cnt=100000 pid=1 pos=1 obj=0 op='PARTITION HASH SINGLE PARTITION: 1 1 (cr=158514 pr=158508 pw=0 str=1 time=4086054 us cost=43213 size=2035865 card=156605)'
STAT #140643497507696 id=3 cnt=100000 pid=2 pos=1 obj=136464 op='TABLE ACCESS FULL BIG_PART PARTITION: 1 1 (cr=158514 pr=158508 pw=0 str=1 time=4063030 us cost=43213 size=2035865 card=156605)'
```

Although we got the same `ORA-01551` error, it was gracefully handled using some ***ROW\_RETRY*** logic without resorting to the ***LOCK/UPDATE*** sequence.
It can also be spotted that Oracle uses the `updrow` function whereas it used `updrowFastPath` for the non-partitioned table from my previous post.
It seems to be because of a different code path - partitioned tables just processed by another routine within Oracle kernel: `updrow`.
Non-partitioned tables are going through the `updrowFastPath` function that does not follow the cheap ***ROW\_RETRY*** flow, so when we get an `ORA-01551` error the underlying Oracle routine restarts the whole statement from scratch to pass it through the ***LOCK/UPDATE*** sequence.

## tl;dr.

This post demonstrates that a certain kind of statement restart, which are presumably caused by `ORA-01551`, are handled differently for partitioned tables than for non-partitioned ones.
The consequences are such that updates performed to partitioned tables can be much faster than the same updates against non-partitioned tables (it was twice as faster in the example from this post).
Hence, that is where this joking title ***getting what you pay for*** is coming from - ***Oracle Partitioning*** option costs money after all (I don't want to say that Oracle made this deliberately - it's just a random consequence of that statement restart anomaly).
