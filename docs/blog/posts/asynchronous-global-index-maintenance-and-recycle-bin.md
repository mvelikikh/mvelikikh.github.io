---
categories:
  - Oracle
date:
  created: 2017-04-30T17:43:00
description: >-
  Oracle automatic maintenance job SYS.PMO_DEFERRED_GIDX_MAINT_JOB, responsible for cleaning up global indexes after drop/truncate operations in the asynchronous global index maintenance feature, may try to process indexes in the Recycle Bin, failing with ORA-38301.
  The problem is that the job stops further processing after encountering an error, which means that it may not process all indexes requiring maintenance after drop/truncate operations.
tags:
  - 12c
  - Indexing
  - OERR
---

# Asynchronous Global Index Maintenance and Recycle Bin

Got an Oracle error `ORA-38301: "can not perform DDL/DML over objects in Recycle Bin"` in the alert log.

<!-- more -->

``` hl_lines="2"
ORCL(3):Errors in file /u01/app/oracle/diag/rdbms/orcl12c/orcl12c/trace/orcl12c_j000_10274.trc:
ORA-12012: error on auto execute of job "SYS"."PMO_DEFERRED_GIDX_MAINT_JOB"
ORA-38301: can not perform DDL/DML over objects in Recycle Bin
ORA-06512: at "SYS.DBMS_PART", line 131
ORA-06512: at "SYS.DBMS_PART", line 131
ORA-06512: at "SYS.DBMS_PART", line 120
ORA-06512: at line 1
```

The highlighted line indicates that the error relates to the automatic scheduler job `SYS.PMO_DEFERRED_GIDX_MAINT_JOB`, which was introduced in the Oracle database 12.1 release.
It is responsible for cleaning up indexes after drop/truncate operations: [documentation](https://docs.oracle.com/en/database/oracle/oracle-database/12.2/vldbg/maintenance-partition-can-be-performed.html#GUID-087B87A6-959A-40C6-82AF-36E401FD089B).

I delved into the issue and found that the job `SYS.PMO_DEFERRED_GIDX_MAINT_JOB` does not ignore objects in the Recycle Bin.
Here is a short test case to demonstrate that:

```sql
SQL> select banner from v$version;

BANNER
--------------------------------------------------------------------------------
Oracle Database 12c Enterprise Edition Release 12.2.0.1.0 - 64bit Production
PL/SQL Release 12.2.0.1.0 - Production
CORE    12.2.0.1.0      Production
TNS for Linux: Version 12.2.0.1.0 - Production
NLSRTL Version 12.2.0.1.0 - Production

SQL> create table t(x)
  2  partition by range(x)
  3  (
  4    partition values less than(maxvalue)
  5  )
  6  as
  7  select 1
  8    from dual;

Table created.

SQL>
SQL> create index t_i on t(x);

Index created.

SQL>
SQL> alter table t truncate partition for(1) update indexes;

Table truncated.

SQL>
SQL> select status, orphaned_entries
  2    from ind
  3   where index_name = 'T_I';

STATUS   ORP
-------- ---
VALID    YES

SQL>
SQL> drop table t;

Table dropped.
```

Now I run the job `SYS.PMO_DEFERRED_GIDX_MAINT_JOB` manually as if it was running automatically:

```sql
SQL> select run_count, failure_count, state from user_scheduler_jobs where job_name='PMO_DEFERRED_GIDX_MAINT_JOB';

 RUN_COUNT FAILURE_COUNT STATE
---------- ------------- --------------------
         4             0 SCHEDULED

SQL>  exec dbms_scheduler.run_job( 'PMO_DEFERRED_GIDX_MAINT_JOB', false)

PL/SQL procedure successfully completed.

SQL>  select run_count, failure_count, state from user_scheduler_jobs where job_name='PMO_DEFERRED_GIDX_MAINT_JOB';

 RUN_COUNT FAILURE_COUNT STATE
---------- ------------- --------------------
         5             1 SCHEDULED
```

The job `SYS.PMO_DEFERRED_GIDX_MAINT_JOB` calls the `DBMS_PART.CLEANUP_GIDX_INTERNAL` procedure.
Thus, the same `ORA-38301` error can be raised if I call the `DBMS_PART.CLEANUP_GIDX` procedure:

```sql
SQL> exec DBMS_PART.CLEANUP_GIDX (user)
BEGIN DBMS_PART.CLEANUP_GIDX (user); END;

*
ERROR at line 1:
ORA-38301: can not perform DDL/DML over objects in Recycle Bin
ORA-06512: at "SYS.DBMS_PART", line 131
ORA-06512: at "SYS.DBMS_PART", line 131
ORA-06512: at "SYS.DBMS_PART", line 120
ORA-06512: at "SYS.DBMS_PART", line 193
ORA-06512: at line 1
```

The problem here is that the automatic job stops further processing on any error.
It means that we may end up having lots of indexes requiring cleanup that are not processed automatically and have to undergone manual actions to reset their state.

**tl;dr.** Although the Asynchronous Global Index Maintenance feature is quite useful and can greatly speedup the partition maintenance operations `TRUNCATE PARTITION` and `DROP PARTITION`, it still does not ignore objects in the Recycle Bin.
Therefore, the automatic maintenance job `PMO_DEFERRED_GIDX_MAINT_JOB` may fail and does not process all of the indexes that require cleanup.
