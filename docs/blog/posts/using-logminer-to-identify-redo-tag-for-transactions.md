---
categories:
  - Oracle
date:
  created: 2020-03-03T23:30:00
description: >-
  How to obtain the redo tag of a transaction using LogMiner and X$LOGMNR_CONTENTS.DUMP_INFO of redo opcode 5.20.
tags:
  - 19c
  - X$
---

# Using LogMiner to Identify Redo Tag for Transactions

I was asked if there is a way to identify what redo tag was set for a specific transaction.
Let's find it out in this post.

<!-- more -->

There is a document that answers the question ***if*** any tag was set without clarifying ***what*** tag was set specifically: [Using Logminer to Identify if a Non-NULL Tag Has Been Set Using DBMS\_STREAMS.SET\_TAG (Doc ID 740574.1)](https://support.oracle.com/rs?type=doc&id=740574.1)
Besides, LogDump can be used to display the tag information when GoldenGate is in use: [GGSTOKEN](https://docs.oracle.com/en/middleware/goldengate/core/19.1/logdump-ref/logdump-commands.html#GUID-9C86F9BB-461D-4002-B517-CB48038A4F3A).

My experiments revealed that the required information can be obtained using `X$LOGMNR_CONTENTS.DUMP_INFO` as the example below demonstrates.

```sql hl_lines="24 33 46 53 70 81"
SYS@PDB> grant create session, create table, select_catalog_role to tc identified by tc;

Grant succeeded.

SYS@PDB>
SYS@PDB> grant execute on dbms_streams_adm to tc;

Grant succeeded.

SYS@PDB>
SYS@PDB> alter user tc quota 100m on users;

User altered.

SYS@PDB>
SYS@PDB> conn tc/tc@pdb
Connected.
TC@PDB>
TC@PDB>
TC@PDB> select current_scn from v$database;

CURRENT_SCN
-----------
    2221571

TC@PDB>
TC@PDB> create table t(id int, s varchar2(30))
  2    segment creation immediate;

Table created.

TC@PDB>
TC@PDB> exec dbms_streams_adm.set_tag(hextoraw('112233'))

PL/SQL procedure successfully completed.

TC@PDB>
TC@PDB> insert into t values (1, 'tag_1');

1 row created.

TC@PDB> select dbms_transaction.local_transaction_id from dual;

LOCAL_TRANSACTION_ID
--------------------------------------------------------------------------------
3.29.732

TC@PDB> commit;

Commit complete.

TC@PDB>
TC@PDB> exec dbms_streams_adm.set_tag(hextoraw('deadbeef'))

PL/SQL procedure successfully completed.

TC@PDB>
TC@PDB> insert into t values (11, 'tag_1');

1 row created.

TC@PDB> insert into t values (12, 'tag_1');

1 row created.

TC@PDB> select dbms_transaction.local_transaction_id from dual;

LOCAL_TRANSACTION_ID
--------------------------------------------------------------------------------
8.26.689

TC@PDB> commit;

Commit complete.

TC@PDB>
TC@PDB> select current_scn from v$database;

CURRENT_SCN
-----------
    2221592
```

Here is the summary information for the transactions above:

| TRANSACTION | TAG      |
| ----------- | -------- |
|    3.29.732 | 112233   |
|    8.26.689 | DEADBEEF |

The following query shows only the redo opcode `5.20` (Transaction Audit) rows for these transactions:

```sql hl_lines="42 56"
SQL> col log_file old_v log_file
SQL>
SQL> select member log_file
  2    from v$log l,
  3         v$logfile f
  4   where l.status = 'CURRENT'
  5     and f.group# = l.group#;

LOG_FILE
--------------------------------------------------------------------------------
/opt/oracle/oradata/ORCLCDB/redo02.log

SQL>
SQL> exec dbms_logmnr.add_logfile('&log_file.')

PL/SQL procedure successfully completed.

SQL>
SQL> exec dbms_logmnr.start_logmnr(options => dbms_logmnr.dict_from_online_catalog)

PL/SQL procedure successfully completed.

SQL> select xidusn, xidslt, xidsqn,
  2        dump_info
  3   from x$logmnr_contents
  4  where (xidusn, xidslt, xidsqn) in ((3,29,732),(8,26,689))
  5    and scn between 2221571 and 2221592
  6    and component_id = 5
  7    and opcode = 20;

    XIDUSN     XIDSLT     XIDSQN DUMP_INFO
---------- ---------- ---------- ----------------------------------------------------------------------------------------------------
         3         29        732 CHANGE #3 MEDIA RECOVERY MARKER CON_ID:3 SCN:0x0000000000000000 SEQ:0 OP:5.20 ENC:0 FLG:0x0000
                                 session number   = 264
                                 serial  number   = 29041
                                 transaction name =
                                 version 318767104
                                 audit sessionid 24
                                 Client Id =
                                 login   username = TC
                                 REPL MARKER:
                                  06 00 09 00 00 00 01 00 03 11 22 33


    XIDUSN     XIDSLT     XIDSQN DUMP_INFO
---------- ---------- ---------- ----------------------------------------------------------------------------------------------------
         8         26        689 CHANGE #3 MEDIA RECOVERY MARKER CON_ID:3 SCN:0x0000000000000000 SEQ:0 OP:5.20 ENC:0 FLG:0x0000
                                 session number   = 264
                                 serial  number   = 29041
                                 transaction name =
                                 version 318767104
                                 audit sessionid 24
                                 Client Id =
                                 login   username = TC
                                 REPL MARKER:
                                  06 00 0a 00 00 00 01 00 04 de ad be ef
```

It appears that the 9th byte of a `REPL MARKER` value stores the length of the tag.
Therefore, it is possible to extract a tag using the following query:

```sql hl_lines="16 30"
SQL> select xidusn, xidslt, xidsqn, repl_marker,
  2         utl_raw.substr(repl_marker, 10, to_number(utl_raw.substr(repl_marker, 9, 1), 'xxxxxxxxxx')) tag,
  3         dump_info
  4    from (
  5          select xidusn, xidslt, xidsqn,
  6                 hextoraw(replace(regexp_substr(dump_info, 'REPL MARKER:.(.*).', 1, 1, 'n', 1), ' ')) repl_marker,
  7                 dump_info
  8            from x$logmnr_contents
  9           where (xidusn, xidslt, xidsqn) in ((3,29,732),(8,26,689))
 10             and scn between 2221571 and 2221592
 11             and component_id = 5
 12             and opcode = 20);

    XIDUSN     XIDSLT     XIDSQN REPL_MARKER                TAG        DUMP_INFO
---------- ---------- ---------- -------------------------- ---------- ----------------------------------------------------------------------------------------------------
         3         29        732 060009000000010003112233   112233     CHANGE #3 MEDIA RECOVERY MARKER CON_ID:3 SCN:0x0000000000000000 SEQ:0 OP:5.20 ENC:0 FLG:0x0000
                                                                       session number   = 264
                                                                       serial  number   = 29041
                                                                       transaction name =
                                                                       version 318767104
                                                                       audit sessionid 24
                                                                       Client Id =
                                                                       login   username = TC
                                                                       REPL MARKER:
                                                                        06 00 09 00 00 00 01 00 03 11 22 33


    XIDUSN     XIDSLT     XIDSQN REPL_MARKER                TAG        DUMP_INFO
---------- ---------- ---------- -------------------------- ---------- ----------------------------------------------------------------------------------------------------
         8         26        689 06000A000000010004DEADBEEF DEADBEEF   CHANGE #3 MEDIA RECOVERY MARKER CON_ID:3 SCN:0x0000000000000000 SEQ:0 OP:5.20 ENC:0 FLG:0x0000
                                                                       session number   = 264
                                                                       serial  number   = 29041
                                                                       transaction name =
                                                                       version 318767104
                                                                       audit sessionid 24
                                                                       Client Id =
                                                                       login   username = TC
                                                                       REPL MARKER:
                                                                        06 00 0a 00 00 00 01 00 04 de ad be ef
```

It is quite handy that `X$LOGMNR_CONTENTS.DUMP_INFO` contains the same or, at least, the subset of the information present in the redo log dump, that allows to use it for sophisticated analysis in SQL\*Plus without resorting to low-level dumps or the LogDump utility of Oracle GoldenGate.
I was using a vanilla 19.3 database on Linux for these experiments.
