---
categories:
  - Oracle
date:
  created: 2017-03-15T09:08:00
description: >-
  A behavior change is introduced in Oracle Database 12.2 on Linux when login.sql is not invoked from SQLPATH anymore.
  ORACLE_PATH should be used instead.
tags:
  - 12c
  - SQL*Plus
---

# SQL*Plus 12.2 and searching path of login.sql

Having installed Oracle Database 12.2 on a client, I have noticed that the `login.sql` script, which is placed in a custom directory specified by `SQLPATH`, is not invoked anymore.

<!-- more -->

Here is my `login.sql`:

```sql title="/tmp/sqlpath/login.sql"
select 'login.sql invoked' output
  from dual;
```

The `login.sql` script is not invoked when I connect through SQL\*Plus 12.2 despite the fact the `SQLPATH` environment variable is set:

```sql
[oracle@localhost]$ export SQLPATH=/tmp/sqlpath
[oracle@localhost]$ sqlplus tc/tc@ora12

SQL*Plus: Release 12.2.0.1.0 Production on Wed Mar 15 09:20:52 2017

Copyright (c) 1982, 2016, Oracle.  All rights reserved.

Last Successful login time: Wed Mar 15 2017 09:16:06 +07:00

Connected to:
Oracle Database 12c Enterprise Edition Release 12.1.0.2.0 - 64bit Production
With the Partitioning, Automatic Storage Management, OLAP, Advanced Analytics,
Real Application Testing and Unified Auditing options

SQL>
```

This issue is documented in [SQL\*Plus 12.2.0.1.0 Change in Behavior for Search Path of Login.sql (SQL\*Plus User Profile Script) (Doc ID 2241021.1)](https://support.oracle.com/rs?type=doc&id=2241021.1).

Unsurprisignly, if I set `ORACLE_PATH`, then `login.sql` is invoked:

```sql hl_lines="1-2 17-19"
[oracle@localhost]$ export ORACLE_PATH=$SQLPATH
[oracle@localhost]$ unset SQLPATH
[oracle@localhost]$ sqlplus tc/tc@ora12

SQL*Plus: Release 12.2.0.1.0 Production on Wed Mar 15 09:21:13 2017

Copyright (c) 1982, 2016, Oracle.  All rights reserved.

Last Successful login time: Wed Mar 15 2017 09:20:52 +07:00

Connected to:
Oracle Database 12c Enterprise Edition Release 12.1.0.2.0 - 64bit Production
With the Partitioning, Automatic Storage Management, OLAP, Advanced Analytics,
Real Application Testing and Unified Auditing options


OUTPUT
---------------------------------------------------
login.sql invoked

SQL>
```

The MOS note also contains information that this new behaviour may influence earlier releases when the PSU or CI are released for them.
I have no idea why Oracle has changed the existing functionality with `login.sql`, but that is definitely something to keep in mind in case you are going to upgrade to a new release.

Interestingly, SQLcl still honors `SQLPATH` even when both `SQLPATH` and `ORACLE_PATH` are set:

```sql hl_lines="7 8 21-23"
[oracle@localhost]$ cat /tmp/sqlpath/login.sql
select 'login.sql invoked' output
  from dual;
[oracle@localhost]$ cat /tmp/oracle_path/login.sql
select 'oracle_path invoked'
  from dual;
[oracle@localhost]$ export ORACLE_PATH=/tmp/oracle_path
[oracle@localhost]$ export SQLPATH=/tmp/sqlpath
[oracle@localhost]$ ./sql tc/tc@ora12

SQLcl: Release 12.2.0.1.0 RC on Ср мар 15 09:42:08 2017

Copyright (c) 1982, 2017, Oracle.  All rights reserved.

Connected to:
Oracle Database 12c Enterprise Edition Release 12.1.0.2.0 - 64bit Production
With the Partitioning, Automatic Storage Management, OLAP, Advanced Analytics,
Real Application Testing and Unified Auditing options


OUTPUT
-----------------
login.sql invoked

```
