---
categories:
  - Oracle
date:
  created: 2020-07-11T23:40:00
description: >-
  An ORA-00600 [kglobpg_is_pkp] error was encountered while I was applying Database Release Update 19.7 in the rolling mode.
  I was unable to start one of the database instances after that.
  I had to apply patch Patch 31359215 to be able to start the instance successfully and continue the patching.
tags:
  - 19c
  - OERR
  - OPatch
  - RAC
---

# ORA-600 [kglobpg\_is\_pkp] During Rolling RU 19.7 Apply

I came across this error while applying Database Release Update 19.7 to my RAC database.

<!-- more -->

That was the old `ORACLE_HOME`:

```
[oracle@rac1 dbhome_1]$ OPatch/opatch lspatches
30128191;OJVM RELEASE UPDATE: 19.5.0.0.191015 (30128191)
30122149;OCW RELEASE UPDATE 19.5.0.0.0 (30122149)
30125133;Database Release Update : 19.5.0.0.191015 (30125133)

OPatch succeeded.
```

That was the new one:

```
[oracle@rac1 dbhome_3]$ OPatch/opatch lspatches
30805684;OJVM RELEASE UPDATE: 19.7.0.0.200414 (30805684)
30894985;OCW RELEASE UPDATE 19.7.0.0.0 (30894985)
30869156;Database Release Update : 19.7.0.0.200414 (30869156)

OPatch succeeded.
```

There were two nodes in the cluster: rac1 and rac2.

I set the new `ORACLE_HOME` for the database and restarted rac2:

``` hl_lines="18 20 22 24"
Patch Id: 30805684
Patch Description: OJVM RELEASE UPDATE: 19.7.0.0.200414 (30805684)
Patch Apply Time: 2020-07-09T19:38:43Z
Bugs Fixed: 29254623,29445548,29512125,29540327,29774362,29942275,30134746,
30160625,30534662,30855101
===========================================================
2020-07-11T15:39:33.323415+00:00
Resize operation completed for file# 1, old size 993280K, new size 1003520K
Resize operation completed for file# 1, old size 1003520K, new size 1013760K
2020-07-11T15:39:35.107445+00:00
Resize operation completed for file# 1, old size 1013760K, new size 1024000K
Resize operation completed for file# 1, old size 1024000K, new size 1034240K
2020-07-11T15:39:37.061108+00:00
Resize operation completed for file# 1, old size 1034240K, new size 1044480K
Resize operation completed for file# 1, old size 1044480K, new size 1054720K
2020-07-11T15:39:38.695595+00:00
Resize operation completed for file# 1, old size 1054720K, new size 1064960K
jox_pujs ending in pid 23121 cid 1
2020-07-11T15:39:39.024323+00:00
Java patching prepare phase started.
2020-07-11T15:39:39.068031+00:00
## jox_ujs_status: op_instance_patched: returning TRUE in pid 22749
2020-07-11T15:39:44.069088+00:00
## jox_ujs_status: op_instance_patched: returning TRUE in pid 22749
```

pid 22749 was GEN0 and it was writing that `jox_ujs_status` message to the alert log every 5 seconds.

That was what I had on rac1:

``` hl_lines="15 17 19"
2020-07-11T15:38:52.976980+00:00
Increasing priority of 1 RS
Domain Action Reconfiguration started (domid 3, new da inc 6, cluster inc 8)
Instance 2 is attaching to domain 3
 Global Resource Directory partially frozen for domain action
 Non-local Process blocks cleaned out
 Set master node info
 Dwn-cvts replayed, VALBLKs dubious
 All grantable enqueues granted
Domain Action Reconfiguration complete (total time 0.1 secs)
Decreasing priority of 1 RS
2020-07-11T15:39:39.024882+00:00
Java patching prepare phase started.
2020-07-11T15:39:39.049868+00:00
## jox_ujs_status: op_instance_patched: UJS active in root, ujs state present, its version does not match executable version, returning FALSE in pid 31373
2020-07-11T15:39:44.069761+00:00
## jox_ujs_status: op_instance_patched: UJS active in root, ujs state present, its version does not match executable version, returning FALSE in pid 31373
2020-07-11T15:39:49.071807+00:00
## jox_ujs_status: op_instance_patched: UJS active in root, ujs state present, its version does not match executable version, returning FALSE in pid 31373
```

Although it looked suspicious, I decided to continue the patching.
Once I stopped rac1, I was not able to start it anymore:

``` hl_lines="14 24 35"
2020-07-11T15:42:40.981054+00:00
## jox_ujs_status: op_instance_patched: returning TRUE in pid 4744
Starting background process GTX0
2020-07-11T15:42:41.422960+00:00
GTX0 started with pid=63, OS id=4926
2020-07-11T15:42:41.427547+00:00
joxcsys_required_dirobj_exists: directory object exists with required path /u01/app/oracle/product/19.3.0/dbhome_3/javavm/admin/, pid 4844 cid 1
Starting background process RCBG
2020-07-11T15:42:41.492063+00:00
RCBG started with pid=64, OS id=4928
replication_dependency_tracking turned off (no async multimaster replication found)
2020-07-11T15:42:41.831459+00:00
Errors in file /u01/app/oracle/diag/rdbms/racdb/racdb1/trace/racdb1_ora_4844.trc  (incident=5249) (PDBNAME=CDB$ROOT):
ORA-00600: internal error code, arguments: [kglobpg_is_pkp], [0x077DD9BC8], [], [], [], [], [], [], [], [], [], []
Incident details in: /u01/app/oracle/diag/rdbms/racdb/racdb1/incident/incdir_5249/racdb1_ora_4844_i5249.trc
Use ADRCI or Support Workbench to package the incident.
See Note 411.1 at My Oracle Support for error and packaging details.
..
2020-07-11T15:42:42.782978+00:00
## jox_ujs_status: op_instance_patched: returning TRUE in pid 4744
Errors in file /u01/app/oracle/diag/rdbms/racdb/racdb1/trace/racdb1_ora_4844.trc  (incident=5250) (PDBNAME=CDB$ROOT):
ORA-00603: ORACLE server session terminated by fatal error
ORA-01092: ORACLE instance terminated. Disconnection forced
ORA-00600: internal error code, arguments: [kglobpg_is_pkp], [0x077DD9BC8], [], [], [], [], [], [], [], [], [], []
Incident details in: /u01/app/oracle/diag/rdbms/racdb/racdb1/incident/incdir_5250/racdb1_ora_4844_i5250.trc
2020-07-11T15:42:42.941948+00:00
Dumping diagnostic data in directory=[cdmp_20200711154242], requested by (instance=1, osid=4844), summary=[incident=5249].
2020-07-11T15:42:43.784890+00:00
## jox_ujs_status: op_instance_patched: returning TRUE in pid 4744
2020-07-11T15:42:43.960028+00:00
opiodr aborting process unknown ospid (4844) as a result of ORA-603
2020-07-11T15:42:43.976310+00:00
ORA-603 : opitsk aborting process
License high water mark = 1
USER(prelim) (ospid: 4844): terminating the instance due to ORA error 600
```

That essentially left me with rac2 whose GEN0 was spamming the following message to the alert log once in 5 seconds:

```
## jox_ujs_status: op_instance_patched: returning TRUE in pid 22749
```

Any attempts to run datapatch and finish the patching ended up with the following errors:

```
ORA-29548: Java system class reported: UJS still running
ORA-06512: at "SYS.DBMS_JAVA_TEST", line 2
ORA-06512: at "SYS.DBMS_JAVA_TEST", line 55
ORA-06512: at line 4
```

There were some `ORA-00600 [kglobpg_is_pkp]` errors on My Oracle Support (MOS) but there was nothing specific that I could link to my issue.
When I get no hits, I usually turn PowerView off or extend my search to include bugs, patches, etc.
That worked out well and I found the following patch: [Patch 31359215: INSTANCE STARTUP FAILS ORA-600 [KGLOBPG\_IS\_PKP] DURING ROLLING RU 19.7 APPLY](https://support.oracle.com/rs?type=patch&id=31359215)
I applied that patch to rac1 and was finally able to start that instance successfully.

The remaining part of that rolling patch exercise went without a hitch.
The patch itself was released on 7th July.
I hope Oracle Support will update the Knowledge Base, or publish some alerts about this issue, or even merge that patch into 19.7 OJVM.
