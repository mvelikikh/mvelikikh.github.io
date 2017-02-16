---
categories:
  - Oracle
date:
  created: 2017-02-16T11:03:00
description: >-
  Encountered an ORA-3180 on an Active Data Guard standby database.
  Investigated how exactly Data Guard identifies the primary database to serve queries using sequences.
tags:
  - 12c
  - Data Guard
  - Initialization parameter
  - OERR
---

# ORA-3180 on Active Data Guard standby database

Got a call asking me to provide advice on the cause of ORA-3180 error on an Active Data Guard standby database instance

<!-- more -->

```sql hl_lines="6"
SQL> explain plan for select * from dual;
explain plan for select * from dual
                        *
ERROR at line 1:
ORA-00604: error occurred at recursive SQL level 1
ORA-03180: Sequence values cannot be allocated for Oracle Active Data Guard standby.
```

It is a documented fact that sequences can be used within an Oracle Active Data Guard physical standby database: [Using Sequences in Oracle Active Data Guard](http://docs.oracle.com/database/121/SBYDB/manage_ps.htm#SBYDB5164).
I have not found whether the actual algorithm used to identify the primary database is documented either on MOS or in the documentation.
I have been tinkering around with the issue for a while, so this blog post is about my findings.

First, the most useful source of information about this error is the server process trace file. Here is an excerpt from it:

``` hl_lines="9"
*** 2017-02-09 13:12:59.339
*** SESSION ID:(51.12274) 2017-02-09 13:12:59.339
*** CLIENT ID:() 2017-02-09 13:12:59.339
*** SERVICE NAME:(SYS$USERS) 2017-02-09 13:12:59.339
*** MODULE NAME:(sqlplus@misha2 (TNS V1-V3)) 2017-02-09 13:12:59.339
*** CLIENT DRIVER:(SQL*PLUS) 2017-02-09 13:12:59.339
*** ACTION NAME:() 2017-02-09 13:12:59.339

krsd_get_primary_connect_string: found pcs 'adg3' by reverse lookup
Connected to primary database target adg3
*** 2017-02-09 13:12:59.372643 3981 krsb.c
krsb_stream_dispatch: Error 604 during streaming operation to destination 1
*** 2017-02-09 13:12:59.372842 2178 krsu.c
krsu_rmi_send_recv: Encountered error 604 sending message to connection 1
*** 2017-02-09 13:12:59.372867 2023 krsu.c
krsu_rmi_lwc_send_recv: Encountered error status 604 sending RMI message to adg3
kdn_sseq_so_primary: Encountered send recv exception 604
```

I was curious about what "by reverse lookup" meant.
I speculate that it means that the primary database TNS alias (or the fully-formed TNS descriptor) is obtained from one of `LOG_ARCHIVE_DEST_n` parameters (let it call `LADn` for the sake of shortness).

And conversely, there is a forward lookup using the `FAL_SERVER` parameter:

```
krsd_get_primary_connect_string: found pcs 'adg1' by FAL_SERVER lookup
Connected to primary database target adg1
krsd_get_primary_connect_string: found pcs 'adg1' by FAL_SERVER lookup
Connected to primary database target adg1
```

It seems that Oracle is considering either the `LADn` or `FAL_SERVER` parameter when it tries to identify the primary database connect identifier to request a sequence cache.

I have done several tests in my sandbox Data Guard environment, and I believe that the `LADn` parameters take precedence over `FAL_SERVER`.
All of the tests were performed using the following Data Guard configuration:

```
DGMGRL> show configuration;

Configuration - adg

  Protection Mode: MaxAvailability
  Members:
  adg1 - Primary database
    adg2 - Physical standby database
    adg3 - Physical standby database

Fast-Start Failover: DISABLED

Configuration Status:
SUCCESS   (status updated 10 seconds ago)
```

I ran my scripts in `adg2`, which is a physical standby database, and the databases have DBBP 12.1.0.2.161018 applied.
Here is what I was observing while doing my experiments:

**1. The first `LADn` with `db_unique_name=<primary_db>` is selected.
The corresponding `LOG_ARCHIVE_DEST_STATE_N`, `VALID_FOR` parameters are ignored.**

Here is an example where I set `VALID_FOR=(ALL_LOGFILES,STANDBY_ROLE)`, `LOG_ARCHIVE_DEST_STATE_4=DEFER`, and nevertheless `LADn` was used to identify the primary database TNS:

```sql
SQL> alter system set fal_server='adg1' log_archive_dest_4='service=non_existent valid_for=(all_logfiles,standby_role) db_unique_name=adg1' log_archive_dest_state_4=defer;

System altered.

SQL> conn / as sysdba
Connected.
SQL> explain plan for select * from dual;
explain plan for select * from dual
                        *
ERROR at line 1:
ORA-00604: error occurred at recursive SQL level 1
ORA-03180: Sequence values cannot be allocated for Oracle Active Data Guard standby.
```

The trace file:

```
krsd_get_primary_connect_string: found pcs 'non_existent' by reverse lookup
OCIServerAttach failed -1
.. Detailed OCI error val is 12154 and errmsg is 'ORA-12154: TNS:could not resolve the connect identifier specified
'
OCIServerAttach failed -1
.. Detailed OCI error val is 12154 and errmsg is 'ORA-12154: TNS:could not resolve the connect identifier specified
'
OCIServerAttach failed -1
.. Detailed OCI error val is 12154 and errmsg is 'ORA-12154: TNS:could not resolve the connect identifier specified
'
OCIServerAttach failed -1
.. Detailed OCI error val is 12154 and errmsg is 'ORA-12154: TNS:could not resolve the connect identifier specified
'
*** 2017-02-09 14:05:22.153950 4929 krsh.c
Error 12154 received logging on to the standby
*** 2017-02-09 14:05:22.153969 1460 krsu.c
krsu_rmi_lwc_connect: Encountered error status 12154 attempting connection to non_existent
non_existent: Encountered connect exception 12154
```

**2. When there is no `LADn` with `db_unique_name=<primary_db>` present, then the `FAL_SERVER` parameter is used.
It is sequentially traversed left-to-right:**

```sql
SQL> alter system set fal_server='x','adg1','y';

System altered.

SQL> explain plan for select * from dual;

Explained.
```

The trace file:

```
*** 2017-02-09 14:42:50.944
*** SESSION ID:(47.31048) 2017-02-09 14:42:50.944
*** CLIENT ID:() 2017-02-09 14:42:50.944
*** SERVICE NAME:(SYS$USERS) 2017-02-09 14:42:50.944
*** MODULE NAME:(sqlplus@userhost (TNS V1-V3)) 2017-02-09 14:42:50.944
*** CLIENT DRIVER:(SQL*PLUS) 2017-02-09 14:42:50.944
*** ACTION NAME:() 2017-02-09 14:42:50.944

OCIServerAttach failed -1
.. Detailed OCI error val is 12154 and errmsg is 'ORA-12154: TNS:could not resolve the connect identifier specified
'
OCIServerAttach failed -1
.. Detailed OCI error val is 12154 and errmsg is 'ORA-12154: TNS:could not resolve the connect identifier specified
'
OCIServerAttach failed -1
.. Detailed OCI error val is 12154 and errmsg is 'ORA-12154: TNS:could not resolve the connect identifier specified
'
OCIServerAttach failed -1
.. Detailed OCI error val is 12154 and errmsg is 'ORA-12154: TNS:could not resolve the connect identifier specified
'
*** 2017-02-09 14:42:50.960591 4929 krsh.c
Error 12154 received logging on to the standby
*** 2017-02-09 14:42:50.960676 4929 krsh.c
FAL[client, USER]: Error 12154 connecting to x for fetching gap sequence
ORA-12154: TNS:could not resolve the connect identifier specified
krsd_get_primary_connect_string: found pcs 'adg1' by FAL_SERVER lookup
Connected to primary database target adg1
OCIServerAttach failed -1
.. Detailed OCI error val is 12154 and errmsg is 'ORA-12154: TNS:could not resolve the connect identifier specified
'
OCIServerAttach failed -1
.. Detailed OCI error val is 12154 and errmsg is 'ORA-12154: TNS:could not resolve the connect identifier specified
'
OCIServerAttach failed -1
.. Detailed OCI error val is 12154 and errmsg is 'ORA-12154: TNS:could not resolve the connect identifier specified
'
OCIServerAttach failed -1
.. Detailed OCI error val is 12154 and errmsg is 'ORA-12154: TNS:could not resolve the connect identifier specified
'
*** 2017-02-09 14:42:51.071116 4929 krsh.c
Error 12154 received logging on to the standby
*** 2017-02-09 14:42:51.071188 4929 krsh.c
FAL[client, USER]: Error 12154 connecting to x for fetching gap sequence
ORA-12154: TNS:could not resolve the connect identifier specified
krsd_get_primary_connect_string: found pcs 'adg1' by FAL_SERVER lookup
Connected to primary database target adg1
```

How could one come across this issue:

1. Have incorrect parameter settings and do not use Data Guard Broker.
   That is what the problem was when my client came upon it.
1. Actually, we can face this issue using Data Guard Broker too.
   Data Guard Broker does not change the `FAL_SERVER` parameters on switchover, at least, it is how it works now.
   See, for example, [this link](https://community.oracle.com/thread/3970711).

One possible workaround - it is to manually invoke the DGMGRL `enable configuration` command each time when a switchover takes place.
I raised an SR with Oracle about this problem but I decided not to progress towards the permanent solution due to lack of time.
