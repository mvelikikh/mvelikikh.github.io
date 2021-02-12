---
categories:
  - Oracle
date:
  created: 2021-02-12T02:23:00
description: >-
  The cluster verification utility (CVU) command failed with the `PRVF-5157` and `PRVF-5431` errors.
  This post demonstrates how the errors were diagnosed and the root cause was identified.
tags:
  - 19c
  - Clusterware
  - OERR
---

# Diagnosing Cluster Verification Utility (CVU) Errors

A cluster verification utility (CVU) command failed with the `PRVF-5157` and `PRVF-5431` errors.
This post demonstrates how the errors were diagnosed and the root cause was identified.

<!-- more -->

``` hl_lines="3 10"
[grid@rac1 ~]$ cluvfy comp vdisk -n rac1 -verbose

Verifying Voting Disk ...FAILED (PRVF-5157, PRVF-5431)

Verification of Voting Disk was unsuccessful on all the specified nodes.


Failures were encountered during execution of CVU verification request "Voting Disk".

Verifying Voting Disk ...FAILED
PRVF-5157 : could not verify ASM disk group "GRID" for voting disk location
"/dev/flashgrid/racq.lun1" is available on node "rac1"
PRVF-5157 : could not verify ASM disk group "GRID" for voting disk location
"/dev/flashgrid/rac1.lun1" is available on node "rac1"
PRVF-5157 : could not verify ASM disk group "GRID" for voting disk location
"/dev/flashgrid/rac2.lun1" is available on node "rac1"
PRVF-5431 : Oracle Cluster Voting Disk configuration check failed


CVU operation performed:      Voting Disk
Date:                         Feb 11, 2021 6:18:51 PM
CVU home:                     /u01/app/19.3.0/grid/
User:                         grid
```

It can be seen that the command already had the verbose option which did not give any hint about the cause of the error.
The documentation [says](https://docs.oracle.com/en/database/oracle/oracle-database/19/cwadd/cluster-verification-utility-reference.html#GUID-405E2CE7-D8B0-4D72-8E53-741DB6A8E919) that CVU generates trace data by default unless it has been disabled.
The default trace file location is `$ORACLE_BASE/crsdata/<host_name>/cvu`.
A non-default location can be specified using the `CV_TRACELOC` environment variable.

That is what I got in the aforementioned directory:

```
[grid@rac1 ~]$ cd $ORACLE_BASE/crsdata/$(hostname -s)/cvu
[grid@rac1 cvu]$ ll
total 4
drwxrwxrwt 2 grid   oinstall 4096 Feb 11 14:01 cvulog
drwxrwxrwt 2 grid   oinstall  144 Feb 11 14:03 cvutrc
drwxr-xr-x 2 grid   oinstall   78 Feb 11 18:18 grid
drwxr-xr-x 2 grid   oinstall    6 Feb 11 14:03 init
drwxr-xr-x 2 oracle oinstall   28 Feb  2 20:48 oracle
[grid@rac1 cvu]$ cd grid
[grid@rac1 grid]$ ll
total 11272
-rw-r----- 1 grid oinstall   641638 Feb 11 18:18 cvuhelper.log.0
-rw-r--r-- 1 grid oinstall        0 Jan  4 12:12 cvuhelper.log.0.lck
-rw-r--r-- 1 grid oinstall 10899074 Feb 11 18:18 cvutrace.log.0
```

The `cvutrace.log.0` contained actual trace data in which the following lines drew my eye:

``` hl_lines="20 21 22"
[main] [ 2021-02-11 18:18:57.681 UTC ] [ClusterConfig.block:624]  block acquired semnum=0
[main] [ 2021-02-11 18:18:57.681 UTC ] [ClusterConfig.submit:573]  Out of block
[main] [ 2021-02-11 18:18:57.681 UTC ] [ClusterConfig.submit:590]  status=true
[main] [ 2021-02-11 18:18:57.681 UTC ] [ClusterConfig.destroy:468]  destroying resources for client thread Thread[main,5,main]
[main] [ 2021-02-11 18:18:57.681 UTC ] [ResultSet.traceResultTable:1065]

ResultTable Info ===>

        contents of resultTable

Dumping Result data.
  Status     : SUCCESSFUL
  Name       : rac1
  Type       : Node
  Has Results: No
  Exp. value : null
  Act. value : null

  Errors  :
    PRVG-2043 : Command "/u01/app/19.3.0/grid/bin/kfod op=GROUPS nohdr=true " failed on node "rac1" and produced the following output:
KFOD-00101: LRM error [110] while parsing command line arguments
KFOD-00103: LRM message: LRM-00118: syntax error at '=' at the end of input
```

As the above output demonstrates, CVU called `kfod` which was failing.
Thus, I decided to run it myself and got the same LRM errors:

```
[grid@rac1 ~]$ /u01/app/19.3.0/grid/bin/kfod op=GROUPS nohdr=true
KFOD-00101: LRM error [110] while parsing command line arguments
KFOD-00103: LRM message: LRM-00118: syntax error at '=' at the end of input
[grid@rac1 ~]$ /u01/app/19.3.0/grid/bin/kfod op=GROUPS
KFOD-00101: LRM error [110] while parsing command line arguments
KFOD-00103: LRM message: LRM-00118: syntax error at '=' at the end of input
```

LRM seems to be the parameter manager, but it did not ring a bell yet:

``` hl_lines="7"
[grid@rac1 ~]$ head -9 $ORACLE_HOME/oracore/mesg/lrmus.msg
/
/ $Header: lrmus.msg 19-jun-2003.17:48:08 Exp $
/
/ Copyright (c) 1996, 2003, Oracle.  All rights reserved.
/   NAME
/     lrmus.msg - CORE error message file for the parameter manager (LRM)
/   DESCRIPTION
/     Listing of all CORE error messages for LRM
/
```

`kfod` is just a shell script that invokes its binary counterpart `kfod.bin` similar to what many other Grid Infrastructure (GI) utilities do.
They obviously interact with the operating system, so that we can trace system calls being invoked.
That is what I did:

``` hl_lines="6"
[grid@rac1 ~]$ strace -f -e trace=open,write -s 256 /u01/app/19.3.0/grid/bin/kfod op=GROUPS
..
<skip>
..
open("/u01/app/19.3.0/grid/nls/data/lx40011.nlb", O_RDONLY) = 7
open("/u01/app/19.3.0/grid/dbs/init+ASM1.ora", O_RDONLY) = 7
open("/u01/app/19.3.0/grid/rdbms/mesg/kfodus.msb", O_RDONLY) = 7
write(1, "KFOD-00101: LRM error [110] while parsing command line arguments\n", 65KFOD-00101: LRM error [110] while parsing command line arguments
) = 65
..
```

In a nutshell, the process opened `/u01/app/19.3.0/grid/dbs/init+ASM1.ora`.
It then went to `/u01/app/19.3.0/grid/rdbms/mesg/kfodus.msb`, which is a binary message file.
After that it put the KFOD error to stdout.

Therefore, it made sense to check that parameter file:

``` hl_lines="2"
[grid@rac1 ~]$ cat /u01/app/19.3.0/grid/dbs/init+ASM1.ora
SPFILE=
```

It became obvious that the parameter file is the main culprit of these LRM errors:

```
KFOD-00101: LRM error [110] while parsing command line arguments
KFOD-00103: LRM message: LRM-00118: syntax error at '=' at the end of input
```

To confirm that, I renamed the file and reran both `kfod` and `cluvfy` commands successfully:

``` hl_lines="8 10 12"
[grid@rac1 ~]$ mv /u01/app/19.3.0/grid/dbs/init+ASM1.ora{,.bak}
[grid@rac1 ~]$ /u01/app/19.3.0/grid/bin/kfod op=GROUPS
--------------------------------------------------------------------------------
Group          Size          Free Redundancy Name
================================================================================
   1:      10240 MB       3712 MB     NORMAL GRID
   3:      65536 MB       3712 MB     NORMAL DATA
[grid@rac1 ~]$ cluvfy comp vdisk -n rac1 -verbose

Verifying Voting Disk ...PASSED

Verification of Voting Disk was successful.

CVU operation performed:      Voting Disk
Date:                         Feb 11, 2021 6:50:38 PM
CVU home:                     /u01/app/19.3.0/grid/
User:                         grid
```

I still do not know why that parameter file was created, but it is a neat example of how Oracle tools can be debugged.
