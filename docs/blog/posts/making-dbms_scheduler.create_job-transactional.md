---
categories:
  - Oracle
date:
  created: 2021-06-30T17:46:00
description: >-
  Demonstrate how to make DBMS_SCHEDULER.CREATE_JOB transactional using an undocumented procedure DBMS_ISCHED.SET_NO_COMMIT_FLAG.
tags:
  - 19c
  - PL/SQL
---

# Making DBMS\_SCHEDULER.CREATE\_JOB Transactional

Let us investigate how to make `DBMS_SCHEDULER.CREATE_JOB` support transactions.

<!-- more -->

It is known that `DBMS_SCHEDULER.CREATE_JOB` is non-transactional as opposed to the old `DBMS_JOB`.
There is even an Oracle idea to provide a transactional interface: [link](https://community.oracle.com/tech/apps-infra/discussion/4390942/dbms-scheduler-create-job-remove-implicit-commit).
In Oracle 19c `DBMS_JOB` jobs are actually `DBMS_SCHEDULER` jobs, and they can be part of a bigger transaction.
I was curious how it is done and if I can make it work for `DBMS_SCHEDULER` jobs.

## Demonstration

Here is a test script that I used for this blogpost on 19.9:

```sql
SQL> conn / as sysdba
Connected.
SQL>
SQL> alter session set container=pdb;

Session altered.

SQL>
SQL> exec dbms_scheduler.purge_log()

PL/SQL procedure successfully completed.

SQL>
SQL> drop user tc cascade;

User dropped.

SQL>
SQL> grant create job, create session to tc identified by tc;

Grant succeeded.

SQL>
SQL> grant execute on sys.dbms_isched to tc;

Grant succeeded.
```

Firstly, let us create a traditional `DBMS_SCHEDULER` job so as to demonstrate that `CREATE_JOB` is non-transactional.
By "non-transactional" here I mean that it does not leave the session with an open transaction.

```sql
SQL> conn tc/tc@localhost/pdb
Connected.
SQL>
SQL> doc
DOC>################################################################################
DOC>#  Traditional Job
DOC>################################################################################
DOC>#
SQL>
SQL> select dbms_transaction.local_transaction_id from dual;

LOCAL_TRANSACTION_ID
--------------------------------------------------------------------------------


SQL>
SQL> exec dbms_scheduler.create_job( -
>   job_name => 'JOB_NON_TX', -
>   job_type => 'PLSQL_BLOCK', -
>   job_action => 'null;', -
>   enabled    => true)

PL/SQL procedure successfully completed.

SQL>
SQL> select dbms_transaction.local_transaction_id from dual;

LOCAL_TRANSACTION_ID
--------------------------------------------------------------------------------


SQL>
SQL> exec dbms_session.sleep(5)

PL/SQL procedure successfully completed.

SQL>
SQL> col job_name for a10
SQL>
SQL> select job_name, state
  2    from user_scheduler_jobs;

no rows selected

SQL>
SQL> col log_date for a35
SQL> select log_date, job_name, status
  2    from user_scheduler_job_run_details
  3   order by log_date;

LOG_DATE                            JOB_NAME   STATUS
----------------------------------- ---------- ----------
30-JUN-21 12.02.26.780546 PM +01:00 JOB_NON_TX SUCCEEDED
```

Now, I try the same but I call `DBMS_ISCHED.SET_NO_COMMIT_FLAG` before calling the `CREATE_JOB` procedure.

```sql
SQL> doc
DOC>################################################################################
DOC>#  Transactional Job
DOC>################################################################################
DOC>#
SQL>
SQL> exec sys.dbms_isched.set_no_commit_flag

PL/SQL procedure successfully completed.

SQL>
SQL> select dbms_transaction.local_transaction_id from dual;

LOCAL_TRANSACTION_ID
--------------------------------------------------------------------------------


SQL>
SQL> exec dbms_scheduler.create_job( -
>   job_name => 'JOB_TX', -
>   job_type => 'PLSQL_BLOCK', -
>   job_action => 'null;', -
>   enabled    => true)

PL/SQL procedure successfully completed.

SQL>
SQL> select dbms_transaction.local_transaction_id from dual;

LOCAL_TRANSACTION_ID
--------------------------------------------------------------------------------
9.23.604

SQL>
SQL> exec dbms_session.sleep(5)

PL/SQL procedure successfully completed.

SQL>
SQL> col job_name for a10
SQL>
SQL> select job_name, state
  2    from user_scheduler_jobs;

JOB_NAME   STATE
---------- ----------
JOB_TX     SCHEDULED

SQL>
SQL> col log_date for a35
SQL> select log_date, job_name, status
  2    from user_scheduler_job_run_details
  3   order by log_date;

LOG_DATE                            JOB_NAME   STATUS
----------------------------------- ---------- ----------
30-JUN-21 12.02.26.780546 PM +01:00 JOB_NON_TX SUCCEEDED
```

The things are a bit different this time around:

- `DBMS_SCHEDULER.CREATE_JOB` left the session with an open transaction.
- The job is not started.
- It is not demonstrated here, but it is possible to issue a `ROLLBACK` and it will remove the job definition.

Such a job gets started as soon as the transaction is committed:

```sql
SQL> commit;

Commit complete.

SQL>
SQL> exec dbms_session.sleep(5)

PL/SQL procedure successfully completed.

SQL>
SQL> col job_name for a10
SQL> col state for a10
SQL>
SQL> select job_name, state
  2    from user_scheduler_jobs;

no rows selected

SQL>
SQL> col status for a10
SQL>
SQL> col log_date for a35
SQL> select log_date, job_name, status
  2    from user_scheduler_job_run_details
  3   order by log_date;

LOG_DATE                            JOB_NAME   STATUS
----------------------------------- ---------- ----------
30-JUN-21 12.02.26.780546 PM +01:00 JOB_NON_TX SUCCEEDED
30-JUN-21 12.02.36.835878 PM +01:00 JOB_TX     SUCCEEDED
```

## Conclusion

The post demonstrates that one can utilize undocumented `DBMS_ISCHED.SET_NO_COMMIT_FLAG` to make `DBMS_SCHEDULER.CREATE_JOB` transactional.
Since the package is undocumented, there is no guarantee that it will keep working in future versions.
Hopefully, Oracle will make a transactional interface available someday.
