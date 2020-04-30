---
categories:
  - Oracle
date:
  created: 2020-04-30T23:00:00
description: >-
  Invoking external programs from the Oracle Database using a Java class uses the database OS user account by default.
  To secure the invocation, it is possible to configure a separate low-privileged OS account.
  However, when Grid Infrastructure runs under a different OS account, such an invocation fails.
  A workaround is to change the group of the jssu binary to be OSASM rather than oinstall as this post demonstrates.
tags:
  - 19c
  - OS
---

# Secure Use of Runtime.exec Functionality in Oracle Database

Developers wanted to call external programs from the database using a Java class.
By default, those commands are run under the database user account which is anything but secure.
Let's see how to improve security in this scenario.

<!-- more -->

Following [Oracle security guidelines](https://docs.oracle.com/en/database/oracle/oracle-database/20/jjdev/Runtime-exe-secure-use.html#GUID-63109A8A-028C-4DFC-B24B-A2A6DB7FAE19), I created a separate low-privileged OS account and configured the database user access to it.
It turns out that this functionality has some limitations and does not work especially well with Grid Infrastructure.

Here are the details of my setup:

Oracle Grid Infrastructure 19.7 standalone that uses separate OS groups: `$ORACLE_HOME/rdbms/lib/config.c`:

```c
#define SS_DBA_GRP "asmdba"
#define SS_OPER_GRP "asmoper"
#define SS_ASM_GRP "asmadmin"
#define SS_BKP_GRP "asmadmin"
#define SS_DGD_GRP "asmadmin"
#define SS_KMT_GRP "asmadmin"
#define SS_RAC_GRP "asmadmin"
```

Oracle Database 19.7 uses the following groups:

```c
#define SS_DBA_GRP "dba"
#define SS_OPER_GRP "oper"
#define SS_ASM_GRP ""
#define SS_BKP_GRP "backupdba"
#define SS_DGD_GRP "dgdba"
#define SS_KMT_GRP "kmdba"
#define SS_RAC_GRP "racdba"
```

The `oracle` user is the software owner; its group is `oinstall`.
The database listener runs from the GI `ORACLE_HOME` (it does not matter for the purpose of the test case, though, as the issue can be reproduced even with bequeath connections).

Here is an SQL script that I use to demonstrate the issue:

```sql
def user_connect_string=tc/tc@//localhost/pdb
def sys_connect_string="sys/oracle@//localhost/pdb as sysdba"

set echo on

spool ojvm_test_case

connect &sys_connect_string

doc
  CREATING THE TEST CASE USER
#

drop user tc cascade;
grant create procedure, create session to tc identified by tc;

exec dbms_java.grant_permission('TC', 'SYS:java.io.FilePermission', '/usr/bin/who', 'read,execute')

connect &user_connect_string

CREATE OR REPLACE AND COMPILE JAVA SOURCE NAMED "OSCommand" AS
import java.io.*;
public class OSCommand {
    public static String Run(String command) {
        final String crlf = "" + (char) 10 + (char) 13;
        final int max_length = 4000;
        String str_out = "";

        try {
            final Process pr = Runtime.getRuntime().exec(command);
            pr.waitFor();

            BufferedReader br_in = null;
            try {
                br_in = new BufferedReader(new InputStreamReader(pr.getInputStream()));
                String buff = null;
                while (((buff = br_in.readLine()) != null) & (str_out.length() < max_length)) {
                    System.out.println("Process out :" + buff);
                    str_out += buff + crlf;
                }
                br_in.close();
            } catch (IOException ioe) {
                System.out.println("Exception caught printing process output.");
                ioe.printStackTrace();
            } finally {
                try {
                    br_in.close();
                } catch (Exception ex) {}
            }

            BufferedReader br_err = null;
            try {
                br_err = new BufferedReader(new InputStreamReader(pr.getErrorStream()));
                String buff = null;
                while (((buff = br_err.readLine()) != null) & (str_out.length() < max_length)) {
                    str_out += buff + crlf;
                }
                br_err.close();
            } catch (IOException ioe) {
                System.out.println("Exception caught printing process error.");
                ioe.printStackTrace();
            } finally {
                try {
                    br_err.close();
                } catch (Exception ex) {}
            }

        } catch (Exception e) {
            e.printStackTrace();
            return (e.getMessage());
        }
        if (str_out.length() > 4000) str_out = str_out.substring(0, max_length); //limit output
        return str_out;
    }
}
/

CREATE OR REPLACE FUNCTION OSCommand_Run(Command IN STRING)
RETURN VARCHAR2 IS
LANGUAGE JAVA
NAME 'OSCommand.Run(java.lang.String) return int';
/

doc
  Test #1: call OS command
#

select oscommand_run('/usr/bin/who') from dual;


doc
  ENABLING OJVM SECURITY
#

conn &sys_connect_string

exec dbms_java.set_runtime_exec_credentials('TC', 'oraexec', 'test');
commit;


connect &user_connect_string

doc
  Test #2: call OS command after Java credentials were set
#

select oscommand_run('/usr/bin/who') from dual;

doc
  Test #3: getting additional output
#
set serverout on
exec dbms_java.set_output(100000)
select oscommand_run('/usr/bin/who') from dual;


spo off
```

In a nutshell, the script creates a separate user and grants it necessary privileges to run the external command `/usr/bin/who` using a Java class (that might be copied from somewhere over the Internet judging by how it handles exceptions).

When I call that command for the first time, I get the following output:

```sql
SQL> select oscommand_run('/usr/bin/who') from dual;

OSCOMMAND_RUN('/USR/BIN/WHO')
--------------------------------------------------------------------------------
oracle   pts/0        2020-04-29 09:06 (:pts/2:S.0)
ec2-user pts/2        2020-04-29 09:06 (172.17.1.27)
ec2-user pts/3        2020-04-29 09:06 (172.17.1.27)
```

There is an OS account `oraexec` with a password test that is created on the database server host, and I associate that account to run any external commands initiated by the `TC` database user ([Java Developer's Guide](https://docs.oracle.com/en/database/oracle/oracle-database/20/jjdev/DBMS-JAVA-package.html#GUID-7DB95C10-0386-4E88-991A-2496B325082F)):

```sql
exec dbms_java.set_runtime_exec_credentials('TC', 'oraexec', 'test');
```

The subsequent calls of the previously working function, now starts failing:

```sql
SQL> select oscommand_run('/usr/bin/who') from dual;

OSCOMMAND_RUN('/USR/BIN/WHO')
--------------------------------------------------------------------------------
Cannot run program "/usr/bin/who": cannot execute /u01/app/oracle/product/db_19.
7.0/bin/jssu
```

OJVM can produce additional output, which in this case is not particularly helpful:

```sql
SQL> set serverout on
SQL> exec dbms_java.set_output(100000)

PL/SQL procedure successfully completed.

SQL> select oscommand_run('/usr/bin/who') from dual;

OSCOMMAND_RUN('/USR/BIN/WHO')
--------------------------------------------------------------------------------
Cannot run program "/usr/bin/who": cannot execute /u01/app/oracle/product/db_19.
7.0/bin/jssu


java.io.IOException: Cannot run program "/usr/bin/who": cannot execute
/u01/app/oracle/product/db_19.7.0/bin/jssu
 at java.lang.ProcessBuilder.start(ProcessBuilder.java:1057)
 at java.lang.Runtime.exec(Runtime.java:620)
 at java.lang.Runtime.exec(Runtime.java:450)
 at java.lang.Runtime.exec(Runtime.java:347)
 at OSCommand.Run(OSCommand:11)
Caused by: java.io.IOException: cannot execute
/u01/app/oracle/product/db_19.7.0/bin/jssu
 at java.lang.OracleProcess.create(Native Method)
 at java.lang.OracleProcess.construct(OracleProcess.java:112)
 at java.lang.OracleProcess.<init>(OracleProcess.java:42)
 at java.lang.OracleProcess.start(OracleProcess.java:383)
 at java.lang.ProcessBuilder.start(ProcessBuilder.java:1038)
 ... 4 more
```

`jssu` is an Oracle's way to switch to another user per my knowledge.
I know that the database uses it when it runs external jobs through `DBMS_SCHEDULER`.
The `jssu` name itself was likely inspired by the Linux `su` command (Switch User).

The first thing that I do is to check its permissions since I am quite familiar with certain issues when those permissions can go sideways due to patching actions:

```bash
[oracle@ip-172-17-31-160 lib]$ ls -la $ORACLE_HOME/bin/jssu
-rwsr-x---. 1 root oinstall 2327920 Apr 28 15:14 /u01/app/oracle/product/db_19.7.0/bin/jssu
```

The permissions are fine - its owned by root and has the setuid bit set.
In order to further diagnose this issue, I run `strace` against the server process and find this:

```
stat("/u01/app/oracle/product/db_19.7.0/bin/jssu", {st_mode=S_IFREG|S_ISUID|0750, st_size=2327920, ...}) = 0
geteuid()                         = 54321
getegid()                         = 54331
```

The uid `54321` is the oracle user, however, the gid `54331` is asmadmin (the OSASM group):

```bash
[oracle@ip-172-17-31-160 lib]$ grep 54321 /etc/passwd
oracle:x:54321:54321::/home/oracle:/bin/bash
[oracle@ip-172-17-31-160 lib]$ grep 54331 /etc/group
asmadmin:x:54331:oracle
```

When there is a role-separation in place, the Oracle binary is owned by the OSASM group:

```bash
[oracle@ip-172-17-31-160 lib]$ ls -ls /u01/app/oracle/product/db_19.7.0/bin/oracle
432852 -rwsr-s--x. 1 oracle asmadmin 443232296 Apr 28 15:15 /u01/app/oracle/product/db_19.7.0/bin/oracle
```

Oracle processes have the following groups:

```bash
# ps -o rgid,egid,cmd -p 27280
 RGID  EGID CMD
54321 54331 oracleorcl (LOCAL=NO)
```

Where `RGID=oinstall`, `EGID=asmadmin` (OSASM):

```bash
# grep 543[23]1 /etc/group
oinstall:x:54321:oracle
asmadmin:x:54331:oracle
```

The OJVM code expects that `jssu` is owned by the OSASM group in this case, so that a possible workaround for this issue is to amend the `jssu` permissions as follows:

```bash
[oracle@ip-172-17-31-160 lib]$ ls -ls /u01/app/oracle/product/db_19.7.0/bin/jssu
2276 -rwsr-x---. 1 root asmadmin 2327920 Apr 28 15:14 /u01/app/oracle/product/db_19.7.0/bin/jssu
```

Obviously it cannot be used as a long-term solution as I recall that `jssu` permissions might be changed when relink is run, or when some patches are applied.
There permissions also work fine with external jobs that use credentials.
I opened an SR with Oracle Support a few months ago and it has not gone anywhere yet.
