---
categories:
  - Linux
date:
  created: 2021-09-22T01:10:00
description: >-
  There were periodic blk_update_request I/O error on dev df0 sector 0 on one of the Linux servers.
  I used Linux Audit to troubleshoot the issue.
  It turns out the issue was caused by a job calling fdisk -l.
tags:
  - OS
---

# Finding cause of kernel: blk\_update\_request: I/O error, dev fd0, sector 0

There was a Linux server that got periodic `kernel: blk_update_request: I/O error, dev fd0, sector 0` errors in `/var/log/messages`.
This post demonstrates how I troubleshooted the issue.

<!-- more -->

```
Sep 21 11:38:29 localhost kernel: blk_update_request: I/O error, dev fd0, sector 0
```

There were no cron jobs or systemd timers that can cause these errors, so that I had to resort to other tools.
In this specific example, I decided to use the Linux Audit system:

```
[root@floppy ~]# auditctl -a exit,always -S open -F path=/dev/fd0 -k floppy
WARNING - 32/64 bit syscall mismatch, you should specify an arch
```

After I got new `blk_update_request` errors, I obtained the audit logs (formatted for readability):

``` hl_lines="12 23"
[root@floppy ~]# ausearch -k floppy
----
time->Tue Sep 21 11:43:04 2021
type=CONFIG_CHANGE msg=audit(1632224584.979:146): auid=1000 ses=1 op=add_rule key="floppy" list=4 res=1
----
time->Tue Sep 21 11:43:17 2021
type=PROCTITLE msg=audit(1632224597.188:147): proctitle=666469736B002D6C002F6465762F666430
type=PATH msg=audit(1632224597.188:147): item=0 name="/dev/fd0" inode=8972 dev=00:05 mode=060660 ouid=0 ogid=6 rdev=02:00 objtype=NORMAL cap_fp=0000000000000000 cap_fi=0000000000000000 cap_fe=0 cap_fver=0
type=CWD msg=audit(1632224597.188:147):  cwd="/root"
type=SYSCALL msg=audit(1632224597.188:147): arch=c000003e syscall=2 success=no exit=-6 a0=7ffcd4c7290a a1=80000 a2=1 a3=7ffcd4c70e20 items=1
                                            ppid=1767 pid=2060 auid=1000 uid=0 gid=0 euid=0 suid=0 fsuid=0 egid=0 sgid=0 fsgid=0 tty=pts0 ses=1
                                            comm="fdisk" exe="/usr/sbin/fdisk" key="floppy"
.. after a while ..
[root@floppy ~]# ausearch -k floppy
...
----
time->Tue Sep 21 11:43:31 2021
type=PROCTITLE msg=audit(1632224611.123:148): proctitle=666469736B002D6C002F6465762F666430
type=PATH msg=audit(1632224611.123:148): item=0 name="/dev/fd0" inode=8972 dev=00:05 mode=060660 ouid=0 ogid=6 rdev=02:00 objtype=NORMAL cap_fp=0000000000000000 cap_fi=0000000000000000 cap_fe=0 cap_fver=0
type=CWD msg=audit(1632224611.123:148):  cwd="/root"
type=SYSCALL msg=audit(1632224611.123:148): arch=c000003e syscall=2 success=no exit=-6 a0=7fff65dd690a a1=80000 a2=1 a3=7fff65dd4220 items=1
                                            ppid=1767 pid=2073 auid=1000 uid=0 gid=0 euid=0 suid=0 fsuid=0 egid=0 sgid=0 fsgid=0 tty=pts0 ses=1
                                            comm="fdisk" exe="/usr/sbin/fdisk" key="floppy"
```

As it is seen from the executable, it was `fdisk`.
More specifically, `fdisk -l` can cause such errors on Azure Generation 1 VMs.
