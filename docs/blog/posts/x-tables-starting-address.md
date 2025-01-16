---
categories:
  - Oracle
date:
  created: 2023-04-15T01:32:00
description: >-
  Demonstrate how to determine X$ tables starting addresses and the number of rows by using the Oracle qerfxArrayMaxSize function.
tags:
  - 19c
  - Code symbol
  - X$
---

# X$ tables: starting address

The starting address of X$ tables makes sense for tables residing in SGA or defined within the Oracle binary.
It is usually found by querying an X$ table.
This blog post describes an alternative method of obtaining the starting address by calling an Oracle C function.

<!-- more -->

## Introduction

The Oracle function that can be used here is `qerfxArrayMaxSize`.
Here is a short GDB script demonstrating its usage:

```
set pagination off
set trace-commands on

set $ctx = (int *)malloc(4)

def x_desc
  printf "result = 0x%x\n", (int)qerfxArrayMaxSize($arg0, (int)strlen($arg0), (int *)$ctx)
  printf "start_addr = 0x%x\n", *(long *)($ctx+18)
  info symbol *(int *)($ctx+18)
  p/a (long[10])(**(long *)($ctx+18))
  printf "row_count = %d\n", *(int *)($ctx+20)
end

x_desc "X$KSUPR"
x_desc "X$KSUSE"
x_desc "X$MESSAGES"
```

The three tables are going to be examined in separate sections below: [X$KSUPR](#xksupr), [X$KSUSE](#xksuse), [X$MESSAGES](#xmessages).

## X$KSUPR

The GDB output:

``` hl_lines="3 5 9"
+x_desc "X$KSUPR"
++printf "result = 0x%x\n", (int)qerfxArrayMaxSize("X$KSUPR", (int)strlen("X$KSUPR"), (int *)$ctx)
result = 0x9a537260
++printf "start_addr = 0x%x\n", *(long *)($ctx+18)
start_addr = 0x9a537260
++info symbol *(int *)($ctx+18)
No symbol matches *(int *)($ctx+18).
++p/a (long[10])(**(long *)($ctx+18))
$1 = {0x9a588070, 0x9a5895e0, 0x9a58ab50, 0x9a58c0c0, 0x9a58d630, 0x9a58eba0, 0x9a590110, 0x9a591680, 0x9a592bf0, 0x9a594160}
++printf "row_count = %d\n", *(int *)($ctx+20)
row_count = 600
```

The SQL\*Plus output:

```sql
SQL> select addr from x$ksupr where rownum<=10;

ADDR
----------------
000000009A588070
000000009A5895E0
000000009A58AB50
000000009A58C0C0
000000009A58D630
000000009A58EBA0
000000009A590110
000000009A591680
000000009A592BF0
000000009A594160

10 rows selected.
```

Thus, the result of the function is a pointer to an array storing pointers to `X$KSUPR` rows (**0x9a588070**, **0x9a5895e0**, **0x9a58ab50**, etc.).
The function also conveniently returns the number of rows of the relevant fixed array:

```sql
++printf "row_count = %d\n", *(int *)($ctx+20)
row_count = 600

SQL> select count(*) from x$ksupr;

  COUNT(*)
----------
       600

SQL> select value from v$parameter where name='processes';

VALUE
--------------------------------------------------------------------------------
600
```

## X$KSUSE

The GDB output:

``` hl_lines="3 5 9"
+x_desc "X$KSUSE"
++printf "result = 0x%x\n", (int)qerfxArrayMaxSize("X$KSUSE", (int)strlen("X$KSUSE"), (int *)$ctx)
result = 0x39c
++printf "start_addr = 0x%x\n", *(long *)($ctx+18)
start_addr = 0x9ae5a808
++info symbol *(int *)($ctx+18)
No symbol matches *(int *)($ctx+18).
++p/a (long[10])(**(long *)($ctx+18))
$2 = {0x9a8ec740, 0x9a8eef28, 0x9a8f1710, 0x9a8f3ef8, 0x9a8f66e0, 0x9a8f8ec8, 0x9a8fb6b0, 0x9a8fde98, 0x9a900680, 0x9a902e68}
++printf "row_count = %d\n", *(int *)($ctx+20)
row_count = 924
```

This time around the function returns the number of rows (**0x39c**=**924**) of the corresponding array.
The SQL\*Plus output:

```sql
SQL> select addr from x$ksuse where rownum<=10;

ADDR
----------------
000000009A8EC740
000000009A8EEF28
000000009A8F1710
000000009A8F3EF8
000000009A8F66E0
000000009A8F8EC8
000000009A8FB6B0
000000009A8FDE98
000000009A900680
000000009A902E68

10 rows selected.

SQL> select count(*) from x$ksuse;

  COUNT(*)
----------
       924

SQL> select value from v$parameter where name='sessions';

VALUE
--------------------------------------------------------------------------------
924
```

## X$MESSAGES

The GDB output:

```
+x_desc "X$MESSAGES"
++printf "result = 0x%x\n", (int)qerfxArrayMaxSize("X$MESSAGES", (int)strlen("X$MESSAGES"), (int *)$ctx)
result = 0x212
++printf "start_addr = 0x%x\n", *(long *)($ctx+18)
start_addr = 0x152e5760
++info symbol *(int *)($ctx+18)
ksbsdt in section .rodata of /u01/app/oracle/product/19.3.0/dbhome_1/bin/oracle
++p/a (long[10])(**(long *)($ctx+18))
$3 = {0xee3e20 <ksl_pdb_event_stats_extend>, 0x152ef148, 0x13be18f8, 0x11, 0xee4ad0 <kslwo_compute_sys_thresholds_bg_action>, 0x152ef160, 0x13be18f8, 0x1, 0x713b1f0 <kslwo_process_sys_wait_bg_action>, 0x152ef178}
++printf "row_count = %d\n", *(int *)($ctx+20)
row_count = 530
```

The output above is very different from both `X$KSUPR` and `X$KSUSE` - the starting address is the actual address of the `ksbsdt` structure defined in the Oracle binary:

```
[oracle@rac1 bin]$ readelf -s oracle | grep 152e5760
203009: 00000000152e5760 16992 OBJECT  GLOBAL DEFAULT   17 ksbsdt
218757: 00000000152e5760 16992 OBJECT  GLOBAL DEFAULT   17 ksbsdt
```

The SQL\*Plus output:

```sql
SQL> select addr from x$messages where rownum<=10;

ADDR
----------------
00000000152E5760
00000000152E5780
00000000152E57A0
00000000152E57C0
00000000152E57E0
00000000152E5800
00000000152E5820
00000000152E5840
00000000152E5860
00000000152E5880

10 rows selected.

SQL> select count(*) from x$messages;

  COUNT(*)
----------
       530
```

## Conclusion

The `qerfxArrayMaxSize` function can be used to determine the starting address of X$ tables residing in SGA or Oracle binary.
The return value of the function is not very consistent: the function returned the starting address for `X$KSUPR` and the number of rows for `X$KSUSE`/`X$MESSAGES`.
It might be the case that the function returns the `void` type and the results are inconsistent because we are just examining `$rax`.
By contrast, the memory area defined by the third parameter always stores the starting address and the number of rows for the tables I tested it with.
I consider it is reliable for these types of tables (non-UGA/non-PGA based).
I am disposed to think that `X$KQFTA.KQFTATYP` and maybe `KQFTAFLG` determine whether it is an SGA/PGA/UGA/Oracle binary based table:

```sql
SQL> select kqftanam, kqftatyp, kqftaflg
  2    from x$kqfta
  3   where kqftanam in ('X$KSUPR', 'X$KSUSE', 'X$MESSAGES')
  4  /

KQFTANAM                         KQFTATYP   KQFTAFLG
------------------------------ ---------- ----------
X$KSUSE                                 2          1
X$KSUPR                                 2          0
X$MESSAGES                              1          0
```

However, more experiments need to be conducted to confirm that.
I initially started looking at this because I found that I could not determine the static structure behind `X$MESSAGES` using my [xinfo](/tools.md#xinfo) tool:

```
[oracle@rac1 ~]$ xinfo list 'X$MESSAGES' --with-kqftap
+------------+-----+------------+------------+-----------------+---------+-----+-----+-----+-----+-----------------------------------------------------+
|        obj | ver |    nam_ptr | nam        | xstruct_nam_ptr | xstruct | typ | flg | rsz | coc | kqftap                                              |
+------------+-----+------------+------------+-----------------+---------+-----+-----+-----+-----+-----------------------------------------------------+
| 4294950992 |   3 | 0x14b845e0 | X$MESSAGES |      0x14b845ec | ksbsd   |   1 |   0 |  32 |   6 | {'xstruct_ptr': '0x14a26180', 'xstruct': 'ksbsd_c'} |
+------------+-----+------------+------------+-----------------+---------+-----+-----+-----+-----+-----------------------------------------------------+
```

There are structures such as `ksbsd`/`ksbsd_c` but there is no explicit `ksbsdt`.
`qerfxArrayMaxSize` can be used to identify this missing structure.