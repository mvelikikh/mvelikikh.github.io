---
categories:
  - Oracle
date:
  created: 2020-09-30T19:51:00
description: >-
  Explain how to determine Oracle Database edition using the libedtn19.a library and OS commands.
tags:
  - 18c
  - 19c
  - OS
---

# Determining Oracle Database Edition

The other day I debugged some Oracle provided utilities and came across another way of determining an Oracle Database edition.
It does not require a running database instance.

<!-- more -->

The Oracle code was checking what is inside the `$ORACLE_HOME/lib/libedtn19.a` library:

```bash
# Enterprise Edition
[oracle@rac1 lib]$ ar t /u01/app/oracle/product/19.3.0/dbhome_1/lib/libedtn19.a
vsnfent.o

# Standard Edition
[oracle@rac1 lib]$ ar t /u01/app/oracle/product/19.3.0/dbhome_2/lib/libedtn19.a
vsnfstd.o
```

As it can be seen, it is 'vsnf**std**.o' for Standard vs 'vsnf**ent**.o' for Enterprise.
It appears to be a file for each edition and the file `libedtn19.a` contains the edition of that specific Oracle Home:

```bash
[oracle@rac1 lib]$ find . -name 'libedtn19*a' -print -exec ar t '{}' \;
./libedtn19_xp.a
vsnfxp.o
./libedtn19_ent.a
vsnfent.o
./libedtn19_cse.a
vsnfcse.o
./libedtn19_cee.a
vsnfcee.o
./libedtn19.a
vsnfent.o
./libedtn19_hp.a
vsnfhp.o
./libedtn19_std.a
vsnfstd.o
```

It has no effect on `V$VERSION` output whatsoever, and it obviously cannot be used to change one edition to another.
Yet I discovered that SRVCTL checks that `libedtn19.a` file in certain scenarios to determine whether or not some edition specific features should be allowed.
Per my research, that library was introduced in Oracle 18c.
