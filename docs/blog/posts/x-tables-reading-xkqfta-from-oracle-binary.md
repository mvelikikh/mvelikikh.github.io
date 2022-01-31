---
categories:
  - Oracle
date:
  created: 2022-01-31T17:01:00
description: >-
  Explaining how to read the `X$KQFTA` structure listing X$ tables from the Oracle binary.
  Demonstrate how to dereference the symbols, and then introduce xinfo - a tool that can do the same.
tags:
  - 21c
  - Code symbol
  - X$
---

# X$ tables: reading X$KQFTA from Oracle binary

Explaining how to read the `X$KQFTA` structure listing X$ tables.

<!-- more -->

X$ tables are visible in `X$KQFTA`, for example:

```sql
SQL> select * from x$kqfta where rownum<=10;

ADDR                   INDX    INST_ID     CON_ID   KQFTAOBJ   KQFTAVER KQFTANAM       KQFTATYP   KQFTAFLG   KQFTARSZ   KQFTACOC
---------------- ---------- ---------- ---------- ---------- ---------- ------------ ---------- ---------- ---------- ----------
0000000016CDBF20          0          1          0 4294950912          6 X$KQFTA               4          0         80         11
0000000016CDBF70          1          1          0 4294950913          3 X$KQFVI               1          0         80          7
0000000016CDBFC0          2          1          0 4294951149          3 X$KQFVT               1          0         32          5
0000000016CDC010          3          1          0 4294950914          4 X$KQFDT               1          0         40          7
0000000016CDC060          4          1          0 4294951036          6 X$KQFCO               4          2         80         17
0000000016CDC0B0          5          1          0 4294952712          2 X$KQFOPT              1          0         24          6
0000000016CDC100          6          1          0 4294952922          3 X$KYWMPCTAB           4          0         88         12
0000000016CDC150          7          1          0 4294953009          2 X$KYWMWRCTAB          4          0         72          6
0000000016CDC1A0          8          1          0 4294952923          2 X$KYWMCLTAB           4          0       4076          7
0000000016CDC1F0          9          1          0 4294952924          5 X$KYWMNF              4          0        240         11
```

This information is mostly coming from the `kqftab` structure within the Oracle binary:

```
[oracle@db-21 bin]$ readelf -s oracle | grep -E -A1 -w 'Symbol|kqftab' --no-group-separator
Symbol table '.dynsym' contains 225083 entries:
   Num:    Value          Size Type    Bind   Vis      Ndx Name
224955: 0000000016cdbf20 0x18dd0 OBJECT  GLOBAL DEFAULT   17 kqftab
224956: 00000000058400a0   288 FUNC    GLOBAL DEFAULT   13 kole_length
Symbol table '.symtab' contains 402534 entries:
   Num:    Value          Size Type    Bind   Vis      Ndx Name
344560: 0000000016cdbf20 0x18dd0 OBJECT  GLOBAL DEFAULT   17 kqftab
344561: 0000000016bc7a98    40 OBJECT  GLOBAL DEFAULT   17 kqreqv
```

This is the actual `kqftab` structure:

``` hl_lines="6 11 16"
[oracle@db-21 bin]$ objdump -s --start-address=0x0000000016cdbf20 --stop-address=$((0x0000000016cdbf20+0x18dd0)) oracle

oracle:     file format elf64-x86-64

Contents of section .rodata:
 16cdbf20 07000000 00000000 80f52c16 00000000  ..........,.....
 16cdbf30 05000000 00000000 703be816 00000000  ........p;......
 16cdbf40 04000000 00000000 50000000 00000000  ........P.......
 16cdbf50 00000000 00000000 0b000000 02000000  ................
 16cdbf60 00c0ffff 06000000 00000000 00000000  ................
 16cdbf70 07000000 00000000 783be816 00000000  ........x;......
 16cdbf80 05000000 00000000 703be816 00000000  ........p;......
 16cdbf90 01000000 00000000 50000000 00000000  ........P.......
 16cdbfa0 00000000 00000000 07000000 00000000  ................
 16cdbfb0 01c0ffff 03000000 00000000 00000000  ................
 16cdbfc0 07000000 00000000 803be816 00000000  .........;......
 16cdbfd0 05000000 00000000 883be816 00000000  .........;......
 16cdbfe0 01000000 00000000 20000000 00000000  ........ .......
 16cdbff0 00000000 00000000 05000000 00000000  ................
 16cdc000 edc0ffff 03000000 00000000 00000000  ................
...
```

There is a visible pattern in this data.
The highlighted lines contain some addresses which can be easily dereferenced:

``` hl_lines="9 14 19"
[oracle@db-21 bin]$ for a in 162cf580 16e83b78 16e83b80
> do
>   objdump -s --start-address=0x$a --stop-address=$((0x$a+16)) oracle
> done

oracle:     file format elf64-x86-64

Contents of section .rodata:
 162cf580 58244b51 46544100 716b736f 7050726f  X$KQFTA.qksopPro

oracle:     file format elf64-x86-64

Contents of section .rodata:
 16e83b78 58244b51 46564900 58244b51 46565400  X$KQFVI.X$KQFVT.

oracle:     file format elf64-x86-64

Contents of section .rodata:
 16e83b80 58244b51 46565400 6b716674 70000000  X$KQFVT.kqftp...
```

Not surprisingly, the order of tables is the same as in `X$KQFTA`.
It made me think that the structure `kqftab` can be used to construct an output similar to `X$KQFTA`.
That is why I wrote a program [xinfo](/tools.md#xinfo) that reads the Oracle binary and does just that:

```
[oracle@db-21 ~]$ xinfo list
+------------+-----+------------+-------------------------------+-----------------+---------------------------+-----+------+--------+-----+
|        obj | ver |    nam_ptr | nam                           | xstruct_nam_ptr | xstruct                   | typ |  flg |    rsz | coc |
+------------+-----+------------+-------------------------------+-----------------+---------------------------+-----+------+--------+-----+
| 4294950912 |   6 | 0x16282d00 | X$KQFTA                       |      0x16e33810 | kqftv                     |   4 |    0 |     80 |  11 |
| 4294950913 |   3 | 0x16e33818 | X$KQFVI                       |      0x16e33810 | kqftv                     |   1 |    0 |     80 |   7 |
| 4294951149 |   3 | 0x16e33820 | X$KQFVT                       |      0x16e33828 | kqftp                     |   1 |    0 |     32 |   5 |
| 4294950914 |   4 | 0x16e33830 | X$KQFDT                       |      0x16e33838 | kqfdt                     |   1 |    0 |     40 |   7 |
| 4294951036 |   6 | 0x16e33840 | X$KQFCO                       |      0x16e33848 | kqfcc                     |   4 |    2 |     80 |  17 |
| 4294952712 |   2 | 0x16e33850 | X$KQFOPT                      |      0x16e3385c | kqfopt                    |   1 |    0 |     24 |   6 |
| 4294952922 |   3 | 0x16e33864 | X$KYWMPCTAB                   |      0x16e33870 | kywmpctab                 |   4 |    0 |     88 |  12 |
| 4294953009 |   2 | 0x16e3387c | X$KYWMWRCTAB                  |      0x16e3388c | kywmwrctab                |   4 |    0 |     72 |   6 |
| 4294952923 |   2 | 0x16e33898 | X$KYWMCLTAB                   |      0x16e338a4 | kywmcltab                 |   4 |    0 |   4076 |   7 |
| 4294952924 |   5 | 0x16e338b0 | X$KYWMNF                      |      0x16e338bc | kywmnf                    |   4 |    0 |    240 |  11 |
...
| 4294956357 |   2 | 0x16e3a834 | X$CONSENSUS_STATS             |      0x16e3a848 | kconsstats                |   4 |    2 |     64 |  10 |
| 4294956360 |   2 | 0x16e3a854 | X$BCAPPLY_STATS               |      0x16e3a864 | kbbaStats                 |   4 |    2 |    260 |  16 |
| 4294956225 |   2 | 0x16e3a870 | X$FSDDBFS                     |      0x16e3a87c | fsddbfs                   |   4 |    0 |   1144 |  14 |
+------------+-----+------------+-------------------------------+-----------------+---------------------------+-----+------+--------+-----+

[oracle@db-21 ~]$ xinfo list 'X$KCCC*'
+------------+-----+------------+---------+-----------------+---------+-----+-----+-----+-----+
|        obj | ver |    nam_ptr | nam     | xstruct_nam_ptr | xstruct | typ | flg | rsz | coc |
+------------+-----+------------+---------+-----------------+---------+-----+-----+-----+-----+
| 4294951110 |   5 | 0x16e3553c | X$KCCCF |      0x16e35544 | kcccf   |   4 |   0 | 532 |   9 |
| 4294951215 |   4 | 0x16e3567c | X$KCCCC |      0x16e35684 | kcccc   |   5 |   6 |  48 |  14 |
| 4294951392 |   5 | 0x16e35d90 | X$KCCCP |      0x16e35d98 | kctcpx  |   5 |   0 | 552 |  25 |
+------------+-----+------------+---------+-----------------+---------+-----+-----+-----+-----+
```

I also make use of other information that is stored in `kqftab` and add a column called `xstruct` to the output.
