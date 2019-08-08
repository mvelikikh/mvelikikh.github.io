---
categories:
  - Oracle
date:
  created: 2019-08-09T00:49:00
description: >-
  There is an example when a DML statement executes faster with triggers than without them due to different code paths around DML restarts.
tags:
  - Code symbol
  - Diagnostic event
  - OERR
  - Performance
---

# That Old Restart Problem Strikes Back: Triggers to the Rescue

Database triggers are notoriously known for slowing down DML operations.
Yet, they lead to a remarkable consequence while applying to the first post of this series in which I demonstrated statement restarts within a single user session updating a non-partitioned table.

<!-- more -->

The previous articles in this series:

1. [That Old Restart Problem Strikes Back: Setting the Stage](that-old-restart-problem-strikes-back-setting-the-stage.md)
1. [That Old Restart Problem Strikes Back: Getting What You Pay for](that-old-restart-problem-strikes-back-getting-what-you-pay-for.md)

## Demonstration

Let us create a non-partitioned table using the script from [the first part](that-old-restart-problem-strikes-back-setting-the-stage.md) of this series:

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
    164352       1284

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

This time, though, I am adding a new after update row-level trigger:

```sql
SQL> create trigger big_au_trg
  2  after update
  3  on big
  4  for each row
  5  declare
  6  begin
  7    null;
  8  end;
  9  /

Trigger created.
```

Then I am updating the table and am going to measure consistent and current buffer gets statistics:

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
consistent gets                                                      158587
db block gets                                                        103337
```

We got ***158K*** consistent gets and ***103K*** current gets for our ***164K*** block table - that is a decent amount of buffer gets in this scenario.
The SQL Monitoring Report shows that we executed the rowsource functions only once and read ***1GB*** of data:

```sql hl_lines="31 39 40 41"
SQL> select dbms_sqltune.report_sql_monitor('7z5h5dg0pa0fv') from dual;

DBMS_SQLTUNE.REPORT_SQL_MONITOR('7Z5H5DG0PA0FV')
---------------------------------------------------------------------------------------------------------------------------------------------------
SQL Monitoring Report

SQL Text
------------------------------
update big set val = val + 1 where val = 1

Global Information
------------------------------
 Status              :  DONE
 Instance ID         :  1
 Session             :  TC (48:40781)
 SQL ID              :  7z5h5dg0pa0fv
 SQL Execution ID    :  16777226
 Execution Started   :  08/01/2019 12:02:01
 First Refresh Time  :  08/01/2019 12:02:05
 Last Refresh Time   :  08/01/2019 12:02:12
 Duration            :  11s
 Module/Action       :  SQL*Plus/-
 Service             :  pdb
 Program             :  sqlplus.exe

Global Stats
================================================================================
| Elapsed |   Cpu   |    IO    | Concurrency | PL/SQL  | Buffer | Read | Read  |
| Time(s) | Time(s) | Waits(s) |  Waits(s)   | Time(s) |  Gets  | Reqs | Bytes |
================================================================================
|      11 |    4.58 |     6.30 |        0.00 |    0.08 |   262K | 2931 |   1GB |
================================================================================

SQL Plan Monitoring Details (Plan Hash Value=3225303172)
=====================================================================================================================================================
| Id |      Operation       | Name |  Rows   | Cost  |   Time    | Start  | Execs |   Rows   | Read | Read  | Activity |      Activity Detail       |
|    |                      |      | (Estim) |       | Active(s) | Active |       | (Actual) | Reqs | Bytes |   (%)    |        (# samples)         |
=====================================================================================================================================================
|  0 | UPDATE STATEMENT     |      |         |       |         4 |     +8 |     1 |        0 |      |       |          |                            |
|  1 |   UPDATE             | BIG  |         |       |         5 |     +8 |     1 |        0 | 1112 |   9MB |    22.22 | Cpu (2)                    |
|  2 |    TABLE ACCESS FULL | BIG  |      5M | 43217 |        11 |     +1 |     1 |     100K | 1818 |   1GB |    77.78 | db file scattered read (7) |
=====================================================================================================================================================
```

Notice also that it took us only 11 seconds to execute that update statement whereas it was around 16 seconds without any triggers - your mileage can vary.

I would not jump to conclusions keeping in mind that there still might be statement restarts even when the rowsource functions were executed only once (it was demonstrated in [the second article](that-old-restart-problem-strikes-back-getting-what-you-pay-for.md) of this series), so that I provide the relevant output from the trace file instead:

```sql hl_lines="22 24"
PARSING IN CURSOR #140092319088552 len=46 dep=0 uid=138 oct=6 lid=138 tim=2680019864414 hv=3243573723 ad='c7471690' sqlid='7z5h5dg0pa0fv'
update big
   set val = val + 1
 where val = 1
END OF STMT
PARSE #140092319088552:c=130,e=131,p=0,cr=0,cu=0,mis=0,r=0,dep=0,og=1,plh=3225303172,tim=2680019864414
updSetExecCmpColInfo: not RHS: objn=136467, cid=3
  kduukcmpf=0x7f69ce5d99ea, kduukcmpl=0x7f69ce5d99e8, kduukcmpp=(nil)
updThreePhaseExe: objn=136467 phase=NOT LOCKED
updaul: phase is NOT LOCKED snap oldsnap env: (scn: 0x8000.0277b741  xid: 0x0000.000.00000000  uba: 0x00000000.0000.00  statement num=0  parent xid: xid: 0x0000.000.00000000  scn: 0x0000.00000000  97sch: scn: 0x0000.00000000  mascn: (scn: 0
x8000.0277b72c) env: (scn: 0x0000.00000000  xid: 0x0000.000.00000000  uba: 0x00000000.0000.00  statement num=0  parent xid: xid: 0x0000.000.00000000  scn: 0x0000.00000000  512sch: scn: 0x0000.00000000  mascn: (scn: 0x0000.00000000)
..
updrow: objn=136467 phase=NOT LOCKED
updrow: kauupd objn:136467 table:0 rowMigrated:FALSE  rowid 00021513.098a6964.34 code 0
updrow: objn=136467 phase=NOT LOCKED
updrow: kauupd objn:136467 table:0 rowMigrated:FALSE  rowid 00021513.098a6964.35 code 0
updrow: objn=136467 phase=NOT LOCKED
updrow: kauupd objn:136467 table:0 rowMigrated:FALSE  rowid 00021513.098a6964.36 code 0
.. there are many updrow calls
.. there are several ROW_RETRY as well
WAIT #140092319088552: nam='undo segment extension' ela= 15 segment#=6 p2=0 p3=0 obj#=0 tim=2680026841072
updrow: objn=136467 error=1551
updrow: qecinvsub objn=136467
updrow: setting ROW_RETRY objn=136467
updrow: retry_this_row: ROW_RETRY set, objn= 136467 phase=NOT LOCKED
WAIT #140092319088552: nam='undo segment extension' ela= 10848 segment#=6 p2=0 p3=0 obj#=0 tim=2680026852020
updrow: objn=136467 error=1551
updrow: qecinvsub objn=136467
updrow: setting ROW_RETRY objn=136467
updrow: retry_this_row: ROW_RETRY set, objn= 136467 phase=NOT LOCKED
updrow: kauupd objn:136467 table:0 rowMigrated:FALSE  rowid 00021513.098a698b.23 code 0
updrow: objn=136467 phase=NOT LOCKED
updrow: kauupd objn:136467 table:0 rowMigrated:FALSE  rowid 00021513.098a698b.24 code 0
..
updrow: objn=136467 phase=NOT LOCKED
updrow: kauupd objn:136467 table:0 rowMigrated:FALSE  rowid 00021513.098a6fb1.2c code 0
EXEC #140092319088552:c=4580202,e=10824372,p=158086,cr=158543,cu=103457,mis=0,r=100000,dep=0,og=1,plh=3225303172,tim=2680030688827
STAT #140092319088552 id=1 cnt=0 pid=0 pos=1 obj=0 op='UPDATE  BIG (cr=158543 pr=158086 pw=0 str=1 time=10824071 us)'
STAT #140092319088552 id=2 cnt=100000 pid=1 pos=1 obj=136467 op='TABLE ACCESS FULL BIG (cr=158531 pr=156973 pw=0 str=1 time=6924111 us cost=43217 size=15000000 card=5000000)'
```

There are no `updrowFastPath` lines and that output which looks suspiciously similar to the corresponding output with a partitioned table from [the second part](that-old-restart-problem-strikes-back-getting-what-you-pay-for.md) of this series.
That statement does not use the ***fast-path*** code path anymore and follows the usual ***non-fast*** code path that appears to be due to the presence of a trigger.

The `ORA-01551` error can also explain the issue described in [this link](https://plsql-challenge.blogspot.com/2011/02/dml-restarts-only-happen-with.html) when after a certain number of executions the statement restart is observed.
In fact, I ran the sample code provided by (Valentin?) Nikotin on [the SQL.RU forum](https://www.sql.ru/forum/833618/undo-management-statement-restart?mid=10331463#10331463) and I got the same ***ROW\_RETRY*** messages in the trace file when there was a mismatch between the number of times the trigger was fired and the number of rows being updated.

## tl;dr

When triggers are present the `updrowFastPath` function appears to be not used anymore and the execution goes through the `updrow` code path (the same one is used for partitioned tables).
In this specific example, the statement executes faster and generates far less load - it does not read the table three times after all, so that the `UPDATE` statement is actually ***faster with*** a trigger then ***without*** it.
Therefore, a suggestion to optimize a DML statement by creating a new trigger (a statement level trigger works as well) - does not sound so wacky anymore (of course, I am making use of the Oracle deficiency here).
