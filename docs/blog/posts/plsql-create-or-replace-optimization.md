---
categories:
  - Oracle
date:
  created: 2019-04-08T03:22:00
description: >-
  PL/SQL Create or Replace optimization kicks in when the source is the same.
  It is checked before Multitenant related checks, so that a local user can seemingly compile a PL/SQL unit belonging to a global user provided the source is the same.
  There is event 10523 to disable the optimization.
tags:
  - 12c
  - Code symbol
  - Diagnostic event
  - OERR
  - PL/SQL
---

# PL/SQL Create or Replace Optimization

Oracle said in their Student Guide for 12c that a local user cannot utilize system privileges on a common user's schema.
When I initially checked that preposition, I was a little bit puzzled by the behavior discussed in this post.

<!-- more -->

```sql
TC@PDB> create or replace procedure c##tc.p
  2  is
  3  begin
  4    null;
  5  end;
  6  /

Procedure created.

TC@PDB>
TC@PDB> create or replace procedure c##tc.p
  2  is
  3  begin
  4    null;
  5    null; -- second null
  6  end;
  7  /
create or replace procedure c##tc.p
*
ERROR at line 1:
ORA-01031: insufficient privileges
```

I drew a proper conclusion back then that Oracle generally tries to be as lazy as possible, so that if it could not do something, it would probably would not do it.
Like in the example above, if Oracle knows that the source code is the same and all PL/SQL settings are the same, why bother?
It just reports back as if the code had been compiled when actually Oracle compared the stored source and its PL/SQL settings with whatever a user supplied.
Although it seems a sound approach, I did not have enough proves that Oracle definitely works in such a way with PL/SQL units.

However, last week I listened to an excellent [Bryn Llewellyn](https://twitter.com/brynlite?lang=en)'s one day seminar where we were discussing Edition-Based Redefinition (EBR) topics, and Bryn said exactly the same thing - PL/SQL does have an optimization to not recompile stored units when the supplied code is the same (it was roughly something like that).
It rang a bell and made me return to that issue discovered a few years ago.

Let us make an initial setup and reproduce the error:

```sql
SYS@CDB$ROOT> conn / as sysdba
Connected.

SYS@CDB$ROOT> create user c##tc identified by oracle;

User created.

SYS@CDB$ROOT> grant connect, create procedure to c##tc container=all;

Grant succeeded.

SYS@CDB$ROOT>
SYS@CDB$ROOT> conn c##tc/oracle@pdb
Connected.
C##TC@PDB>
C##TC@PDB> create or replace procedure c##tc.p
  2  is
  3  begin
  4    null;
  5  end;
  6  /

Procedure created.

C##TC@PDB>
C##TC@PDB> conn sys/oracle@pdb as sysdba
Connected.
SYS@PDB>
SYS@PDB> grant alter session, connect, create any procedure to tc identified by tc;

Grant succeeded.

SYS@PDB> conn tc/tc@pdb
Connected.
TC@PDB>
TC@PDB> create or replace procedure c##tc.p
  2  is
  3  begin
  4    null;
  5  end;
  6  /

Procedure created.

TC@PDB>
TC@PDB> create or replace procedure c##tc.p
  2  is
  3  begin
  4    null;
  5    null; -- second null
  6  end;
  7  /
create or replace procedure c##tc.p
*
ERROR at line 1:
ORA-01031: insufficient privileges
```

I re-execute the same create or replace statement with sql trace enabled so as to confirm that it is effectively a noop operation - Oracle does not really recompile that procedure.

While looking into the trace file, the last executed statement is this:

```
PARSING IN CURSOR #140098350838112 len=54 dep=1 uid=0 oct=3 lid=0 tim=228489468158 hv=696375357 ad='c49fffc0' sqlid='9gq78x8ns3q1x'
select source from source$ where obj#=:1 order by line
END OF STMT
```

Once I got this, I decided to obtain a short stack of Oracle functions to see what function in Oracle kernel causes that SQL to be executed:

```sql
TC@PDB> alter session set events 'sql_trace[sql:9gq78x8ns3q1x] trace("%s\n", shortstack())';

Session altered.
TC@PDB> create or replace procedure c##tc.p
  2  is
  3  begin
  4    null;
  5  end;
  6  /

Procedure created.
```

The interesting part in the trace file is below:

```
kkscsCheckCriteria<-kkscsCheckCursor<-kkscsSearchChildList<-kksfbc<-kkspsc0<-kksParseCursor<-opiosq0<-opiall0<-opikpr<-opiodr<-rpidrus<-skgmstack<-rpiswu2<-kprball<-kqlsrclod<-kqllod_new<-kqllod<-kglobld<-kglobpn<-kglpim<-kglpin<-kkx_same_src<-kkpcrt<-opies
kxstGetSqlTraceLevel<-kkscsCheckCriteria<-kkscsCheckCursor<-kkscsSearchChildList<-kksfbc<-kkspsc0<-kksParseCursor<-opiosq0<-opiall0<-opikpr<-opiodr<-rpidrus<-skgmstack<-rpiswu2<-kprball<-kqlsrclod<-kqllod_new<-kqllod<-kglobld<-kglobpn<-kglpim<-kglpin<-kkx_s
opiexe<-opiall0<-opikpr<-opiodr<-rpidrus<-skgmstack<-rpiswu2<-kprball<-kqlsrclod<-kqllod_new<-kqllod<-kglobld<-kglobpn<-kglpim<-kglpin<-kkx_same_src<-kkpcrt<-opiexe<-opiosq0<-kpoal8<-opiodr<-ttcpip<-opitsk<-opiino<-opiodr<-opidrv<-sou2o<-opimai_real<-ssthrs
kxstGetSqlTraceLevel<-opiexe<-opiall0<-opikpr<-opiodr<-rpidrus<-skgmstack<-rpiswu2<-kprball<-kqlsrclod<-kqllod_new<-kqllod<-kglobld<-kglobpn<-kglpim<-kglpin<-kkx_same_src<-kkpcrt<-opiexe<-opiosq0<-kpoal8<-opiodr<-ttcpip<-opitsk<-opiino<-opiodr<-opidrv<-sous
```

Notice that sequence: `kkpcrt -> kkx_same_src`
I was quite curious about that `kkx_same_src` as it looked like an explanation of that fictional compilation, so I just disassembled it and found these two assembler instructions below in the output:

```
gdb $ORACLE_HOME/bin/oracle
GNU gdb (GDB) Red Hat Enterprise Linux 7.6.1-114.el7
Copyright (C) 2013 Free Software Foundation, Inc.
License GPLv3+: GNU GPL version 3 or later <http://gnu.org/licenses/gpl.html>
This is free software: you are free to change and redistribute it.
There is NO WARRANTY, to the extent permitted by law.  Type "show copying"
and "show warranty" for details.
This GDB was configured as "x86_64-redhat-linux-gnu".
For bug reporting instructions, please see:
<http://www.gnu.org/software/gdb/bugs/>...
Reading symbols from /u01/app/oracle/product/12.1.0/dbhome_1/bin/oracle...(no debugging symbols found)...done.
(gdb) disassemble kkx_same_src
Dump of assembler code for function kkx_same_src:
... skip ...
   0x0000000002b8703f <+479>:   mov    $0x291b,%edi
   0x0000000002b87044 <+484>:   callq  0xceafa20 <dbkdchkeventrdbmserr>
```

There is an event `0x291b` that can influence that function!
Let us try this out:

```sql
TC@PDB> alter session set events '0x291b level 1';

Session altered.

TC@PDB> create or replace procedure c##tc.p
  2  is
  3  begin
  4    null;
  5  end;
  6  /
create or replace procedure c##tc.p
*
ERROR at line 1:
ORA-01031: insufficient privileges


TC@PDB> alter session set events '0x291b off';

Session altered.

TC@PDB> create or replace procedure c##tc.p
  2  is
  3  begin
  4    null;
  5  end;
  6  /

Procedure created.
```

Indeed, it does effect the execution.
The next step is to find out what this event is:

```
[oracle@localhost ~]$ echo 'ibase=16;291B' | bc
10523
[oracle@localhost ~]$ oerr ora 10523
10523, 00000, "force recreate package even if definition is unchanged"
// *Cause:
// *Action:  Set this event only under the supervision of Oracle development
// *Comment: Changes behaviour of create or replace package, procedure,
//           function or type to force recreation of the object even if its new
//           definition exactly matches the old definition.
//           No level number required.
```

That event was the last missing piece in this puzzle.

**TL;DR**: as any good program, Oracle tries to do as little work as possible - this is laziness in its good sense.
After all, the fastest way to do something is to not do it at all.

That what happens here - if there is no need to compile a PL/SQL unit, Oracle can identify it and report back to the user that the PL/SQL has been compiled when really it was not.
That optimization is controlled by event 10523.
However, it kicks in early, before other Multitenant related checks, namely Oracle does not check whether a local user actually can compile a stored PL/SQL unit in a common schema.
I believe that is a bug as there should be an `ORA-1031` error in the first place, even when the source is the same.

Everything said is applicable only to 12.1.0.2 on which it has been tested.
