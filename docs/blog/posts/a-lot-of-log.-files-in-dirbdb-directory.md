---
categories:
  - Oracle
date:
  created: 2016-11-29T12:52:00
description: >-
  Found a lot of log.* files in the dirbdb directory of an Oracle GoldenGate home after ENABLEMONITORING was set.
  Turns out those are Berkeley Database related files.
  Creating a DB_CONFIG file with DB_LOG_AUTOREMOVE options enables automatic removal of those files.
tags:
  - GoldenGate
---

# A lot of `log.*` files in dirbdb directory

After adding `ENABLEMONITORING` in the `GLOBALS` file, I noticed that the `$OGG_HOME/dirbdb` directory started growing.

<!-- more -->

That was OGG version 12.2.0.1.160517.
The size of this directory was 23G in the test environment, and the `ENABLEMONITORING` option was set 3 weeks ago:

```bash
-bash-4.1$ du -sh dirbdb
 23.8G   dirbdb
```

Out of that 23.8G, 23.5G was occupied by the `log.*` files like below:

```
-rw-r-----   1 oracle dba      10485760 Nov 16 18:16 log.0000015971
-rw-r-----   1 oracle dba      10485760 Nov 16 18:28 log.0000015972
-rw-r-----   1 oracle dba      10485760 Nov 16 18:41 log.0000015973
-rw-r-----   1 oracle dba      10485760 Nov 16 18:55 log.0000015974
-rw-r-----   1 oracle dba      10485760 Nov 16 19:08 log.0000015975
-rw-r-----   1 oracle dba      10485760 Nov 16 19:20 log.0000015976
-rw-r-----   1 oracle dba      10485760 Nov 16 19:32 log.0000015977
-rw-r-----   1 oracle dba      10485760 Nov 16 19:43 log.0000015978
-rw-r-----   1 oracle dba      10485760 Nov 16 19:55 log.0000015979
-rw-r-----   1 oracle dba      10485760 Nov 16 20:07 log.0000015980
-rw-r-----   1 oracle dba      10485760 Nov 16 20:19 log.0000015981
-rw-r-----   1 oracle dba      10485760 Nov 16 20:31 log.0000015982
```

These files were generated approximately every ten minutes, and each of them was 10M in size that made up 1.4G daily.
Having searched through MOS and Internet search engines, I stumbled across this [MOSC Thread: Monitoring - Berkeley Database](https://community.oracle.com/message/11857042#11857042).

So I created a new `DB_CONFIG` file within the `dirbdb` directory, and added the following line to it:

```bash
-bash-4.1$ cat dirbdb/DB_CONFIG
set_flags DB_LOG_AUTOREMOVE
```

Then I restarted my OGG processes and discovered that these log files were gone.

Now there are only at most two log files that are kept:

```bash
[oracle@host ggs]$ ls -ltr dirbdb/log*
-rw-r-----   1 oracle   dba      10485760 Nov 28 13:31 dirbdb/log.0000017532
-rw-r-----   1 oracle   dba      10485760 Nov 28 13:41 dirbdb/log.0000017533
[oracle@host ggs]$ ls -ltr dirbdb/log*
-rw-r-----   1 oracle   dba      10485760 Nov 28 13:42 dirbdb/log.0000017533
-rw-r-----   1 oracle   dba      10485760 Nov 28 13:51 dirbdb/log.0000017534
[oracle@host ggs]$ ls -ltr dirbdb/log*
-rw-r-----   1 oracle   dba      10485760 Nov 29 07:21 dirbdb/log.0000017625
-rw-r-----   1 oracle   dba      10485760 Nov 29 07:22 dirbdb/log.0000017626
```

Looks like another option that should be added in environments in which `ENABLEMONITORING` is set.
Regretfully, MOS returns no hits apart from the aforementioned MOSC thread.
