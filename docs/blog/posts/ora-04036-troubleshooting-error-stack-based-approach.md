---
categories:
  - Oracle
date:
  created: 2019-07-14T23:40:00
description: >-
  Troubleshooting ORA-04036 errors without modifying the source code.
  Oracle diagnostic events are used.
tags:
  - 19c
  - Diagnostic event
  - OERR
  - X$
---

# ORA-04036 Troubleshooting: Error Stack Based Approach

A developer came to me the other day to ask me about an `ORA-04036` error he encountered.
The goal of this blog post is to provide steps to troubleshoot the `ORA-04036` error without modifying the source code.

<!-- more -->

The trace file was as follows:

``` hl_lines="9 15 21"
=======================================
PRIVATE MEMORY SUMMARY FOR THIS PROCESS
---------------------------------------
******************************************************
PRIVATE HEAP SUMMARY DUMP
1666 MB total:
  1665 MB commented, 296 KB permanent
   260 KB free (0 KB in empty extents),
    1664 MB,   1 heap:    "session heap   "            64 KB free held
------------------------------------------------------
Summary of subheaps at depth 1
1665 MB total:
  1662 MB commented, 76 KB permanent
  2973 KB free (0 KB in empty extents),
    1664 MB,   7 heaps:   "koh-kghu sessi "            2956 KB free held
------------------------------------------------------
Summary of subheaps at depth 2
1661 MB total:
  1615 MB commented, 15 KB permanent
    46 MB free (0 KB in empty extents),
    1661 MB, 41455 chunks:  "pl/sql vc2                " 46 MB free held
```

That is quite common and a conclusion can easily be drawn that most memory is allocated to PL/SQL collections.
The relevant incident file contained the following lines:

``` hl_lines="3 9"
[TOC00004]
----- Current SQL Statement for this session (sql_id=fr9uqhy2xzj6n) -----
BEGIN pkg.fill_memory; END;
[TOC00005]
----- PL/SQL Stack -----
----- PL/SQL Call Stack -----
  object      line  object
  handle    number  name
0x6a6b4250        43  package body TC.PKG.SMALL_ALLOCATION
0x6a6b4250         8  package body TC.PKG.FILL_MEMORY
0x68f1f108         1  anonymous block
[TOC00005-END]
```

It can be depicted from that PL/SQL Call Stack that the actual error happened in the `SMALL_ALLOCATION` procedure.
As you might guess, it does not allocate a lot of memory.
Therefore, there is just not enough information in the trace file and the corresponding incident file to figure out those PL/SQL units that allocated the most memory.
The developer was not very helpful and had no clue where the memory could be allocated from in his own code.
Thankfully, he was able to provide the code that reproduced the error.

Initially I tried to troubleshoot this issue dumping Error Stacks for the session running the problem code.
I settled on Error Stacks because those included PL/SQL Call Stacks, and I do not know any other ways to get them.

Here comes the first challenge: when do I need to gather the Error Stack?
I decided to gather it when `V$PROCESS.PGA_USED_MEM` goes above a certain value.
A sample script to dump the Error Stack when `PGA_USED_MEM` goes above 1G is below:

```sql hl_lines="22"
SQL> col paddr new_v paddr
SQL>
SQL> select value from v$diag_info where name = 'Default Trace File';

VALUE
--------------------------------------------------------------------------------
/u01/app/oracle/diag/rdbms/orcl/orcl/trace/orcl_ora_13014.trc

SQL>
SQL> select '0x'||paddr paddr
  2    from v$session
  3   where sid = sys_context('userenv', 'sid');

PADDR
------------------
0x0000000075558A80

SQL>
SQL> alter session set events -
>   'wait_event["PGA memory operation"] {gt:refn(&paddr., 8, 3728), 0x40000000}{occurence:1,1} trace("pga_used_mem=%\n", refn(&paddr., 8, 3728)) errorstack(1)';
old   1: alter session set events    'wait_event["PGA memory operation"] {gt:refn(&paddr., 8, 3728), 0x40000000}{occurence:1,1} trace("pga_used_mem=%\n", refn(&paddr., 8, 3728)) errorstack(1)'
new   1: alter session set events    'wait_event["PGA memory operation"] {gt:refn(0x0000000075558A80, 8, 3728), 0x40000000}{occurence:1,1} trace("pga_used_mem=%\n", refn(0x0000000075558A80, 8, 3728)) errorstack(1)'

Session altered.
```

The highlighted line requires a bit of explanation:

```sql
alter session set events -
  'wait_event["PGA memory operation"] -
   {gt:refn(0x0000000075558A80, 8, 3728), 0x40000000} -
   {occurence:1,1} -
   trace("pga_used_mem=%\n", refn(0x0000000075558A80, 8, 3728)) -
   errorstack(1)';
```

- `wait_event["PGA memory operation"]` - I would like to execute some actions when the session wait event is `PGA memory operation`
- `refn(0x0000000075558A80, 8, 3728)`: `refn` can be used to peek into a memory location and dereference the value under it.
  Here is an excerpt from the `oradebug doc event action` output:
  ```
  refn
           - Dereference ptr-to-number: *(ub<numsize>*)(((ub1*)<ptr>)) + <offset>)
  ```
  I use the `refn(v$process.addr, 8, 3728)` call where 3728 is the offset of `PGA_USED_MEM` within the `X$KSUPR` structure that is behind `V$PROCESS`:
  ```sql
  SQL> select c.kqfconam, c.kqfcosiz, c.kqfcooff
    2    from x$kqfta t,
    3         x$kqfco c
    4   where t.kqftanam = 'X$KSUPR'
    5     and c.kqfcotab = t.indx
    6     and c.kqfconam = 'KSUPRPUM';

  KQFCONAM       KQFCOSIZ     KQFCOOFF
  ---------- ------------ ------------
  KSUPRPUM              8         3728
  ```
  As you might guess, 8 is the size of the value which is the second parameter in the `refn` call.
- `0x40000000` is 1G in hex.
- `{gt:refn(0x0000000075558A80, 8, 3728), 0x40000000}` - that is an event filter.
  Here is an excerpt from the `oradebug doc event filter` output:
  ```
  gt                   filter to only fire an event when a > b
  ```
  Hence, I would like to fire my event action only when `PGA_USED_MEM` is above 1G.
- `{occurence:1,1}` I would like to fire it only once to minimize overhead.
- `trace("pga_used_mem=%\n", refn(0x0000000075558A80, 8, 3728)) errorstack(1)` - these are the actions that should be executed.
  Firstly, I am tracing the `PGA_USED_MEM` value.
  Then I am dumping the Error Stack.

After running this code, I executed the procedure causing `ORA-04036` and got the following lines in the trace file:

``` hl_lines="1 8 13"
pga_used_mem=1092512013

*** 2019-07-14T18:22:04.499962+01:00 (PDB(3))
dbkedDefDump(): Starting a non-incident diagnostic dump (flags=0x0, level=1, mask=0x0)
----- Error Stack Dump -----
<error barrier> at 0x7fff83740dd0 placed dbkda.c@296
----- Current SQL Statement for this session (sql_id=fr9uqhy2xzj6n) -----
BEGIN pkg.fill_memory; END;
----- PL/SQL Stack -----
----- PL/SQL Call Stack -----
  object      line  object
  handle    number  name
0x6a6b4250        31  package body TC.PKG.HUGE_ALLOCATION
0x6a6b4250         7  package body TC.PKG.FILL_MEMORY
0x68f1f108         1  anonymous block
```

Following the Error Stack dump, there was a dump for `ORA-04036`.
Still, there can be the case that `HUGE_ALLOCATION` procedure just allocated 100M out of 1G, so that the main shortcoming of this method - its granularity.
For instance, I was not able to find out how to setup several Error Stacks triggering at 500M and 1G.

The package that I used in these tests is provided below:

```sql hl_lines="25 37 49"
create or replace package pkg
is
  MAX_VC_LEN constant binary_integer := 32767;
  type char_tbl_type is table of varchar2(MAX_VC_LEN);
  v_tbl char_tbl_type := char_tbl_type();
  procedure fill_memory;
  procedure tiny_allocation;
  procedure huge_allocation;
  procedure small_allocation;
end;
/
create or replace package body pkg
is
  procedure fill_memory
  is
  begin
    tiny_allocation;
    huge_allocation;
    small_allocation;
  end fill_memory;

  procedure tiny_allocation
  is
    v_start_size pls_integer := v_tbl.count;
    v_extend_size constant pls_integer := 1000;
  begin
    v_tbl.extend(v_extend_size);
    for i in 1..v_extend_size
    loop
      v_tbl(v_start_size + i) := lpad('x', MAX_VC_LEN, 'x');
    end loop;
  end tiny_allocation;

  procedure huge_allocation
  is
    v_start_size pls_integer := v_tbl.count;
    v_extend_size constant pls_integer := 38500;
  begin
    v_tbl.extend(v_extend_size);
    for i in 1..v_extend_size
    loop
      v_tbl(v_start_size + i) := lpad('x', MAX_VC_LEN, 'x');
    end loop;
  end huge_allocation;

  procedure small_allocation
  is
    v_start_size pls_integer := v_tbl.count;
    v_extend_size constant pls_integer := 3000;
  begin
    v_tbl.extend(v_extend_size);
    for i in 1..v_extend_size
    loop
      v_tbl(v_start_size + i) := lpad('x', MAX_VC_LEN, 'x');
    end loop;
  end small_allocation;
end;
/
```

I specifically setup those collection values to make the `SMALL_ALLOCATION` call produce the `ORA-04036` error in my 19c instance with `PGA_AGGREGATE_LIMIT=2G`.
