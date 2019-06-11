---
categories:
  - Oracle
date:
  created: 2019-06-11T03:00:00
description: >-
  While doing backup incremental level 1 for recover of image copies in RMAN, it is possible to specify the location of new image copies using the DATAFILECOPY FORMAT clause.
  Another way to achieve the same is to specify the format while allocating channels.
tags:
  - RMAN
---

# A case for DATAFILECOPY FORMAT

I was migrating several databases from AWS EC2 non-Nitro based instances to [Nitro-based](https://docs.aws.amazon.com/en_us/AWSEC2/latest/UserGuide/instance-types.html#ec2-nitro-instances) ones when I came across one issue with Oracle Recovery Manager (RMAN).
This blog post is about it.

<!-- more -->

The high-level process of the migration was as follows:

1. Attach a new ASM disk group to the host that is to be migrated
1. Make an initial level 0 copy of the database
1. Roll forward the copy as many times as needed using an incremental level 1 backup
1. When it is time to switch to the new server, roll forward the copy once again, switch logfile, backup all archive logs covering the last backup, dismount the ASM disk group, mount it on the new server, and open the database (there are also controlfile and spfile copies as well as some extra steps specific to that environment)

I would rather use a physical standby or GoldenGate than that meticulously designed process I developed, albeit those alternatives were ruled out since they would require additional licenses.
At the end of the day, the final downtime was less than 30 minutes as almost everything was automated using Ansible.

I ran that procedure several times in non-Production instances without any issues, however, I got a missing file when I performed the same steps in the Production instance.
Here is how that happened.

The disk group configuration is the following:

- `DATA`: `db_create_file_dest`
- `FRA`: `db_recovery_file_dest`
- `MIGR`: the transient ASM disk group to keep image copies

Let us setup a test tablespace:

```sql
SQL> create tablespace test_ts;

Tablespace created.
```

Make a copy of it:

```
RMAN> backup as copy incremental level 0 format '+MIGR' tablespace pdb:test_ts tag migr;

Starting backup at 10.06.2019 21:14:51
using channel ORA_DISK_1
channel ORA_DISK_1: starting datafile copy
input datafile file number=00016 name=+DATA/ORCL/8AAFC31944116B0CE0554A7F9DE2B2FD/DATAFILE/test_ts.276.1010610875
output file name=+MIGR/ORCL/8AAFC31944116B0CE0554A7F9DE2B2FD/DATAFILE/test_ts.256.1010610893 tag=MIGR RECID=6 STAMP=1010610895
channel ORA_DISK_1: datafile copy complete, elapsed time: 00:00:07
Finished backup at 10.06.2019 21:14:59
```

Then add a datafile to that tablespace:

```sql
SQL> alter tablespace test_ts add datafile;

Tablespace altered.
```

The final backup/recover block:

``` hl_lines="8 18"
RMAN> run {
  backup incremental level 1 format '+MIGR' for recover of copy with tag migr tablespace pdb:test_ts;
  recover copy of tablespace pdb:test_ts with tag migr;
}2> 3> 4>

Starting backup at 10.06.2019 21:16:42
using channel ORA_DISK_1
no parent backup or copy of datafile 17 found
channel ORA_DISK_1: starting incremental level 1 datafile backup set
channel ORA_DISK_1: specifying datafile(s) in backup set
input datafile file number=00016 name=+DATA/ORCL/8AAFC31944116B0CE0554A7F9DE2B2FD/DATAFILE/test_ts.276.1010610875
channel ORA_DISK_1: starting piece 1 at 10.06.2019 21:16:42
channel ORA_DISK_1: finished piece 1 at 10.06.2019 21:16:43
piece handle=+MIGR/ORCL/8AAFC31944116B0CE0554A7F9DE2B2FD/BACKUPSET/2019_06_10/nnndn1_migr_0.258.1010611003 tag=MIGR comment=NONE
channel ORA_DISK_1: backup set complete, elapsed time: 00:00:01
channel ORA_DISK_1: starting datafile copy
input datafile file number=00017 name=+DATA/ORCL/8AAFC31944116B0CE0554A7F9DE2B2FD/DATAFILE/test_ts.277.1010610945
output file name=+FRA/ORCL/8AAFC31944116B0CE0554A7F9DE2B2FD/DATAFILE/test_ts.265.1010611003 tag=MIGR RECID=7 STAMP=1010611006
channel ORA_DISK_1: datafile copy complete, elapsed time: 00:00:03
Finished backup at 10.06.2019 21:16:46
```

Despite the fact that the format was set to `+MIGR`, the copy of the new added datafile was put to the `FRA` disk group:

``` hl_lines="16"
RMAN> list copy tag migr;

specification does not match any control file copy in the repository
specification does not match any archived log in the repository
List of Datafile Copies
=======================

Key     File S Completion Time     Ckp SCN    Ckp Time            Sparse
------- ---- - ------------------- ---------- ------------------- ------
8       16   A 10.06.2019 21:16:47 1468031    10.06.2019 21:16:42 NO
        Name: +MIGR/ORCL/8AAFC31944116B0CE0554A7F9DE2B2FD/DATAFILE/test_ts.256.1010610893
        Tag: MIGR
        Container ID: 3, PDB Name: PDB

7       17   A 10.06.2019 21:16:46 1468032    10.06.2019 21:16:43 NO
        Name: +FRA/ORCL/8AAFC31944116B0CE0554A7F9DE2B2FD/DATAFILE/test_ts.265.1010611003
        Tag: MIGR
        Container ID: 3, PDB Name: PDB
```

That is pretty much the same issue that I encountered while doing a test migration of that multi-terabyte database in the Production system - a few datafiles have been added between the initial level 0 and the subsequent level 1 copies.
It is the case when the [DATAFILECOPY FORMAT](https://docs.oracle.com/en/database/oracle/oracle-database/19/rcmrf/BACKUP.html#GUID-73642FF2-43C5-48B2-9969-99001C52EB50) clause can be used:

``` hl_lines="4 11 21"
RMAN> run {
  backup incremental level 1
    format '+MIGR' for recover of copy with tag migr
    datafilecopy format '+MIGR'
    tablespace pdb:test_ts;
  recover copy of tablespace pdb:test_ts with tag migr;
}2> 3> 4>

Starting backup at 10.06.2019 21:21:57
using channel ORA_DISK_1
no parent backup or copy of datafile 19 found
channel ORA_DISK_1: starting incremental level 1 datafile backup set
channel ORA_DISK_1: specifying datafile(s) in backup set
input datafile file number=00018 name=+DATA/ORCL/8AAFC31944116B0CE0554A7F9DE2B2FD/DATAFILE/test_ts.277.1010611243
channel ORA_DISK_1: starting piece 1 at 10.06.2019 21:21:57
channel ORA_DISK_1: finished piece 1 at 10.06.2019 21:21:58
piece handle=+MIGR/ORCL/8AAFC31944116B0CE0554A7F9DE2B2FD/BACKUPSET/2019_06_10/nnndn1_migr_0.259.1010611317 tag=MIGR comment=NONE
channel ORA_DISK_1: backup set complete, elapsed time: 00:00:01
channel ORA_DISK_1: starting datafile copy
input datafile file number=00019 name=+DATA/ORCL/8AAFC31944116B0CE0554A7F9DE2B2FD/DATAFILE/test_ts.276.1010611299
output file name=+MIGR/ORCL/8AAFC31944116B0CE0554A7F9DE2B2FD/DATAFILE/test_ts.260.1010611319 tag=MIGR RECID=10 STAMP=1010611321
channel ORA_DISK_1: datafile copy complete, elapsed time: 00:00:03
Finished backup at 10.06.2019 21:22:01
```

That is just another flexibility that Oracle provides.
If you think about it, it makes complete sense - image copies and backupsets can be stored separately.

Another way to specify location for image copies in that case is an explicit channel configuration:

``` hl_lines="3 13 23 31"
RMAN> run {
  # allocate as many channels as needed
  allocate channel c1 device type disk format '+MIGR';
  backup incremental level 1 for recover of copy with tag migr tablespace pdb:test_ts;
  recover copy of tablespace pdb:test_ts with tag migr;
}2> 3> 4> 5>

released channel: ORA_DISK_1
allocated channel: c1
channel c1: SID=94 device type=DISK

Starting backup at 10.06.2019 21:33:43
no parent backup or copy of datafile 21 found
channel c1: starting incremental level 1 datafile backup set
channel c1: specifying datafile(s) in backup set
input datafile file number=00020 name=+DATA/ORCL/8AAFC31944116B0CE0554A7F9DE2B2FD/DATAFILE/test_ts.276.1010611951
channel c1: starting piece 1 at 10.06.2019 21:33:44
channel c1: finished piece 1 at 10.06.2019 21:33:45
piece handle=+MIGR/ORCL/8AAFC31944116B0CE0554A7F9DE2B2FD/BACKUPSET/2019_06_10/nnndn1_migr_0.256.1010612025 tag=MIGR comment=NONE
channel c1: backup set complete, elapsed time: 00:00:01
channel c1: starting datafile copy
input datafile file number=00021 name=+DATA/ORCL/8AAFC31944116B0CE0554A7F9DE2B2FD/DATAFILE/test_ts.277.1010612011
output file name=+MIGR/ORCL/8AAFC31944116B0CE0554A7F9DE2B2FD/DATAFILE/test_ts.261.1010612025 tag=MIGR RECID=13 STAMP=1010612028
channel c1: datafile copy complete, elapsed time: 00:00:03
Finished backup at 10.06.2019 21:33:48
```
