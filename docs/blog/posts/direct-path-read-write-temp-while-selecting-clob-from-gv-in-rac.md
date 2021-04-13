---
categories:
  - Oracle
date:
  created: 2021-04-13T21:29:00
description: >-
  Oracle started doing direct path read/write temp while selecting CLOB from GV$ views in RAC.
  The behavior drastically affects performance and it was introduced in 18c.
  This post demonstrates the behavior and compares performance of 18c/19c against 12.2 to demonstrate the difference.
tags:
  - 11g
  - 12c
  - 18c
  - 19c
  - Diagnostic event
  - LOB
  - Performance
  - RAC
---

# Direct Path Read Write Temp while Selecting CLOB from GV$ in RAC

I was intestigating why a simple `SELECT * FROM GV$SQL` started working much slower in 19c compared to 11.2.0.4.
It turns out Oracle introduced some changes there in 18c.
This blog post is written to demonstrate the new behavior.

<!-- more -->

## Demonstration

A simple test case which I constructed for this example is below:

```sql
set echo on
set timing on

select banner from v$version;
alter session set events 'sql_trace wait=true';
begin
  for r in (
    select sql_fulltext
      from gv$sql)
  loop
    null;
  end loop;
end;
/
alter session set events 'sql_trace off';

select value
  from v$diag_info
 where name='Default Trace File';
```

I ran it in 19.10 and got the following results:

```sql hl_lines="25"
SQL> select banner from v$version;

BANNER
--------------------------------------------------------------------------------
Oracle Database 19c Enterprise Edition Release 19.0.0.0.0 - Production

Elapsed: 00:00:00.00
SQL> alter session set events 'sql_trace wait=true';

Session altered.

Elapsed: 00:00:00.00
SQL> begin
  2    for r in (
  3      select sql_fulltext
  4        from gv$sql)
  5    loop
  6      null;
  7    end loop;
  8  end;
  9  /

PL/SQL procedure successfully completed.

Elapsed: 00:00:02.14
SQL> alter session set events 'sql_trace off';

Session altered.

Elapsed: 00:00:00.00
SQL>
SQL> select value
  2    from v$diag_info
  3   where name='Default Trace File';

VALUE
--------------------------------------------------------------------------------
/u01/app/oracle/diag/rdbms/orcl19/orcl191/trace/orcl191_ora_19616.trc

Elapsed: 00:00:00.00
```

I processed the trace file using TKPROF and got the output below:

``` hl_lines="12 43 44 45"
SQL ID: 250c8asaww0wz Plan Hash: 1891717107

SELECT SQL_FULLTEXT
FROM
 GV$SQL


call     count       cpu    elapsed       disk      query    current        rows
------- ------  -------- ---------- ---------- ---------- ----------  ----------
Parse        1      0.00       0.00          0          0          0           0
Execute      1      0.00       0.00          0          0          0           0
Fetch       21      0.44       2.13        288        288      25355        2011
------- ------  -------- ---------- ---------- ---------- ----------  ----------
total       23      0.44       2.13        288        288      25355        2011

Misses in library cache during parse: 0
Optimizer mode: ALL_ROWS
Parsing user id: SYS   (recursive depth: 1)
Number of plan statistics captured: 1

Rows (1st) Rows (avg) Rows (max)  Row Source Operation
---------- ---------- ----------  ---------------------------------------------------
      2011       2011       2011  PX COORDINATOR  (cr=288 pr=288 pw=2259 time=2499846 us starts=1)
         0          0          0   PX SEND QC (RANDOM) :TQ10000 (cr=0 pr=0 pw=0 time=0 us starts=0 cost=0 size=1638400 card=100)
         0          0          0    VIEW  GV$SQL (cr=0 pr=0 pw=0 time=0 us starts=0)
         0          0          0     FIXED TABLE FULL X$KGLCURSOR_CHILD (cr=0 pr=0 pw=0 time=0 us starts=0 cost=0 size=1638400 card=100)


Elapsed times include waiting on following events:
  Event waited on                             Times   Max. Wait  Total Waited
  ----------------------------------------   Waited  ----------  ------------
  PGA memory operation                           18        0.00          0.00
  PX Deq: reap credit                           232        0.00          0.00
  PX Deq: Join ACK                                2        0.00          0.00
  PX Deq: Parse Reply                             2        0.00          0.00
  PX Deq: Execute Reply                         146        0.00          0.00
  Disk file operations I/O                        5        0.00          0.00
  CSS initialization                              2        0.00          0.00
  CSS operation: query                            6        0.00          0.00
  CSS operation: action                           2        0.00          0.00
  asynch descriptor resize                        1        0.00          0.00
  ASM IO for non-blocking poll                 6769        0.00          0.00
  direct path write temp                       2158        0.00          1.59
  db file sequential read                       144        0.00          0.06
  direct path read temp                         144        0.00          0.06
  reliable message                                1        0.00          0.00
  PX Deq: Signal ACK EXT                          2        0.00          0.00
  IPC send completion sync                        1        0.00          0.00
  PX Deq: Slave Session Stats                     2        0.00          0.00
  IPC group service call                          1        0.00          0.00
  enq: PS - contention                            1        0.00          0.00
```

It is worth noting that the number of rows is **2011** while the number of `direct path write temp` wait events is **2158**.
I believe it is a general pattern rather than a coincidence based on my tests.
I found that the number of `direct path write temp` is always greater than the number of rows but not much.
That basically means that Oracle does at least one write per CLOB returned.

Let us now compare it with 12.2 (I tested both vanilla 12.2.0.1 and 12.2.0.1 with the latest release update):

```sql hl_lines="29"
SQL> select banner from v$version;

BANNER
--------------------------------------------------------------------------------
Oracle Database 12c Enterprise Edition Release 12.2.0.1.0 - 64bit Production
PL/SQL Release 12.2.0.1.0 - Production
CORE    12.2.0.1.0      Production
TNS for Linux: Version 12.2.0.1.0 - Production
NLSRTL Version 12.2.0.1.0 - Production

Elapsed: 00:00:00.01
SQL> alter session set events 'sql_trace wait=true';

Session altered.

Elapsed: 00:00:00.00
SQL> begin
  2    for r in (
  3      select sql_fulltext
  4        from gv$sql)
  5    loop
  6      null;
  7    end loop;
  8  end;
  9  /

PL/SQL procedure successfully completed.

Elapsed: 00:00:00.05
SQL> alter session set events 'sql_trace off';

Session altered.

Elapsed: 00:00:00.00
SQL>
SQL> select value
  2    from v$diag_info
  3   where name='Default Trace File';

VALUE
--------------------------------------------------------------------------------
/u01/app/oracle/diag/rdbms/o122a/o122a1/trace/o122a1_ora_24892.trc
```

It can be seen that 12.2 is much faster than 19.10.

Here is a TKPROF processed output:

```
SQL ID: 250c8asaww0wz Plan Hash: 1891717107

SELECT SQL_FULLTEXT
FROM
 GV$SQL


call     count       cpu    elapsed       disk      query    current        rows
------- ------  -------- ---------- ---------- ---------- ----------  ----------
Parse        1      0.00       0.00          0          0          0           0
Execute      1      0.00       0.00          0          0          0           0
Fetch       21      0.02       0.03          0          0          0        2069
------- ------  -------- ---------- ---------- ---------- ----------  ----------
total       23      0.03       0.05          0          0          0        2069

Misses in library cache during parse: 1
Optimizer mode: ALL_ROWS
Parsing user id: 76     (recursive depth: 1)
Number of plan statistics captured: 1

Rows (1st) Rows (avg) Rows (max)  Row Source Operation
---------- ---------- ----------  ---------------------------------------------------
      2069       2069       2069  PX COORDINATOR  (cr=0 pr=0 pw=0 time=138102 us starts=1)
         0          0          0   PX SEND QC (RANDOM) :TQ10000 (cr=0 pr=0 pw=0 time=0 us starts=0 cost=0 size=200200 card=100)
         0          0          0    VIEW  GV$SQL (cr=0 pr=0 pw=0 time=0 us starts=0)
         0          0          0     FIXED TABLE FULL X$KGLCURSOR_CHILD (cr=0 pr=0 pw=0 time=0 us starts=0 cost=0 size=200200 card=100)


Elapsed times include waiting on following events:
  Event waited on                             Times   Max. Wait  Total Waited
  ----------------------------------------   Waited  ----------  ------------
  enq: PS - contention                            3        0.00          0.00
  PX Deq: Join ACK                                5        0.00          0.00
  PX Deq: reap credit                           277        0.00          0.00
  IPC send completion sync                        3        0.00          0.00
  PX Deq: Parse Reply                             2        0.00          0.00
  PGA memory operation                           28        0.00          0.00
  PX Deq: Execute Reply                         132        0.00          0.01
  reliable message                                1        0.00          0.00
  PX Deq: Signal ACK EXT                          2        0.00          0.00
  PX Deq: Slave Session Stats                     2        0.00          0.00
```


Although the number of rows is roughly the same (**2069** in 12.2 vs **2011** in 19.10), the runtime performance and wait events are drastically different.
Please bear in mind, that I initially asked to investigate why the same query in 11.2 was running in **1** second while the same query in 19.10 was running in **90** seconds with about the same number of rows as in 11.2.

I also reviewed the trace file in 19c to see if I can spot any pattern there:

```
[oracle@rac1 ~]$ grep 'WAIT #139925193433952' /u01/app/oracle/diag/rdbms/orcl19/orcl191/trace/orcl191_ora_19616.trc | grep -E 'direct path (read|write) temp|db file sequential read'
WAIT #139925193433952: nam='direct path write temp' ela= 758 file number=201 first dba=4355 block cnt=1 obj#=-1 tim=20569064799
WAIT #139925193433952: nam='direct path write temp' ela= 674 file number=201 first dba=4356 block cnt=1 obj#=-1 tim=20569065748
..59 direct path write temp in total
WAIT #139925193433952: nam='direct path write temp' ela= 680 file number=201 first dba=4413 block cnt=1 obj#=-1 tim=20569114649
..then there are groups consisting of one db file sequential read/one direct path read temp (the same block)/multiple direct path write temp:
..group 1
WAIT #139925193433952: nam='db file sequential read' ela= 473 file#=201 block#=4413 blocks=1 obj#=-1 tim=20569115200
WAIT #139925193433952: nam='direct path read temp' ela= 449 file number=201 first dba=4413 block cnt=1 obj#=-1 tim=20569115739
WAIT #139925193433952: nam='direct path write temp' ela= 699 file number=201 first dba=4413 block cnt=1 obj#=-1 tim=20569116529
WAIT #139925193433952: nam='direct path write temp' ela= 643 file number=201 first dba=4414 block cnt=1 obj#=-1 tim=20569117342
WAIT #139925193433952: nam='direct path write temp' ela= 753 file number=201 first dba=4415 block cnt=1 obj#=-1 tim=20569118266
WAIT #139925193433952: nam='direct path write temp' ela= 706 file number=201 first dba=4416 block cnt=1 obj#=-1 tim=20569119134
WAIT #139925193433952: nam='direct path write temp' ela= 593 file number=201 first dba=4417 block cnt=1 obj#=-1 tim=20569119882
WAIT #139925193433952: nam='direct path write temp' ela= 626 file number=201 first dba=4418 block cnt=1 obj#=-1 tim=20569120652
WAIT #139925193433952: nam='direct path write temp' ela= 807 file number=201 first dba=4419 block cnt=1 obj#=-1 tim=20569121585
WAIT #139925193433952: nam='direct path write temp' ela= 625 file number=201 first dba=4420 block cnt=1 obj#=-1 tim=20569122348
WAIT #139925193433952: nam='direct path write temp' ela= 605 file number=201 first dba=4421 block cnt=1 obj#=-1 tim=20569123097
WAIT #139925193433952: nam='direct path write temp' ela= 509 file number=201 first dba=4422 block cnt=1 obj#=-1 tim=20569123753
WAIT #139925193433952: nam='direct path write temp' ela= 577 file number=201 first dba=4423 block cnt=1 obj#=-1 tim=20569124476
WAIT #139925193433952: nam='direct path write temp' ela= 667 file number=201 first dba=4424 block cnt=1 obj#=-1 tim=20569125286
WAIT #139925193433952: nam='direct path write temp' ela= 501 file number=201 first dba=4425 block cnt=1 obj#=-1 tim=20569125930
WAIT #139925193433952: nam='direct path write temp' ela= 617 file number=201 first dba=4426 block cnt=1 obj#=-1 tim=20569126698
WAIT #139925193433952: nam='direct path write temp' ela= 634 file number=201 first dba=4427 block cnt=1 obj#=-1 tim=20569127473
WAIT #139925193433952: nam='direct path write temp' ela= 577 file number=201 first dba=4428 block cnt=1 obj#=-1 tim=20569128188
WAIT #139925193433952: nam='direct path write temp' ela= 868 file number=201 first dba=4429 block cnt=1 obj#=-1 tim=20569129188
WAIT #139925193433952: nam='direct path write temp' ela= 609 file number=201 first dba=4430 block cnt=1 obj#=-1 tim=20569130099
..group 2
WAIT #139925193433952: nam='db file sequential read' ela= 399 file#=201 block#=4430 blocks=1 obj#=-1 tim=20569130544
WAIT #139925193433952: nam='direct path read temp' ela= 454 file number=201 first dba=4430 block cnt=1 obj#=-1 tim=20569131072
WAIT #139925193433952: nam='direct path write temp' ela= 669 file number=201 first dba=4430 block cnt=1 obj#=-1 tim=20569131834
WAIT #139925193433952: nam='direct path write temp' ela= 686 file number=201 first dba=4431 block cnt=1 obj#=-1 tim=20569132665
WAIT #139925193433952: nam='direct path write temp' ela= 588 file number=201 first dba=4432 block cnt=1 obj#=-1 tim=20569133416
WAIT #139925193433952: nam='direct path write temp' ela= 794 file number=201 first dba=4433 block cnt=1 obj#=-1 tim=20569134366
WAIT #139925193433952: nam='direct path write temp' ela= 648 file number=201 first dba=4434 block cnt=1 obj#=-1 tim=20569135192
WAIT #139925193433952: nam='direct path write temp' ela= 792 file number=201 first dba=4435 block cnt=1 obj#=-1 tim=20569136134
WAIT #139925193433952: nam='direct path write temp' ela= 682 file number=201 first dba=4436 block cnt=1 obj#=-1 tim=20569136961
WAIT #139925193433952: nam='direct path write temp' ela= 609 file number=201 first dba=4437 block cnt=1 obj#=-1 tim=20569137753
WAIT #139925193433952: nam='direct path write temp' ela= 563 file number=201 first dba=4438 block cnt=1 obj#=-1 tim=20569138501
WAIT #139925193433952: nam='direct path write temp' ela= 645 file number=201 first dba=4439 block cnt=1 obj#=-1 tim=20569139298
WAIT #139925193433952: nam='direct path write temp' ela= 807 file number=201 first dba=4440 block cnt=1 obj#=-1 tim=20569140265
WAIT #139925193433952: nam='direct path write temp' ela= 679 file number=201 first dba=4441 block cnt=1 obj#=-1 tim=20569141079
WAIT #139925193433952: nam='direct path write temp' ela= 626 file number=201 first dba=4442 block cnt=1 obj#=-1 tim=20569141844
WAIT #139925193433952: nam='direct path write temp' ela= 740 file number=201 first dba=4443 block cnt=1 obj#=-1 tim=20569142718
WAIT #139925193433952: nam='direct path write temp' ela= 753 file number=201 first dba=4444 block cnt=1 obj#=-1 tim=20569143615
WAIT #139925193433952: nam='direct path write temp' ela= 686 file number=201 first dba=4445 block cnt=1 obj#=-1 tim=20569144450
WAIT #139925193433952: nam='direct path write temp' ela= 673 file number=201 first dba=4446 block cnt=1 obj#=-1 tim=20569145257
WAIT #139925193433952: nam='direct path write temp' ela= 728 file number=201 first dba=4447 block cnt=1 obj#=-1 tim=20569146129
WAIT #139925193433952: nam='direct path write temp' ela= 589 file number=201 first dba=4448 block cnt=1 obj#=-1 tim=20569146857
WAIT #139925193433952: nam='direct path write temp' ela= 658 file number=201 first dba=4449 block cnt=1 obj#=-1 tim=20569147672
WAIT #139925193433952: nam='direct path write temp' ela= 666 file number=201 first dba=4450 block cnt=1 obj#=-1 tim=20569148478
WAIT #139925193433952: nam='direct path write temp' ela= 602 file number=201 first dba=4451 block cnt=1 obj#=-1 tim=20569149255
WAIT #139925193433952: nam='direct path write temp' ela= 841 file number=201 first dba=4452 block cnt=1 obj#=-1 tim=20569150247
WAIT #139925193433952: nam='direct path write temp' ela= 763 file number=201 first dba=4453 block cnt=1 obj#=-1 tim=20569151167
WAIT #139925193433952: nam='direct path write temp' ela= 779 file number=201 first dba=4454 block cnt=1 obj#=-1 tim=20569152208
..group 3
WAIT #139925193433952: nam='db file sequential read' ela= 206 file#=201 block#=4454 blocks=1 obj#=-1 tim=20569152457
WAIT #139925193433952: nam='direct path read temp' ela= 711 file number=201 first dba=4454 block cnt=1 obj#=-1 tim=20569153234
WAIT #139925193433952: nam='direct path write temp' ela= 575 file number=201 first dba=4454 block cnt=1 obj#=-1 tim=20569153905
WAIT #139925193433952: nam='direct path write temp' ela= 930 file number=201 first dba=4455 block cnt=1 obj#=-1 tim=20569155093
WAIT #139925193433952: nam='direct path write temp' ela= 809 file number=201 first dba=4355 block cnt=1 obj#=-1 tim=20569156069
WAIT #139925193433952: nam='direct path write temp' ela= 820 file number=201 first dba=4356 block cnt=1 obj#=-1 tim=20569157024
WAIT #139925193433952: nam='direct path write temp' ela= 976 file number=201 first dba=4357 block cnt=1 obj#=-1 tim=20569158174
WAIT #139925193433952: nam='direct path write temp' ela= 683 file number=201 first dba=4358 block cnt=1 obj#=-1 tim=20569159165
WAIT #139925193433952: nam='db file sequential read' ela= 638 file#=201 block#=4358 blocks=1 obj#=-1 tim=20569159850
WAIT #139925193433952: nam='direct path read temp' ela= 183 file number=201 first dba=4358 block cnt=1 obj#=-1 tim=20569160107
..
```

My next thought was to test how 19c processes `CLOB`s in traditional tables - I have not found any issues there.
There have been no `direct path read/write temp` on copies of `GV$SQL`.
I then tried to select the same persistent tables (non-GV$) via a database link in 19c - again everything worked as it should.
It seems that only GV$ views are affected.
Local selects are not affected at all (the output below is from the first instance):

```
SQL ID: 87myh1vhjdcf8 Plan Hash: 1891717107

SELECT SQL_FULLTEXT
FROM
 GV$SQL WHERE INST_ID = 1


call     count       cpu    elapsed       disk      query    current        rows
------- ------  -------- ---------- ---------- ---------- ----------  ----------
Parse        1      0.00       0.00          0          0          0           0
Execute      1      0.00       0.00          0          0          0           0
Fetch       13      0.02       0.02          0          0          0        1231
------- ------  -------- ---------- ---------- ---------- ----------  ----------
total       15      0.03       0.03          0          0          0        1231

Misses in library cache during parse: 1
Optimizer mode: ALL_ROWS
Parsing user id: SYS   (recursive depth: 1)
Number of plan statistics captured: 1

Rows (1st) Rows (avg) Rows (max)  Row Source Operation
---------- ---------- ----------  ---------------------------------------------------
      1231       1231       1231  PX COORDINATOR  (cr=0 pr=0 pw=0 time=13516 us starts=1)
      1231       1231       1231   PX SEND QC (RANDOM) :TQ10000 (cr=0 pr=0 pw=0 time=13283 us starts=1 cost=0 size=1639700 card=100)
      1231       1231       1231    VIEW  GV$SQL (cr=0 pr=0 pw=0 time=12908 us starts=1)
      1231       1231       1231     FIXED TABLE FULL X$KGLCURSOR_CHILD (cr=0 pr=0 pw=0 time=12657 us starts=1 cost=0 size=1639700 card=100)


Elapsed times include waiting on following events:
  Event waited on                             Times   Max. Wait  Total Waited
  ----------------------------------------   Waited  ----------  ------------
  PGA memory operation                           99        0.00          0.00
```

Whereas any select when non-local instance is involved is done utilizing a temporary tablespace:

``` hl_lines="12 43 44 45"
SQL ID: 4p7vm0hhw6u1v Plan Hash: 1891717107

SELECT SQL_FULLTEXT
FROM
 GV$SQL WHERE INST_ID = 2


call     count       cpu    elapsed       disk      query    current        rows
------- ------  -------- ---------- ---------- ---------- ----------  ----------
Parse        1      0.00       0.00          0          0          0           0
Execute      1      0.00       0.00          0          0          0           0
Fetch       10      0.21       1.06        118        118      11953         968
------- ------  -------- ---------- ---------- ---------- ----------  ----------
total       12      0.21       1.07        118        118      11953         968

Misses in library cache during parse: 1
Optimizer mode: ALL_ROWS
Parsing user id: SYS   (recursive depth: 1)
Number of plan statistics captured: 1

Rows (1st) Rows (avg) Rows (max)  Row Source Operation
---------- ---------- ----------  ---------------------------------------------------
       968        968        968  PX COORDINATOR  (cr=118 pr=118 pw=1075 time=907430 us starts=1)
         0          0          0   PX SEND QC (RANDOM) :TQ10000 (cr=0 pr=0 pw=0 time=0 us starts=0 cost=0 size=1639700 card=100)
         0          0          0    VIEW  GV$SQL (cr=0 pr=0 pw=0 time=0 us starts=0)
         0          0          0     FIXED TABLE FULL X$KGLCURSOR_CHILD (cr=0 pr=0 pw=0 time=0 us starts=0 cost=0 size=1639700 card=100)


Elapsed times include waiting on following events:
  Event waited on                             Times   Max. Wait  Total Waited
  ----------------------------------------   Waited  ----------  ------------
  PX Deq: reap credit                           158        0.00          0.00
  PX Deq: Join ACK                                1        0.00          0.00
  PX Deq: Parse Reply                             1        0.00          0.00
  PGA memory operation                           11        0.00          0.00
  PX Deq: Execute Reply                          61        0.00          0.01
  Disk file operations I/O                        3        0.00          0.00
  CSS initialization                              2        0.00          0.00
  CSS operation: query                            6        0.00          0.00
  CSS operation: action                           2        0.00          0.00
  asynch descriptor resize                        1        0.00          0.00
  ASM IO for non-blocking poll                 3208        0.00          0.00
  direct path write temp                       1029        0.00          0.81
  db file sequential read                        59        0.00          0.02
  direct path read temp                          59        0.00          0.02
  reliable message                                1        0.00          0.00
  PX Deq: Signal ACK EXT                          1        0.00          0.00
  IPC send completion sync                        1        0.00          0.00
  PX Deq: Slave Session Stats                     1        0.00          0.00
  IPC group service call                          1        0.00          0.00
  enq: PS - contention                            1        0.00          0.00
```


I then shut one instance down, and rechecked the queries against GV$ - there were no `direct path read/write temp` wait events.

## Conclusion

It is still not clear why Oracle started writing every `CLOB` from GV$ to a temporary tablespace.
I tried several different GV$ views and the same behaviour was observed everywhere.
It looks like something was changed inside those GV$ functions.

My initial thought was that it is some kind of a temporary tablespace flush for persistence in case some parallel processes got terminated.
However, parallel slaves started on remote instances are sending the blocks to the QC bypassing any temp.

Then I was thinking that it might be done to reduce memory usage.
It has little sense to write every `CLOB` to temp anyway.
Why do not keep a small memory area and write to temp everything that exceeded some threshold?

I also do not know how to alter this behavior to make the things the same as they were before 18c.
I tested 11.2.0.4, 12.2 (vanilla and with the latest RU), 18c, 19c (vanilla and with the latest RU - 19.10).
Both 18c and 19c are affected, so that they wait for `direct path read/write temp` when a `CLOB` column is selected from GV$ with more than one instance.

I will update the blog post if I get to the bottom of it and identify the root cause.
