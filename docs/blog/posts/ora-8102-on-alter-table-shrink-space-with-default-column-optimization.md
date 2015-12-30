---
categories:
  - Oracle
date:
  created: 2015-12-30T13:42:00
description: >-
  Running ALTER TABLE SHRINK may result in ORA-8102 error if the table has columns added using DEFAULT NOT NULL column optimization, which is a metadata-only operation.
  Setting _add_col_optim_enabled to FALSE before modifying a table can prevent the issue.
  If the issue is already encountered, then the table can be rebuilt using ALTER TABLE MOVE or DBMS_REDEFINITION, or the column can be updated to itself to avoid ORA-8102 in the future.
tags:
  - 11g
  - 12c
  - Bug
  - Initialization parameter
  - OERR
---

# `ORA-8102` on `ALTER TABLE SHRINK SPACE` with default column optimization

Encountered `ORA-8102` while executing a regular database maintenance routine.
This post analyzes the problem, builds a test case to reproduce it, and shows how the problem can be avoided.

<!-- more -->

I have been using a centralized AWR repository since 2013.
For that, I developed some PL/SQL procedures that use the original AWR Extract/AWR Load (`awrextr.sql`/`awrload.sql`) scripts as a template.
That solution has some drawbacks, for example, the AWR retention for foreign databases is always set to 40150 years after each load:

```sql hl_lines="6 7"
SQL> select dbid, retention from dba_hist_wr_control;

      DBID RETENTION
---------- --------------------
1110059808 +00366 00:00:00.0
1917063347 +40150 00:00:00.0
1996649024 +40150 00:00:00.0
```

Although the retention could be changed, it would always be reset on the next AWR load causing AWR data growth.
To delete the old AWR rows, I executed the [DBMS\_WORKLOAD\_REPOSITORY.DROP\_SNAPSHOT\_RANGE](https://docs.oracle.com/database/121/ARPLS/d_workload_repos.htm#ARPLS69138) procedure once a year.
2015 was no exception.

I also ran the `ALTER TABLE SHRINK SPACE` command after executing `DBMS_WORKLOAD_REPOSITORY.DROP_SNAPSHOT_RANGE`.
Usually that command takes a while to execute since some of AWR tables are more than 50G in size, for example, `WRH$_ACTIVE_SESSION_HISTORY`.
It is a base table for the `DBA_HIST_ACTIVE_SESS_HISTORY` view and contains historic active session history records.
There is quite a lot of rows and the table is huge.

This year things suddenly went wrong:

```sql hl_lines="2"
SQL> alter table SYS.WRH$_ACTIVE_SESSION_HISTORY shrink space;
-- AFTER 4-8 hours
*
ERROR at line 1:
ORA-03113: end-of-file on communication channel
Process ID: 635
Session ID: 281 Serial number: 54363
```

The alert log was not very helpful:

```
Mon Dec 21 14:37:31 2015
Process 0x3cd728e40 appears to be hung while dumping
Current time = 1689592362, process death time = 1689530965 interval = 60000
Called from location UNKNOWN:UNKNOWN
Attempting to kill process 0x3cd728e40 with OS pid = 17740
OSD kill succeeded for process 3cd728e40
Mon Dec 21 14:39:46 2015
Errors in file /oracle/diag/rdbms/orcl/orcl/trace/orcl_ora_25447.trc:
```

But the relevant trace file, which was more than 4G in size, spotted a light on the problem:

``` hl_lines="3"
*** ACTION NAME:() 2015-12-21 14:39:46.890

oer 8102.2 - obj# 1021709, rdba: 0x086ad43c(afn 33, blk# 2806844)
kdk key 8102.2:
  ncol: 6, len: 26
  key: (26):
 06 c5 0c 0b 06 63 09 04 c3 08 0e 3e 02 c1 02 05 c4 62 46 05 3b 03 c2 02 3d
 ff
  mask: (4096):
 81 90 20 02 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
```

Well, the string `oer 8102.2` is a sign of the notorious `ORA-8102` error:

```
[oracle@localhost ~]$ oerr ora 8102
08102, 00000, "index key not found, obj# %s, file %s, block %s (%s)"
// *Cause:  Internal error: possible inconsistency in index
// *Action:  Send trace file to your customer support representative, along
//      with information on reproducing the error
```

`obj# 1021709` in the trace file shows us where the problem is:

```sql
SQL> select xmltype(cursor(select * from dba_objects where object_id=1021709)) xml_rec from dual;

XML_REC
----------------------------------------------------------------------------------------------------------

<ROWSET>
  <ROW>
    <OWNER>SYS
    <OBJECT_NAME>WRH$_ACTIVE_SESSION_HISTORY_PK
    <SUBOBJECT_NAME>WRH$_ACTIVE_1110059808_66853
    <OBJECT_ID>1021709
    <DATA_OBJECT_ID>1080082
    <OBJECT_TYPE>INDEX PARTITION
    <CREATED>27.10.2015 01:28:05
    <LAST_DDL_TIME>22.12.2015 09:11:22
    <TIMESTAMP>2015-10-27:01:28:05
    <STATUS>VALID
    <TEMPORARY>N
    <GENERATED>N
    <SECONDARY>N
    <NAMESPACE>4
    <SHARING>NONE
    <ORACLE_MAINTAINED>Y
  </ROW>
</ROWSET>
```

The index `WRH$_ACTIVE_SESSION_HISTORY_PK` is local partitioned on the following columns:

```sql
CREATE UNIQUE INDEX "SYS"."WRH$_ACTIVE_SESSION_HISTORY_PK" ON "SYS"."WRH$_ACTIVE_SESSION_HISTORY" ("DBID", "SNAP_ID", "INSTANCE_NUMBER", "SAMPLE_ID", "SESSION_ID", "CON_DBID")
```

All of the above columns are numbers.
The index key:

```
  key: (26):
 06 c5 0c 0b 06 63 09 04 c3 08 0e 3e 02 c1 02 05 c4 62 46 05 3b 03 c2 02 3d
 ff
```

It can be decrypted easily:

```sql
SQL> with input as (
  2    -- index key
  3    select '06 c5 0c 0b 06 63 09 04 c3 08 0e 3e 02 c1 02 05 c4 62 46 05 3b 03 c2 02 3d ff' c from dual),
  4    t(pos, num,c) as (
  5    -- traverse the index key recursively
  6    select 0 pos, 0, replace(c, ' ') c from input union all
  7    select pos+1,
  8           utl_raw.cast_to_number(hextoraw(substr(c, 3, to_number(substr(c,1,2), 'xx')*2))),
  9           substr(c, (to_number(substr(c, 1, 2), 'xx')+1)*2+1)
 10      from t
 11     where c<>'ff')
 12  select pos, num
 13    from t
 14   where pos>0
 15   order by pos
 16  /

       POS        NUM
---------- ----------
         1 1110059808
         2      71361
         3          1
         4   97690458
         5        160
```

Thus, the index key is: `dbid=1110059808`, `snap_id=71361`, `instance_number=1`, `sample_id=97690458`, `session_id=160`.

However, the index was built on six columns whereas the problem key contains only five.
What is the value of `CON_DBID` for the problem key?
That is where the problem lies.
`CON_DBID` was introduced in Oracle 12.1 and added as a `DEFAULT NOT NULL` column, i.e. that column addition was a metadata-only operation without updating the table blocks (unless `_add_col_optim_enabled` was set to `FALSE`).

```sql hl_lines="8"
SQL> select to_char(property, 'fm0xxxxxxx')
  2    from sys.col$
  3   where obj# = 22800
  4     and name = 'CON_DBID';

TO_CHAR(PROPERTY,'FM0XXXXXX
---------------------------
40000000
```

Notice that the property was `0x40000000` - I speculated that such a property was set for columns which were added with the default column optimization.
Some MOS notes prove that, i.e. [Table Columns Have Wrong Default Value After Transporting Tablespaces (Doc ID 1602994.1)](https://support.oracle.com/rs?type=doc&id=1602994.1).

I dumped the relevant table block and found that the `CON_DBID` column was not present in it.
The pieces of that puzzle started to fit together.

I had constructed a simple test case which reproduced the `ORA-8102` error:

```sql
SQL> create table t(x int, pad varchar2(100)) enable row movement;
SQL> insert /*+ append*/
  2    into t
  3  select level, lpad('x', 100, 'x')
  4    from dual
  5    connect by level<=1e5;
SQL> commit;
SQL>
SQL> alter table t add y int default 10 not null;
SQL>
SQL> create index t_xy_i on t(x,y);
SQL>
SQL> delete t where x<=1e5/2;
SQL> commit;
SQL>
SQL> alter table t shrink space;
alter table t shrink space
*
ERROR at line 1:
ORA-08102: index key not found, obj# 91957, file 10, block 3990 (2)
```

The problem is present in Oracle 11.2.0.4 and newer versions.
I did not test in earlier 11g patchsets.
Oracle Support raised a new bug: [ORA-8102 ON ALTER TABLE SHRINK SPACE WITH ADD COL OPTIMIZATION (unpublished)](https://support.oracle.com/rs?type=bug&id=22473983), which is still under investigation.

The tables suspected to the `ORA-8102` error can be identified easily by using the filter `bitand(col$.property, 1073741824)=1073741824` (`0x40000000` in hex):

```sql
SQL> select o.object_name
  2    from sys.col$ c,
  3         dba_objects o
  4   where bitand(c.property, 1073741824)=1073741824
  5     and o.object_id=c.obj#
  6     and o.owner='SYS'
  7   order by o.object_name;
```


I restricted the query above to the SYS schema.
Here is the output of that query in one of databases which was upgraded from 11.2.0.4 to 12.1.0.2 in 2015:

??? Show

    ```sql
    SQL> select o.object_name
      2    from sys.col$ c,
      3         dba_objects o
      4   where bitand(c.property, 1073741824)=1073741824
      5     and o.object_id=c.obj#
      6     and o.owner='SYS'
      7   order by o.object_name;

    OBJECT_NAME
    -------------------------------------------------------------------
    CDB_LOCAL_ADMINAUTH$
    HISTGRM$
    PROFNAME$
    WRH$_ACTIVE_SESSION_HISTORY
    WRH$_BG_EVENT_SUMMARY
    WRH$_BUFFERED_QUEUES
    WRH$_BUFFERED_SUBSCRIBERS
    WRH$_BUFFER_POOL_STATISTICS
    WRH$_CLUSTER_INTERCON
    WRH$_COMP_IOSTAT
    WRH$_CR_BLOCK_SERVER
    WRH$_CURRENT_BLOCK_SERVER
    WRH$_DATAFILE
    WRH$_DB_CACHE_ADVICE
    WRH$_DISPATCHER
    WRH$_DLM_MISC
    WRH$_DYN_REMASTER_STATS
    WRH$_DYN_REMASTER_STATS
    WRH$_ENQUEUE_STAT
    WRH$_EVENT_HISTOGRAM
    WRH$_EVENT_NAME
    WRH$_FILEMETRIC_HISTORY
    WRH$_FILESTATXS
    WRH$_IC_CLIENT_STATS
    WRH$_IC_DEVICE_STATS
    WRH$_INSTANCE_RECOVERY
    WRH$_INST_CACHE_TRANSFER
    WRH$_INTERCONNECT_PINGS
    WRH$_IOSTAT_DETAIL
    WRH$_IOSTAT_FILETYPE
    WRH$_IOSTAT_FILETYPE_NAME
    WRH$_IOSTAT_FUNCTION
    WRH$_IOSTAT_FUNCTION_NAME
    WRH$_JAVA_POOL_ADVICE
    WRH$_LATCH
    WRH$_LATCH_CHILDREN
    WRH$_LATCH_MISSES_SUMMARY
    WRH$_LATCH_NAME
    WRH$_LATCH_PARENT
    WRH$_LIBRARYCACHE
    WRH$_LOG
    WRH$_MEMORY_RESIZE_OPS
    WRH$_MEMORY_TARGET_ADVICE
    WRH$_MEM_DYNAMIC_COMP
    WRH$_METRIC_NAME
    WRH$_MTTR_TARGET_ADVICE
    WRH$_MUTEX_SLEEP
    WRH$_MVPARAMETER
    WRH$_OPTIMIZER_ENV
    WRH$_OSSTAT
    WRH$_OSSTAT_NAME
    WRH$_PARAMETER
    WRH$_PARAMETER_NAME
    WRH$_PERSISTENT_QMN_CACHE
    WRH$_PERSISTENT_QUEUES
    WRH$_PERSISTENT_SUBSCRIBERS
    WRH$_PGASTAT
    WRH$_PGA_TARGET_ADVICE
    WRH$_PLAN_OPERATION_NAME
    WRH$_PLAN_OPTION_NAME
    WRH$_PROCESS_MEMORY_SUMMARY
    WRH$_RESOURCE_LIMIT
    WRH$_ROWCACHE_SUMMARY
    WRH$_RSRC_CONSUMER_GROUP
    WRH$_RSRC_PLAN
    WRH$_RULE_SET
    WRH$_SEG_STAT
    WRH$_SEG_STAT_OBJ
    WRH$_SERVICE_NAME
    WRH$_SERVICE_STAT
    WRH$_SERVICE_WAIT_CLASS
    WRH$_SESSMETRIC_HISTORY
    WRH$_SESS_TIME_STATS
    WRH$_SESS_TIME_STATS
    WRH$_SGA
    WRH$_SGASTAT
    WRH$_SGA_TARGET_ADVICE
    WRH$_SHARED_POOL_ADVICE
    WRH$_SHARED_SERVER_SUMMARY
    WRH$_SQLCOMMAND_NAME
    WRH$_SQLSTAT
    WRH$_SQLTEXT
    WRH$_SQL_BIND_METADATA
    WRH$_SQL_PLAN
    WRH$_SQL_SUMMARY
    WRH$_SQL_WORKAREA_HISTOGRAM
    WRH$_STAT_NAME
    WRH$_STREAMS_APPLY_SUM
    WRH$_STREAMS_APPLY_SUM
    WRH$_STREAMS_CAPTURE
    WRH$_STREAMS_CAPTURE
    WRH$_STREAMS_POOL_ADVICE
    WRH$_SYSMETRIC_HISTORY
    WRH$_SYSMETRIC_SUMMARY
    WRH$_SYSSTAT
    WRH$_SYSTEM_EVENT
    WRH$_SYS_TIME_MODEL
    WRH$_TABLESPACE
    WRH$_TABLESPACE_SPACE_USAGE
    WRH$_TABLESPACE_STAT
    WRH$_TEMPFILE
    WRH$_TEMPSTATXS
    WRH$_THREAD
    WRH$_TOPLEVELCALL_NAME
    WRH$_UNDOSTAT
    WRH$_WAITCLASSMETRIC_HISTORY
    WRH$_WAITSTAT
    WRI$_ADV_SQLT_PLAN_HASH
    WRI$_OPTSTAT_HISTGRM_HISTORY
    WRI$_SQLSET_BINDS
    WRI$_SQLSET_DEFINITIONS
    WRI$_SQLSET_MASK
    WRI$_SQLSET_PLANS
    WRI$_SQLSET_PLAN_LINES
    WRI$_SQLSET_STATEMENTS
    WRI$_SQLSET_STATISTICS
    WRI$_SQLTEXT_REFCOUNT

    117 rows selected.
    ```

It can be seen that mostly AWR tables are affected: `WRH$%`, `WRI%`.
A brand new 12c database's AWR tables do not have the property set to `1073741824` (`0x40000000`) unless those are created manually.
One potential workaround for this issue is to set `_add_col_optim_enabled` to `FALSE`.
If the issue is already encountered, then it is also possible to rebuild the problem table to update the affected column.
It can be done by moving table, redefining it online, or setting the column to itself.
