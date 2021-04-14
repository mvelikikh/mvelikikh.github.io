---
categories:
  - Oracle
date:
  created: 2021-04-14T22:40:00
description: >-
  Patching an Oracle home failed with error undefined reference to __libc_csu_fini.
  It was due to a symbolic link to a wrong libc library.
  This post demonstrates the error and how the error was resolved.
tags:
  - OPatch
---

# Patching with OPatch Failed with Undefined Reference to \_\_libc\_csu\_fini \_\_libc\_csu\_init due to Wrong Libc Library

Patching an Oracle Home failed on one cluster node with the error `undefined reference to __libc_csu_fini`.

<!-- more -->

## Patching errors and wrong libc library

Here is the actual OPatch log:

``` hl_lines="3 5"
Patching component oracle.rdbms, 19.0.0.0.0...
Make failed to invoke "/usr/bin/make -f ins_rdbms.mk ioracle ORACLE_HOME=/u01/app/oracle/product/19.3.0/dbhome_1 OPATCH_SESSION=apply"....'/usr/lib64/crt1.o: In function `_start':
(.text+0x12): undefined reference to `__libc_csu_fini'
/usr/lib64/crt1.o: In function `_start':
(.text+0x19): undefined reference to `__libc_csu_init'
/u01/app/oracle/product/19.3.0/dbhome_1/lib//libserver19.a(kf.o): In function `kfNotify':
kf.c:(.text+0x26f): undefined reference to `atexit'
/u01/app/oracle/product/19.3.0/dbhome_1/lib//libserver19.a(jskm.o): In function `jskmCheckIMJobBCast':
jskm.c:(.text+0x202d): undefined reference to `stat'
jskm.c:(.text+0x2066): undefined reference to `stat'
/u01/app/oracle/product/19.3.0/dbhome_1/lib//libserver19.a(qmsqx.o): In function `qmsqxFetchPos':
qmsqx.c:(text.unlikely+0x1048f): undefined reference to `stat'
/u01/app/oracle/product/19.3.0/dbhome_1/lib//libcore19.a(slzgetevar.o): In function `slzgetevarf_insert_keyval':
slzgetevar.c:(text.unlikely+0x40e): undefined reference to `atexit'
/u01/app/oracle/product/19.3.0/dbhome_1/lib//libgeneric19.a(skgfqsbt.o): In function `xsbtinit':
skgfqsbt.c:(text.unlikely+0x88): undefined reference to `atexit'
/u01/app/oracle/product/19.3.0/dbhome_1/lib//libjavavm19.a(eobtl.o): In function `eobti_create_sym_tmp_file':
eobtl.c:(.text+0x106): undefined reference to `fstat'
/u01/app/oracle/product/19.3.0/dbhome_1/lib//libjavavm19.a(eobtl.o): In function `eobti_digest_symbol_file':
eobtl.c:(.text+0x1b8): undefined reference to `fstat'
/u01/app/oracle/product/19.3.0/dbhome_1/lib//libjavavm19.a(eobtl.o): In function `eobti_build_lookup_tables':
eobtl.c:(.text+0x24ae): undefined reference to `fstat'
eobtl.c:(.text+0x264f): undefined reference to `fstat'
/u01/app/oracle/product/19.3.0/dbhome_1/lib//libnnzst19.a(ext_ztrsaadapter.o): In function `ztcaProcCtx_New':
ztrsaadapter.c:(.text+0xb95): undefined reference to `atexit'
/u01/app/oracle/product/19.3.0/dbhome_1/lib//libnnzst19.a(ccme_ck_rand_load_fileS1.o): In function `r_ck_random_load_file':
ck_rand_load_file.c:(.text+0xd4): undefined reference to `stat'
/u01/app/oracle/product/19.3.0/dbhome_1/rdbms/lib//libfthread19.a(fthread_task.o): In function `fthread_task_tab_init':
fthread_task.c:(text.unlikely+0x3df): undefined reference to `atexit'
make: *** [/u01/app/oracle/product/19.3.0/dbhome_1/rdbms/lib/oracle] Error 1
```

After a bit of searching, I found that the same errors were reported when a wrong libc library was picked up in a case which was not related to Oracle.
Sure enough, there was a symbolic link `$ORACLE_HOME/lib/libc.so` to `/lib64/libc.so.6`:

``` hl_lines="3"
[oracle@rac1 ~]$ find $ORACLE_HOME -name libc.so -ls
137463494    4 -rw-r--r--   1 oracle   oinstall       83 Apr 25  2014 /u01/app/oracle/product/19.3.0/dbhome_1/lib/stubs/libc.so
88704788    0 lrwxrwxrwx   1 oracle   oinstall       16 Apr 14 15:16 /u01/app/oracle/product/19.3.0/dbhome_1/lib/libc.so -> /lib64/libc.so.6
```

Having deleted the link, I was able to patch the Oracle Home successfully.

## Thoughts

My main suspect was `ldconfig` and the files in `/etc/ld.so.conf.d`.
For instance, Oracle Instant Client creates a file there with the `$ORACLE_HOME/lib` in it:

``` hl_lines="2"
[oracle@rac1 ~]$ cat /etc/ld.so.conf.d/oracle-instantclient.conf
/usr/lib/oracle/19.3/client64/lib
[oracle@rac1 ~]$ rpm -qf /etc/ld.so.conf.d/oracle-instantclient.conf
oracle-instantclient19.3-basic-19.3.0.0.0-1.x86_64
```

`ldconfig` is also called when `glibc` is installed:

```
# rpm -qp --scripts /tmp/glibc/glibc-2.17-323.0.1.el7_9.x86_64.rpm
preinstall scriptlet (using <lua>):
-- Check that the running kernel is new enough
required = '2.6.32'
rel = posix.uname("%r")
if rpm.vercmp(rel, required) < 0 then
  error("FATAL: kernel too old", 0)
end
postinstall program: /usr/sbin/glibc_post_upgrade.x86_64
postuninstall program: /sbin/ldconfig
```

Besides, Oracle also uses some libc stubs (`$ORACLE_HOME/lib/stubs/libc.so`), so could it be the case that some unsuccessful patch application left a symbolic link there?
Then, it could be the case that somebody followed an article from My Oracle Support that recommends adding `$ORACLE_HOME/lib` to `/etc/ld.so.conf.d`: [IF: External Jobs Failed With ORA-27301/ORA-27302 (Doc ID 2083336.1)](https://support.oracle.com/rs?type=doc&id=2083336.1).

It is still unclear what caused the issue in the problem scenario since there were no references to `$ORACLE_HOME/lib` in `/etc/ld.so.conf.d`.
For what is worth, next time I will be better prepared when I encounter a similar error.
