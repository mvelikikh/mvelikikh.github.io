---
categories:
  - Oracle
date:
  created: 2019-06-05T03:12:00
description: >-
  Encountered ORA-01031 in a PL/SQL procedure after upgrading a database to 12.2.
  I had to grant the role to the PL/SQL unit to resolve the issue.
  Also disassembled some internal functions to show that SELECT_CATALOG_ROLE is hardcoded there.
tags:
  - 12c
  - 18c
  - 19c
  - Code symbol
  - OERR
  - PL/SQL
---

# `ORA-01031` select `V$RESTORE_POINT` in PL/SQL

This blog post is about an issue with `V$RESTORE_POINT` and `ORA-01031` that I encountered after upgrading one database to 12.2.

<!-- more -->

It is a well known [fact](https://oraganism.wordpress.com/2012/10/28/access-to-vrestore_point/) that `V$RESTORE_POINT` requires special handling, namely the `SELECT_CATALOG_ROLE` should be granted to a low-privileged user trying to access this view.
I had several PL/SQL units working with `V$RESTORE_POINT` in a 12.1 database.
Those units were owned by a user that has `SELECT_CATALOG_ROLE`.
Once I upgraded the database to 12.2, those units stopped working and I started getting an infamous `ORA-01031` error.

Here is a simple test case demonstrating the initial `ORA-01031` error:

```sql hl_lines="42"
SYS@CDB$ROOT> create restore point rp_test;

Restore point created.

SYS@CDB$ROOT> alter session set container=pdb;

Session altered.

SYS@PDB> grant connect, create procedure to tc identified by tc;

Grant succeeded.

SYS@PDB> grant read on v_$restore_point to tc;

Grant succeeded.

SYS@PDB> conn tc/tc@localhost/pdb
Connected.
TC@PDB>
TC@PDB> create or replace procedure p_test
  2  is
  3  begin
  4    for test_rec in (
  5      select *
  6        from v$restore_point)
  7    loop
  8      dbms_output.put_line(test_rec.name);
  9    end loop;
 10  end;
 11  /

Procedure created.

TC@PDB>
TC@PDB> set serverout on
TC@PDB>
TC@PDB> exec p_test
BEGIN p_test; END;

*
ERROR at line 1:
ORA-01031: insufficient privileges
ORA-06512: at "TC.P_TEST", line 4
ORA-06512: at line 1
```

Despite the fact that the user `TC` does have the `READ` privilege on `V_$RESTORE_POINT`, it is still not able to access it.

Till 12.2 it was enough to grant `SELECT_CATALOG_ROLE` to the owner of a program unit to avoid the error:

```sql hl_lines="1 11 13"
SYS@PDB> grant select_catalog_role to tc;

Grant succeeded.

SYS@PDB> conn tc/tc@localhost/pdb
Connected.
TC@PDB>
TC@PDB> set serverout on
TC@PDB>
TC@PDB> exec p_test
RP_TEST

PL/SQL procedure successfully completed.
```

It is not the case anymore in 12.2 and subsequent versions which I tested: 18c and 19c.

The output from 19c is below:

```sql hl_lines="1 15"
SYS@PDB> grant select_catalog_role to tc;

Grant succeeded.

SYS@PDB> conn tc/tc@localhost/pdb
Connected.
SYS@PDB>
TC@PDB> set serverout on
TC@PDB>
TC@PDB> exec p_test
BEGIN p_test; END;

*
ERROR at line 1:
ORA-01031: insufficient privileges
ORA-06512: at "TC.P_TEST", line 5
ORA-06512: at "TC.P_TEST", line 5
ORA-06512: at line 1
```

BTW, the line `ORA-06512: at "TC.P_TEST", line 5` is reported twice, and 19c shows a slightly different errorstack than 12.1.

The following solution works in 12.2 on:

```sql hl_lines="1 12 14"
SYS@PDB> grant select_catalog_role to procedure tc.p_test;

Grant succeeded.

SYS@PDB>
SYS@PDB> conn tc/tc@localhost/pdb
Connected.
TC@PDB>
TC@PDB> set serverout on
TC@PDB>
TC@PDB> exec p_test
RP_TEST

PL/SQL procedure successfully completed.
```

The need for having the `SELECT_CATALOG_ROLE` granted to the user in 12.1 does not make much sense as roles do not work in named PL/SQL **definer rights** program units.
I am not talking about roles granted to PL/SQL units here.
Therefore, the "new" behavior requiring the role to be granted to PL/SQL units appears to be more proper and logical.

While working on this issue, I was tinkering with gdb a little bit in an attempt to find an explanation to that `SELECT_CATALOG_ROLE` requirement - that role is not coming from V$-views as it was said in [the blogpost](https://oraganism.wordpress.com/2012/10/28/access-to-vrestore_point/) which I referred before.
It turns out that role is used in Oracle code:

``` hl_lines="1 10 12 16"
(gdb) disassemble kccxrsp
Dump of assembler code for function kccxrsp:
   0x000000000a225740 <+0>:     xchg   %ax,%ax
   0x000000000a225742 <+2>:     push   %rbp
   0x000000000a225743 <+3>:     mov    %rsp,%rbp
   0x000000000a225746 <+6>:     sub    $0x60,%rsp
   0x000000000a22574a <+10>:    mov    %rbx,-0x58(%rbp)
   0x000000000a22574e <+14>:    mov    %rdx,%rbx
..skip..
   0x000000000a2257e5 <+165>:   mov    $0xdda7b48,%edi
   0x000000000a2257ea <+170>:   mov    $0x13,%esi
   0x000000000a2257ef <+175>:   callq  0x859bd90 <kzsrol>
..skip..
---Type <return> to continue, or q <return> to quit---q
Quit
(gdb) x/s 0xdda7b48
0xdda7b48:      "SELECT_CATALOG_ROLE"
```

`GV$RESTORE_POINT` is based on `X$KCCRSP` and `X$KCCNRS`.
The former is seems to be accessed through the `kccxrsp` function.
`kccxrsp` calls `kzsrol` to perform extra security checks and passes `SELECT_CATALOG_ROLE` to it.

TL;DR: V$-views are really special views (i.e. no read consistency), and `V$RESTORE_POINT` has its own little peculiarity among them.
Not only does it require to have the `SELECT_CATALOG_ROLE` granted to a non-administrative user but also the definer rights PL/SQL unit owned by such a user should have that role granted as well.
