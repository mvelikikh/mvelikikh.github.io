---
categories:
  - Oracle
date:
  created: 2021-02-06T04:56:00
  updated: 2021-02-13T03:08:40
description: >-
  Demonstrate how to use Standard Edition High Availability cold failover in Enterprise Edition.
tags:
  - 19c
  - Clusterware
---

# Using SEHA Features in EE

Here is a short demonstration how to make use of the Standard Edition High Availability (SEHA) cold failover feature in Enterprise Edition (EE).

<!-- more -->

I installed a non-RAC Enterprise Edition 19.10 database home on my cluster.
Then I created a new database on ACFS:

```
[oracle@rac1 ~]$ srvctl config database -db si
Database unique name: si
Database name: si
Oracle home: /u01/app/oracle/product/19.3.0/dbhome_non_rac
Oracle user: oracle
Spfile: /acfsmounts/acfs1/SI/spfilesi.ora
Password file:
Domain:
Start options: open
Stop options: immediate
Database role: PRIMARY
Management policy: AUTOMATIC
Server pools:
Disk Groups:
Mount point paths: /acfsmounts/acfs1
Services:
Type: SINGLE
OSDBA group: dba
OSOPER group: oper
Database instance: si
Configured nodes: rac1
CSS critical: no
CPU count: 0
Memory target: 0
Maximum memory: 0
Default network number for database services:
Database is administrator managed
```

Let us assume I want to utilize some of [Standard Edition High Availability (SEHA) features](https://docs.oracle.com/en/database/oracle/oracle-database/19/admin/creating-and-configuring-an-oracle-database.html#GUID-4B255433-4F5D-4A75-BB05-EBAB41361B5E) in this database:

```
[oracle@rac1 ~]$ srvctl modify database -db si -node rac1,rac2
PRCD-1302 : failed to retrieve the node hosting this single-instance database
PRCD-2088 : failed to configure the single instance database si with multiple nodes because it is not a Standard Edition database

[oracle@rac1 ~]$ srvctl relocate database -db si -node rac2
PRKF-1421 : cannot relocate database "si"; invalid database type
```

As expected, `srvctl` disallows such operations.
However, the edition check uses the `$ORACLE_HOME/lib/libedtn19.a` file which I described in the following post: [Determining Oracle Database Edition](determining-oracle-database-edition.md).

It turns out it is enough to copy the standard edition library to make these `srvctl` commands work:

``` hl_lines="25"
[oracle@rac1 lib]$ cp libedtn19_std.a libedtn19.a

[oracle@rac1 ~]$ srvctl modify database -db si -node rac1,rac2

[oracle@rac1 ~]$ srvctl config database -db si
Database unique name: si
Database name: si
Oracle home: /u01/app/oracle/product/19.3.0/dbhome_non_rac
Oracle user: oracle
Spfile: /acfsmounts/acfs1/SI/spfilesi.ora
Password file:
Domain:
Start options: open
Stop options: immediate
Database role: PRIMARY
Management policy: AUTOMATIC
Server pools:
Disk Groups:
Mount point paths: /acfsmounts/acfs1
Services:
Type: SINGLE
OSDBA group: dba
OSOPER group: oper
Database instance: si
Configured nodes: rac1,rac2
CSS critical: no
CPU count: 0
Memory target: 0
Maximum memory: 0
Default network number for database services:
Database is administrator managed
```

My clusterware resources before doing the `srvctl relocate database` command:

``` hl_lines="68 69"
[grid@rac2 ~]$ crsctl stat res -t
--------------------------------------------------------------------------------
Name           Target  State        Server                   State details
--------------------------------------------------------------------------------
Local Resources
--------------------------------------------------------------------------------
ora.DATA.VOLUME1.advm
               ONLINE  ONLINE       rac1                     STABLE
               ONLINE  ONLINE       rac2                     STABLE
ora.LISTENER.lsnr
               ONLINE  ONLINE       rac1                     STABLE
               ONLINE  ONLINE       rac2                     STABLE
ora.chad
               ONLINE  ONLINE       rac1                     STABLE
               ONLINE  ONLINE       rac2                     STABLE
ora.data.volume1.acfs
               ONLINE  ONLINE       rac1                     mounted on /acfsmoun
                                                             ts/acfs1,STABLE
               ONLINE  ONLINE       rac2                     mounted on /acfsmoun
                                                             ts/acfs1,STABLE
ora.net1.network
               ONLINE  ONLINE       rac1                     STABLE
               ONLINE  ONLINE       rac2                     STABLE
ora.ons
               ONLINE  ONLINE       rac1                     STABLE
               ONLINE  ONLINE       rac2                     STABLE
ora.proxy_advm
               ONLINE  ONLINE       rac1                     STABLE
               ONLINE  ONLINE       rac2                     STABLE
--------------------------------------------------------------------------------
Cluster Resources
--------------------------------------------------------------------------------
ora.ASMNET1LSNR_ASM.lsnr(ora.asmgroup)
      1        ONLINE  ONLINE       rac1                     STABLE
      2        ONLINE  ONLINE       rac2                     STABLE
ora.DATA.dg(ora.asmgroup)
      1        ONLINE  ONLINE       rac1                     STABLE
      2        ONLINE  ONLINE       rac2                     STABLE
ora.GRID.dg(ora.asmgroup)
      1        ONLINE  ONLINE       rac1                     STABLE
      2        ONLINE  ONLINE       rac2                     STABLE
ora.LISTENER_SCAN1.lsnr
      1        ONLINE  ONLINE       rac2                     STABLE
ora.LISTENER_SCAN2.lsnr
      1        ONLINE  ONLINE       rac1                     STABLE
ora.LISTENER_SCAN3.lsnr
      1        ONLINE  ONLINE       rac1                     STABLE
ora.asm(ora.asmgroup)
      1        ONLINE  ONLINE       rac1                     Started,STABLE
      2        ONLINE  ONLINE       rac2                     Started,STABLE
ora.asmnet1.asmnetwork(ora.asmgroup)
      1        ONLINE  ONLINE       rac1                     STABLE
      2        ONLINE  ONLINE       rac2                     STABLE
ora.cvu
      1        ONLINE  ONLINE       rac1                     STABLE
ora.qosmserver
      1        ONLINE  ONLINE       rac1                     STABLE
ora.rac1.vip
      1        ONLINE  ONLINE       rac1                     STABLE
ora.rac2.vip
      1        ONLINE  ONLINE       rac2                     STABLE
ora.scan1.vip
      1        ONLINE  ONLINE       rac2                     STABLE
ora.scan2.vip
      1        ONLINE  ONLINE       rac1                     STABLE
ora.scan3.vip
      1        ONLINE  ONLINE       rac1                     STABLE
ora.si.db
      1        ONLINE  ONLINE       rac1                     Open,HOME=/u01/app/o
                                                             racle/product/19.3.0
                                                             /dbhome_non_rac,STAB
                                                             LE
--------------------------------------------------------------------------------
```

Running `srvctl relocate database`:

``` hl_lines="3"
[oracle@rac1 ~]$ srvctl relocate database -db si -node rac2
[oracle@rac1 ~]$ srvctl status database -db si
Instance si is running on node rac2
```

Clusterware also restarts that database on a working node in case the node it was running on fails.
To test that, I initiated a kernel panic on the `rac1` node where my database was running:

```
[root@rac1 ~]# echo c > /proc/sysrq-trigger
```

After a while, the database was started on the other node:

``` hl_lines="60 61"
[grid@rac2 ~]$ crsctl stat res -t
--------------------------------------------------------------------------------
Name           Target  State        Server                   State details
--------------------------------------------------------------------------------
Local Resources
--------------------------------------------------------------------------------
ora.DATA.VOLUME1.advm
               ONLINE  ONLINE       rac2                     STABLE
ora.LISTENER.lsnr
               ONLINE  ONLINE       rac2                     STABLE
ora.chad
               ONLINE  ONLINE       rac2                     STABLE
ora.data.volume1.acfs
               ONLINE  ONLINE       rac2                     mounted on /acfsmoun
                                                             ts/acfs1,STABLE
ora.net1.network
               ONLINE  ONLINE       rac2                     STABLE
ora.ons
               ONLINE  ONLINE       rac2                     STABLE
ora.proxy_advm
               ONLINE  ONLINE       rac2                     STABLE
--------------------------------------------------------------------------------
Cluster Resources
--------------------------------------------------------------------------------
ora.ASMNET1LSNR_ASM.lsnr(ora.asmgroup)
      1        ONLINE  OFFLINE                               STABLE
      2        ONLINE  ONLINE       rac2                     STABLE
ora.DATA.dg(ora.asmgroup)
      1        ONLINE  OFFLINE                               STABLE
      2        ONLINE  ONLINE       rac2                     STABLE
ora.GRID.dg(ora.asmgroup)
      1        ONLINE  OFFLINE                               STABLE
      2        ONLINE  ONLINE       rac2                     STABLE
ora.LISTENER_SCAN1.lsnr
      1        ONLINE  ONLINE       rac2                     STABLE
ora.LISTENER_SCAN2.lsnr
      1        ONLINE  ONLINE       rac2                     STABLE
ora.LISTENER_SCAN3.lsnr
      1        ONLINE  ONLINE       rac2                     STABLE
ora.asm(ora.asmgroup)
      1        ONLINE  OFFLINE                               STABLE
      2        ONLINE  ONLINE       rac2                     Started,STABLE
ora.asmnet1.asmnetwork(ora.asmgroup)
      1        ONLINE  OFFLINE                               STABLE
      2        ONLINE  ONLINE       rac2                     STABLE
ora.cvu
      1        ONLINE  ONLINE       rac2                     STABLE
ora.qosmserver
      1        ONLINE  ONLINE       rac2                     STABLE
ora.rac1.vip
      1        ONLINE  INTERMEDIATE rac2                     FAILED OVER,STABLE
ora.rac2.vip
      1        ONLINE  ONLINE       rac2                     STABLE
ora.scan1.vip
      1        ONLINE  ONLINE       rac2                     STABLE
ora.scan2.vip
      1        ONLINE  ONLINE       rac2                     STABLE
ora.scan3.vip
      1        ONLINE  ONLINE       rac2                     STABLE
ora.si.db
      1        ONLINE  ONLINE       rac2                     Open,HOME=/u01/app/o
                                                             racle/product/19.3.0
                                                             /dbhome_non_rac,STAB
                                                             LE
--------------------------------------------------------------------------------
```

I am unsure about the exact repercussions of that library change.
Obviously `srvctl` uses `libedtn19.a` as it was demonstrated above.
Whether or not it can cause any adverse effects - I do not know.

Evidently such configuration is anything but supported by Oracle.
The officially supported way of making EE cold failover configuration on non-RAC environments uses custom Clusterware resources, which I personally find clunky.
I wish those SEHA features were available on EE, but it is not the case at present.
