---
categories:
  - Oracle
date:
  created: 2014-08-23T23:49:00
description: Event 10505 dumps dynamic sampling statistics to user tables
tags:
  - 11g
  - Diagnostic event
  - Performance
---

# Event 10505: CBO enable dynamic sampling dump to table

Event 10505 dumps dynamic sampling statistics to user tables.

<!-- more -->

```
[oracle@oracle ~]$ oerr ora 10505
10505, 00000, "CBO enable dynamic sampling dump to table"
// *Cause:
// *Action:
```

This event requires creating additional tables `KKEDSAMP_TABLE`, `KKEDSAMP_COLUMN`, and `KKEDSAMP_INDEX`:

```sql
-- general table and dynamic sampling stats
create table kkedsamp_table(
  table_name varchar2(30),
  dyn_sampling_level number,
  c3 number, -- unknown
  c4 number, -- unknown
  c5 number, -- unknown
  c6 number, -- unknown
  c7 number, -- unknown
  single_table_dyn_sel_est number,
  dynamic_sampling_card number,
  sample_pct number,
  c11 number, -- unknown, partitioning
  c12 number, -- unknown, partitioning
  c13 number, -- unknown, partitioning
  c14 number, -- unknown
  actual_sample_size number,
  filtered_sample_card number,
  orig_card number,
  block_cnt_for_sampling_tabstat number,
  c19 number,
  max_sample_block_cnt number,
  sample_block_cnt number,
  min_sel_est number);
-- column stats
create table kkedsamp_column(
  column_name varchar2(30),
  table_name varchar2(30),
  c3 number, -- unknown
  num_distinct number,
  num_distinct_scaled number,
  num_nulls number,
  num_nulls_scaled number);
-- index stats
create table kkedsamp_index(
  index_name varchar2(30),
  table_name varchar2(30),
  c3 number, -- unknown
  index_selectity_est number,
  min_sel_est number,
  c6 number, -- unknown
  num_blocks number);
```

Test case (run on 11.2.0.3):

```sql
SQL> create table t1 as select * from dba_objects;

Table created.
SQL> create table t2 as select * from dba_objects;

Table created.
SQL> create index t1_subobject_name_i on t1(subobject_name);

Index created.
SQL> exec dbms_stats.delete_index_stats( '', 'T1_SUBOBJECT_NAME_I')

PL/SQL procedure successfully completed.
SQL> alter session set events '10505';

Session altered.
SQL> select /*+ dynamic_sampling(4)*/
  2         count(*)
  3    from t1, t2
  4   where t1.owner='SYSTEM'
  5     and t2.subobject_name=t1.subobject_name
  6     and t2.object_type like 'TABLE%';

  COUNT(*)
----------
      3425
SQL> alter session set events '10505 off';

Session altered.
SQL> @pt "select * from kkedsamp_table"
TABLE_NAME                    : "T1"
DYN_SAMPLING_LEVEL            : 4
C3                            : 1
C4                            : 1
C5                            : 1
C6                            : 1
C7                            : 1
SINGLE_TABLE_DYN_SEL_EST      : .060506329113924
DYNAMIC_SAMPLING_CARD         : 12665.0793650794
SAMPLE_PCT                    : 31.1881188118812
C11                           : 1
C12                           : 1
C13                           : 1
C14                           : 1
ACTUAL_SAMPLE_SIZE            : 3950
FILTERED_SAMPLE_CARD          : 239
ORIG_CARD                     : 16500
BLOCK_CNT_FOR_SAMPLING_TABSTAT: 202
C19                           : 0
MAX_SAMPLE_BLOCK_CNT          : 64
SAMPLE_BLOCK_CNT              : 63
MIN_SEL_EST                   : .01
-----------------
TABLE_NAME                    : "T2"
DYN_SAMPLING_LEVEL            : 4
C3                            : 1
C4                            : 1
C5                            : 1
C6                            : 1
C7                            : 0
SINGLE_TABLE_DYN_SEL_EST      : .135717785399314
DYNAMIC_SAMPLING_CARD         : 13088.3174603175
SAMPLE_PCT                    : 31.1881188118812
C11                           : 1
C12                           : 1
C13                           : 1
C14                           : 1
ACTUAL_SAMPLE_SIZE            : 4082
FILTERED_SAMPLE_CARD          : 554
ORIG_CARD                     : 16500
BLOCK_CNT_FOR_SAMPLING_TABSTAT: 202
C19                           : 0
MAX_SAMPLE_BLOCK_CNT          : 64
SAMPLE_BLOCK_CNT              : 63
MIN_SEL_EST                   : .05
-----------------

PL/SQL procedure successfully completed.
SQL> @pt "select * from kkedsamp_column"
COLUMN_NAME                   : "T1"."SUBOBJECT_NAME"
TABLE_NAME                    : "T1"
C3                            : 3
NUM_DISTINCT                  : 160
NUM_DISTINCT_SCALED           : 161
NUM_NULLS                     : 3699
NUM_NULLS_SCALED              : 11860.2857142857
-----------------
COLUMN_NAME                   : "T2"."SUBOBJECT_NAME"
TABLE_NAME                    : "T2"
C3                            : 3
NUM_DISTINCT                  : 66
NUM_DISTINCT_SCALED           : 66
NUM_NULLS                     : 3997
NUM_NULLS_SCALED              : 12815.7777777778
-----------------

PL/SQL procedure successfully completed.
SQL> @pt "select * from kkedsamp_index"
INDEX_NAME                    : T1_SUBOBJECT_NAME_I
TABLE_NAME                    : "T1"
C3                            : 0
INDEX_SELECTITY_EST           : -1
MIN_SEL_EST                   : -1
C6                            : 1
NUM_BLOCKS                    : 8
-----------------
PL/SQL procedure successfully completed.
```

Similar information can be obtained from event 10053 trace files.
