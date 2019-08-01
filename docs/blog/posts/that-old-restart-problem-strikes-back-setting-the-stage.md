---
categories:
  - Oracle
date:
  created: 2019-08-01T23:50:00
description: >-
  Demonstrated a case of Oracle DML statement restarts happening in a single session due to ORA-1551.
  SQL Monitoring reports, or events trace[SQL_DML] and sql_trace can be used to identify the restarts.
tags:
  - 12c
  - 19c
  - Diagnostic event
  - Initialization parameter
  - OERR
  - Performance
---

# That Old Restart Problem Strikes Back: Setting the Stage

When I was reading about [statement restarts](https://asktom.oracle.com/Misc/that-old-restart-problem-again.html), I thought it usually happens in a multi-user system or in the presence of triggers.
However, last week one of our developers asked me to help him to figure out why a simple update statement was reading far more data than it was in the table.
That blog post is published to share my findings about that.

<!-- more -->

## Investigation

I created a simple non-partitioned table for this demo that I performed on the Oracle Database ***12.2.0.1.190416*** (the issue has been also reproduced on ***19.4.0.0.190716***):

```sql
SQL> create table big(id int, pad char(100), val int);

Table created.

SQL>
SQL> insert /*+ append*/
  2    into big
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
SQL> select blocks, bytes/power(2,20) mbytes
  2    from user_segments
  3   where segment_name = 'BIG';

    BLOCKS     MBYTES
---------- ----------
    163840       1280

SQL>
SQL> select val, count(*)
  2    from big
  3   group by val
  4   order by val;

       VAL   COUNT(*)
---------- ----------
         0    9900000
         1     100000
```

It has 10M rows and 163K blocks occupying ***1280MB***; there are 9.9M 0's and 100K 1's.

Now I am going to update that table and set all `VAL=1` to 2 (I will be using a new session because I am going to query some statistics as well):

```sql
SQL> select name, value
  2    from v$mystat natural join v$statname
  3   where name in ('db block gets', 'consistent gets')
  4   order by name;

NAME                                                                  VALUE
---------------------------------------------------------------- ----------
consistent gets                                                          45
db block gets                                                             3

SQL>
SQL> update big
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
consistent gets                                                      479962
db block gets                                                        107064

```

It's a slightly unusual number of consistent gets given that that table has only 163K blocks.

Let's see what the SQL Monitoring report looks like:

```sql hl_lines="31 39 40 41"
SQL> select dbms_sqltune.report_sql_monitor('7z5h5dg0pa0fv') from dual;

DBMS_SQLTUNE.REPORT_SQL_MONITOR('7Z5H5DG0PA0FV')
------------------------------------------------------------------------------------------------------------------------------------------------------
SQL Monitoring Report

SQL Text
------------------------------
update big set val = val + 1 where val = 1

Global Information
------------------------------
 Status              :  DONE
 Instance ID         :  1
 Session             :  TC (15:16913)
 SQL ID              :  7z5h5dg0pa0fv
 SQL Execution ID    :  16777224
 Execution Started   :  08/01/2019 07:53:30
 First Refresh Time  :  08/01/2019 07:53:34
 Last Refresh Time   :  08/01/2019 07:53:46
 Duration            :  16s
 Module/Action       :  SQL*Plus/-
 Service             :  pdb
 Program             :  sqlplus.exe

Global Stats
========================================================
| Elapsed |   Cpu   |    IO    | Buffer | Read | Read  |
| Time(s) | Time(s) | Waits(s) |  Gets  | Reqs | Bytes |
========================================================
|      17 |    5.80 |       11 |   587K | 6786 |   4GB |
========================================================

SQL Plan Monitoring Details (Plan Hash Value=3225303172)
======================================================================================================================================================
| Id |      Operation       | Name |  Rows   | Cost  |   Time    | Start  | Execs |   Rows   | Read | Read  | Activity |       Activity Detail       |
|    |                      |      | (Estim) |       | Active(s) | Active |       | (Actual) | Reqs | Bytes |   (%)    |         (# samples)         |
======================================================================================================================================================
|  0 | UPDATE STATEMENT     |      |         |       |        11 |     +6 |     3 |        0 |      |       |          |                             |
|  1 |   UPDATE             | BIG  |         |       |        11 |     +6 |     3 |        0 | 1502 |  12MB |    13.33 | Cpu (2)                     |
|  2 |    TABLE ACCESS FULL | BIG  |      5M | 43216 |        16 |     +1 |     3 |     205K | 5284 |   4GB |    86.67 | Cpu (3)                     |
|    |                      |      |         |       |           |        |       |          |      |       |          | db file scattered read (10) |
======================================================================================================================================================
```

So my session read ***4G*** and all plan lines started thrice. Here is the exact amount of data read:

```sql
SQL> select physical_read_bytes/power(2,20) read_mbytes
  2    from v$sql_monitor
  3   where sql_id = '7z5h5dg0pa0fv'
  4     and sql_exec_id = 16777224
  5     and sid = sys_context('userenv', 'sid');

READ_MBYTES
-----------
 3689.39063
```

Remember, that the table's size is ***1200M***, so that we read that table three times.
It can be also confirmed by looking into the raw trace file (notice the `str=3` string which means that that row-source started three times):

```
STAT #140538058031192 id=1 cnt=0 pid=0 pos=1 obj=0 op='UPDATE  BIG (cr=322910 pr=315316 pw=0 str=3 time=11011457 us)'
STAT #140538058031192 id=2 cnt=205426 pid=1 pos=1 obj=136452 op='TABLE ACCESS FULL BIG (cr=479905 pr=470740 pw=0 str=3 time=13478866 us cost=43216 size=15000000 card=5000000)'
```

If I set some diagnostic events in my session:

```sql
alter session set events 'trace[dml]:sql_trace wait=true';
```

I am able to see what is going on in the trace file:

``` hl_lines="9 12 14 15 24"
PARSING IN CURSOR #140538058031192 len=46 dep=0 uid=138 oct=6 lid=138 tim=2665107653071 hv=3243573723 ad='c7471690' sqlid='7z5h5dg0pa0fv'
update big
   set val = val + 1
 where val = 1
END OF STMT
PARSE #140538058031192:c=1704,e=1744,p=0,cr=0,cu=0,mis=1,r=0,dep=0,og=1,plh=3225303172,tim=2665107653070
updSetExecCmpColInfo: not RHS: objn=136452, cid=3
  kduukcmpf=0x7fd1968399ea, kduukcmpl=0x7fd1968399e8, kduukcmpp=(nil)
updThreePhaseExe: objn=136452 phase=NOT LOCKED
updaul: phase is NOT LOCKED snap oldsnap env: (scn: 0x8000.02774b2c  xid: 0x0000.000.00000000  uba: 0x00000000.0000.00  statement num=0  parent xid: xid: 0x0000.000.00000000  scn: 0x0000.00000000  97sch: scn: 0x0000.00000000  mascn: (scn: 0x8000.02774b0e) env: (scn: 0x0000.00000000  xid: 0x0000.000.00000000  uba: 0x00000000.0000.00  statement num=0  parent xid: xid: 0x0000.000.00000000  scn: 0x0000.00000000  512sch: scn: 0x0000.00000000  mascn: (scn: 0x0000.00000000)
...
updrowFastPath: objn=136452 error=1551
updrowFastPath: qecinvsub objn=136452
updrowFastPath: resignal error due to array update objn=136452updaul: objn=136452 error=1551
updThreePhaseExe: objn=136452 phase=LOCK
updaul: phase is LOCK snap oldsnap env: (scn: 0x8000.02774b2e  xid: 0x0008.009.00009487  uba: 0x00000000.0000.00  statement num=0  parent xid: xid: 0x0000.000.00000000  scn: 0x8000.02774b2e  97sch: scn: 0x0000.00000000  mascn: (scn: 0x8000.02774b0e) env: (scn: 0x8000.02774b2c  xid: 0x0000.000.00000000  uba: 0x00000000.0000.00  statement num=0  parent xid: xid: 0x0000.000.00000000  scn: 0x0000.00000000  608sch: scn: 0x0000.00000000  mascn: (scn: 0x8000.02774b0e)
...
updrowFastPath: kddlkr objn 136452 table 0  rowid 00021504.09874962.34 code 0
updrowFastPath: kddlkr objn 136452 table 0  rowid 00021504.09874962.35 code 0
updrowFastPath: kddlkr objn 136452 table 0  rowid 00021504.09874962.36 code 0
updrowFastPath: kddlkr objn 136452 table 0  rowid 00021504.09874962.37 code 0
--100K such lines
updrowFastPath: kddlkr objn 136452 table 0  rowid 00021504.09874faf.2c code 0
updThreePhaseExe: objn=136452 phase=ALL LOCKED
updaul: phase is ALL LOCKED snap oldsnap env: (scn: 0x8000.02774b2e  xid: 0x0008.009.00009487  uba: 0x00000000.0000.00  statement num=0  parent xid: xid: 0x0000.000.00000000  scn: 0x8000.02774b2e  96sch: scn: 0x0000.00000000  mascn: (scn: 0
x8000.02774b0e) env: (scn: 0x8000.02774b2c  xid: 0x0000.000.00000000  uba: 0x00000000.0000.00  statement num=0  parent xid: xid: 0x0000.000.00000000  scn: 0x0000.00000000  608sch: scn: 0x0000.00000000  mascn: (scn: 0x8000.02774b0e)
```

Somehow the update hit `ORA-01551` and fell back to the LOCK/UPDATE sequence (which is similar to `SELECT FOR UPDATE`/`UPDATE` in SQL).

The table was read three times:

1. the first time we read it at the ***NOT LOCKED*** stage
1. we seemed to get `ORA-01551`, and went through the ***LOCK*** stage to lock all the rows (the `kddlkr` lines)
1. once we locked all the rows, we reached the ***ALL LOCKED*** stage and started changing the column

The error appears to be internal for Oracle:

```
$oerr ora 1551
01551, 00000, "extended rollback segment, pinned blocks released"
// *Cause: Doing recursive extent of rollback segment, trapped internally
//        by the system
// *Action: None
```

It might be related to the `_inplace_update_retry` parameter that has the following description: "inplace update retry for ora1551", but I have not tested it yet.
The closest issue that I found for this error is [this old thread](https://groups.google.com/forum/#!msg/relcom.comp.dbms.oracle/HOr403spfi0/Xm-mZ2NvDMQJ) (2002) on Google Groups which was left without resolution and a detailed explanation (it's in Russian).
There is also [Bug 24827102 : PERFORMANCE OF UPDATE STATEMENT IS NOT CONSISTENT](https://support.oracle.com/rs?type=bug&id=24827102) that mentions the same error.

I cannot reproduce this issue every time and it has not happened in one session twice which makes me think that it is related to the undo segment assigned to that transaction (**update**: that could happen in one session multiple times as well, my initial observation was wrong).

## tl;dr.

DML restarts are possible even in a single-user system.
At least, that is how all modern versions of Oracle Database work (I tested 12.2 and 19c).
Thankfully, it's easy to identify them in SQL Monitoring reports or in trace files (when the `trace[DML]` or `sql_trace` events are set).
When you see some unexpected hikes in buffer gets or reads that cannot be explained by the amount of data being processed, it might as well be due to statement restarts as this post demonstrates.
