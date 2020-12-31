---
categories:
  - Oracle
date:
  created: 2020-12-31T04:10:00
description: >-
  Demonstrate how to create a physical standby RAC database for a single-instance primary using DBCA.
tags:
  - 18c
  - 19c
  - Data Guard
  - RAC
---

# Creating RAC Physical Standby for Single Instance Primary

Oracle made some interesting improvements in the Database Configuration Assistant (DBCA) in 18c simplifying the creation of a standby database, namely allowing to create a copy of a database that will be a RAC database itself regardless of what type the primary database is (e.g. single-instance/RAC/etc.).
This post demonstrates this capability.

<!-- more -->

[Database Administrator's Guide: Changes in Oracle Database 18c](https://docs.oracle.com/en/database/oracle/oracle-database/18/admin/release-changes.html#GUID-7E653931-F2C9-4746-BA12-799508186F59):

> **Creating a copy of an Oracle RAC database**
>
> A copy of an Oracle RAC database can be created using the `-createDuplicateDB` command option `-databaseConfigType` with the value of `RAC` or `RACONENODE`.

It has been possible to create a standby database using [the createDuplicateDB DBCA command](https://docs.oracle.com/en/database/oracle/oracle-database/12.2/admin/creating-and-configuring-an-oracle-database.html#GUID-7F4B1A64-5B08-425A-A62E-854542B3FD4E) since 12.2.
18c added a new capability to specify the database configuration type of a new standby, such as: RAC, RAC One Node, or a regular single instance database.
This method by itself requires some prerequisite actions.
I do not see that these are documented, so that I am writing this blog post.

## Setup

### Primary

- Hostname: `primary`
- `db_name`: `orcl`
- `db_unique_name`: `orcl`
- Configuration Type: `Single Instance`

### Standby

- Hostnames: `rac1.example.com`, `rac2.example.com`
- `db_unique_name`: `racdb`
- Configuration Type: `RAC`
- SCAN port: 1521
- Local listener port: 1522
- Grid Home: `/u01/app/19.3.0/grid`, `owner=grid`
- DB Home: `/u01/app/oracle/product/19.3.0/dbhome_1`, `owner=oracle` (role separation)
- ASM disk groups: single disk group `DATA` for this demo

The naming convention might be a bit odd, but the main purpose of this configuration is to provide some initial steps to setup a new RAC database with a view to making it a new primary.

## Creating RAC Physical Standby

### DBCA Command

This is a DBCA command that I will run to create a standby database in 19.9:

```bash
dbca -createDuplicateDB -silent \
     -gdbName orcl \
     -primaryDBConnectionString primary:1521/orcl \
     -sid racdb \
     -initParams "dg_broker_start=true" \
     -sysPassword change_on_install \
     -adminManaged \
     -nodelist rac1,rac2 \
     -recoveryAreaDestination +DATA \
       -recoveryAreaSize 10000 \
     -databaseConfigType RAC \
     -useOMF true \
     -storageType ASM \
       -datafileDestination +DATA \
     -createAsStandby \
       -dbUniqueName racdb \
     -createListener rac1.example.com:1522
```

Firstly, let me go over the keys that are worth mentioning.

1. `-primaryDBConnectionString primary:1521/orcl` - it should have a specific port number even if it is default 1521
1. `-createListener rac1.example.com:1522` - this is the most interesting part.
   This is part of the RMAN block that is run to create a physical standby database:
   ```
   duplicate target database
   for standby
   from active database
   dorecover
   nofilenamecheck
   ;
   ```

It is [the push-based method](https://docs.oracle.com/en/database/oracle/oracle-database/19/bradv/rman-duplicating-databases.html#GUID-F446FBAC-3BEE-474A-B421-1BE1F926BB9A) of active database duplication.
Therefore, the primary database should be able to connect to the new standby.
I specified the local listener endpoint (1522) in this example.
Then, DBCA always tries to create a new listener in this configuration.
I do not know how to avoid that here.
Even worse, it attempts to create a new listener in the database home rather than the Grid Infrastructure (GI) home.
Thankfully, it silently swallows an error if the listener already exists (which in my case runs from the GI home).

Here is a sample excerpt from the DBCA log file to substantiate that remark with some facts:

``` hl_lines="3 24 36 39"
[progressPage.flowWorker] [ 2020-12-30 19:04:30.642 UTC ] [ClusterInfo.getHostName:462]  Hostname = rac1
INFO: Dec 30, 2020 7:04:30 PM oracle.install.commons.system.process.ProcessLauncher launchProcess
INFO: Executing [/u01/app/oracle/product/19.3.0/dbhome_1/bin/lsnrctl, start, rac1.example.com]

INFO: Dec 30, 2020 7:04:30 PM oracle.install.commons.system.process.ProcessLauncher launchProcess
INFO: Starting Output Reader Threads for process /u01/app/oracle/product/19.3.0/dbhome_1/bin/lsnrctl

INFO: Dec 30, 2020 7:04:30 PM oracle.assistants.common.util.NetworkConfigHelper$2 processLine
INFO:

INFO: Dec 30, 2020 7:04:30 PM oracle.assistants.common.util.NetworkConfigHelper$2 processLine
INFO: LSNRCTL for Linux: Version 19.0.0.0.0 - Production on 30-DEC-2020 19:04:30

INFO: Dec 30, 2020 7:04:30 PM oracle.assistants.common.util.NetworkConfigHelper$2 processLine
INFO:

INFO: Dec 30, 2020 7:04:30 PM oracle.assistants.common.util.NetworkConfigHelper$2 processLine
INFO: Copyright (c) 1991, 2020, Oracle.  All rights reserved.

INFO: Dec 30, 2020 7:04:30 PM oracle.assistants.common.util.NetworkConfigHelper$2 processLine
INFO:

INFO: Dec 30, 2020 7:04:30 PM oracle.assistants.common.util.NetworkConfigHelper$2 processLine
INFO: TNS-01106: Listener using listener name LISTENER has already been started

INFO: Dec 30, 2020 7:04:30 PM oracle.install.commons.system.process.ProcessLauncher launchProcess
INFO: The process /u01/app/oracle/product/19.3.0/dbhome_1/bin/lsnrctl exited with code 1

INFO: Dec 30, 2020 7:04:30 PM oracle.install.commons.system.process.ProcessLauncher launchProcess
INFO: Waiting for output processor threads to exit.

INFO: Dec 30, 2020 7:04:30 PM oracle.install.commons.system.process.ProcessLauncher launchProcess
INFO: Output processor threads exited.

INFO: Dec 30, 2020 7:04:30 PM oracle.assistants.common.util.NetworkConfigHelper startListener
INFO: Exit code of lsnrctl is:1

INFO: Dec 30, 2020 7:04:30 PM oracle.assistants.dbca.driver.backend.steps.ListenerConfigStep createStaticListener
INFO: Static listener created.

INFO: Dec 30, 2020 7:04:30 PM oracle.assistants.dbca.driver.StepDBCAJob$1 update
INFO: Percentage Progress got for job:Listener config step progress:100.0
```

There is another little drawback with this approach - it creates `listener.ora` in the database home which uses a static configuration.
It is harmless, but I would rather clean it up after the exercise to have a nice and tidy environment.

### Prerequisite Steps

It should be possible to establish a connection from the primary host using the local listener endpoint: `rac1.example.com:1522`.
I do not discuss the required DNS setup - it is implied.

I need to configure a static registration for the new RAC instance.
For that, I edit my GI `listener.ora` on the host I am going to run the duplicate command from (`rac1`):

```
# /u01/app/19.3.0/grid/network/admin/listener.ora
SID_LIST_LISTENER=
  (SID_LIST=
      (SID_DESC=
         (SID_NAME=racdb1)
         (ORACLE_HOME=/u01/app/oracle/product/19.3.0/dbhome_1)
       )
   )
```

That is basically it.
Once I reload the local listener, I am good to continue to the next step.

### Running the DBCA Command

```bash
[oracle@rac1 ~]$ dbca -createDuplicateDB -silent \
>      -gdbName orcl \
>      -primaryDBConnectionString primary:1521/orcl \
>      -sid racdb \
>      -initParams "dg_broker_start=true" \
>      -sysPassword change_on_install \
>      -adminManaged \
>      -nodelist rac1,rac2 \
>      -recoveryAreaDestination +DATA \
>        -recoveryAreaSize 10000 \
>      -databaseConfigType RAC \
>      -useOMF true \
>      -storageType ASM \
>        -datafileDestination +DATA \
>      -createAsStandby \
>        -dbUniqueName racdb \
>      -createListener rac1.example.com:1522
Prepare for db operation
22% complete
Listener config step
44% complete
Auxiliary instance creation
67% complete
RMAN duplicate
89% complete
Post duplicate database operations
100% complete

Look at the log file "/u01/app/oracle/cfgtoollogs/dbca/racdb/racdb.log" for further details.
```

That is it:

```sql
SQL> select database_role from v$database;

DATABASE_ROLE
----------------
PHYSICAL STANDBY

SQL> select instance_name, host_name from gv$instance;

INSTANCE_NAME    HOST_NAME
---------------- --------------------
racdb1           rac1.example.com
racdb2           rac2.example.com
```

## Further Steps

1. Delete `/u01/app/oracle/product/19.3.0/dbhome_1/network/admin/listener.ora`.
   DBCA created this file with the following content:
   ```
   SID_LIST_RAC1.EXAMPLE.COM =
     (SID_LIST =
       (SID_DESC =
         (SID_NAME = racdb1)
       )
     )

   RAC1.EXAMPLE.COM =
     (ADDRESS_LIST =
       (ADDRESS = (PROTOCOL = TCP)(HOST = rac1.example.com)(PORT = 1522))
     )
   ```
1. Adding standby redo logs, creating a new Data Guard Configuration, enabling `FORCE_LOGGING`, Flashback database, etc. - I do not mention it here.
   The purpose of this post to show how to instantiate a new RAC standby database in one command after completing some simple preliminary steps.

## Notable Downsides

There ain't no such thing as a free lunch.
Both slow connection between the sites, and a "huge" database size limits the applicability of this method.
I do not see how this method can utilize [the restartable duplication](https://docs.oracle.com/en/database/oracle/oracle-database/19/bradv/rman-duplicating-databases.html#GUID-4A9A4F04-0D65-4BC0-AE4B-EFBD453D017F) too.
In all other cases, it is possible to quickly spin up a new RAC standby database using this excellent DBCA `createDuplicateDB` command.
