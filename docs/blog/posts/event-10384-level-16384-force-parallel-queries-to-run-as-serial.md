---
categories:
  - Oracle
date:
  created: 2014-08-03T21:13:00
description: Event 10384 level 16384 forces parallel queries to run in serial mode
tags:
  - 11g
  - Diagnostic event
  - PX
---

# Event 10384 level 16384: force parallel queries to run as serial

Sometimes it is useful to run parallel queries in serial mode.
Event 10384 level 16384 is one of the ways to do this.

<!-- more -->

```
[oracle@oracle]$ oerr ora 10384
10384, 00000, "parallel dataflow scheduler tracing"
// *Cause:
// *Action:   set this event only under the supervision of Oracle development
// *Comment:  trace level is a bitfield (see kkrp.h)
```

Test case (run on 11.2.0.3):

```sql
doc
  create test data
#
create table t as select * from dba_objects;

doc
  set statistics_level=all and run parallel query
#

alter session set statistics_level=all;
select /*+ parallel(t)*/count(*) from t;
select * from table(dbms_xplan.display_cursor( format=> 'allstats all'));

doc
  purge cursor
#

col address    new_v address
col hash_value new_v hash_value
select address, hash_value from v$sql where sql_id='apmsk02t1z90x';
exec sys.dbms_shared_pool.purge( '&address.,&hash_value.', 'c')

doc
  set event 10384 level 16384, _px_trace=all and run query
#

alter session set events '10384 level 16384';
alter session set "_px_trace"=all;

select /*+ parallel(t)*/count(*) from t;
select * from table(dbms_xplan.display_cursor( format=> 'allstats all'));
alter session set events '10384 off';
```

Row source execution statistics of the first execution.
Default degree 16, starts for line 5 is 16.

```sql hl_lines="9"
-----------------------------------------------------------------------------------------------------------------------------------------------------------
| Id  | Operation              | Name     | Starts | E-Rows | Cost (%CPU)| E-Time   |    TQ  |IN-OUT| PQ Distrib | A-Rows |   A-Time   | Buffers | Reads  |
-----------------------------------------------------------------------------------------------------------------------------------------------------------
|   0 | SELECT STATEMENT       |          |      1 |        |     4 (100)|          |        |      |            |      1 |00:00:00.59 |       5 |      0 |
|   1 |  SORT AGGREGATE        |          |      1 |      1 |            |          |        |      |            |      1 |00:00:00.59 |       5 |      0 |
|   2 |   PX COORDINATOR       |          |      1 |        |            |          |        |      |            |     16 |00:00:00.59 |       5 |      0 |
|   3 |    PX SEND QC (RANDOM) | :TQ10000 |      0 |      1 |            |          |  Q1,00 | P->S | QC (RAND)  |      0 |00:00:00.01 |       0 |      0 |
|   4 |     SORT AGGREGATE     |          |     16 |      1 |            |          |  Q1,00 | PCWP |            |     16 |00:00:01.16 |     567 |    189 |
|   5 |      PX BLOCK ITERATOR |          |     16 |  12736 |     4   (0)| 00:00:01 |  Q1,00 | PCWC |            |  14275 |00:00:01.16 |     567 |    189 |
|*  6 |       TABLE ACCESS FULL| T        |    189 |  12736 |     4   (0)| 00:00:01 |  Q1,00 | PCWP |            |  14275 |00:00:01.14 |     567 |    189 |
-----------------------------------------------------------------------------------------------------------------------------------------------------------
```

Row source execution statistics of the second execution.
Starts for line 5 is 1.
The parallel plan was executed serially.

```sql hl_lines="9"
-----------------------------------------------------------------------------------------------------------------------------------------------------------
| Id  | Operation              | Name     | Starts | E-Rows | Cost (%CPU)| E-Time   |    TQ  |IN-OUT| PQ Distrib | A-Rows |   A-Time   | Buffers | Reads  |
-----------------------------------------------------------------------------------------------------------------------------------------------------------
|   0 | SELECT STATEMENT       |          |      1 |        |     4 (100)|          |        |      |            |      1 |00:00:00.02 |     194 |     63 |
|   1 |  SORT AGGREGATE        |          |      1 |      1 |            |          |        |      |            |      1 |00:00:00.02 |     194 |     63 |
|   2 |   PX COORDINATOR       |          |      1 |        |            |          |        |      |            |      1 |00:00:00.02 |     194 |     63 |
|   3 |    PX SEND QC (RANDOM) | :TQ10000 |      1 |      1 |            |          |  Q1,00 | P->S | QC (RAND)  |      1 |00:00:00.02 |     194 |     63 |
|   4 |     SORT AGGREGATE     |          |      1 |      1 |            |          |  Q1,00 | PCWP |            |      1 |00:00:00.02 |     194 |     63 |
|   5 |      PX BLOCK ITERATOR |          |      1 |  12736 |     4   (0)| 00:00:01 |  Q1,00 | PCWC |            |  14275 |00:00:00.02 |     194 |     63 |
|*  6 |       TABLE ACCESS FULL| T        |      1 |  12736 |     4   (0)| 00:00:01 |  Q1,00 | PCWP |            |  14275 |00:00:00.02 |     194 |     63 |
-----------------------------------------------------------------------------------------------------------------------------------------------------------
```

The trace file with event 10384 set contains the following line:

```
Parallelism disabled at runtime because forced serial by event 10384
```

The level of the event is documented in [How to Force that a Parallel Query Runs in Serial with the Parallel Execution Plan (Doc ID 1114405.1)](https://support.oracle.com/rs?type=doc&id=1114405.1)
