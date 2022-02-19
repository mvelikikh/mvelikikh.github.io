---
categories:
  - Oracle
date:
  created: 2022-02-19T02:31:00
description: >-
  This post demonstrates how to extract X$ table-level callback functions and column definitions.
  The kqftap structure is used for that.
tags:
  - 21c
  - Code symbol
  - X$
---

# X$ tables: table-level callbacks and column definitions (without parsing)

Thus far, I have reviewed the `kqftab` structure which is used to build the majority of tables shown in `X$KQFTA`.
It is not clear yet where actual columns are coming from.
Let us find out in this post.

<!-- more -->

There is an additional structure called `kqftap` that has the extra information.

```
[oracle@db-21 bin]$ readelf -s oracle | grep -E -A1 -w 'Symbol|kqftap' --no-group-separator
Symbol table '.dynsym' contains 225083 entries:
   Num:    Value          Size Type    Bind   Vis      Ndx Name
225049: 0000000016cf4d00 40736 OBJECT  GLOBAL DEFAULT   17 kqftap
225050: 0000000007b02100   256 FUNC    GLOBAL DEFAULT   13 l9_ippsRLEGetInUseTable_8
Symbol table '.symtab' contains 402534 entries:
   Num:    Value          Size Type    Bind   Vis      Ndx Name
351482: 0000000016cf4d00 40736 OBJECT  GLOBAL DEFAULT   17 kqftap
351483: 0000000012aef270   800 FUNC    GLOBAL DEFAULT   14 qesxlGetPayloadData
```

Here is what it looks like:

```
[oracle@db-21 bin]$ objdump -s --start-address=0x0000000016cf4d00 --stop-address=$((0x0000000016cf4d00+40736)) oracle

oracle:     file format elf64-x86-64

Contents of section .rodata:
 16cf4d00 00000000 00000000 00efcf16 00000000  ................
 16cf4d10 7039670e 00000000 00000000 00000000  p9g.............
 16cf4d20 00000000 00000000 00f2cf16 00000000  ................
 16cf4d30 00000000 00000000 00000000 00000000  ................
 16cf4d40 00000000 00000000 00f4cf16 00000000  ................
 16cf4d50 00000000 00000000 00000000 00000000  ................
 16cf4d60 00000000 00000000 80f5cf16 00000000  ................
 16cf4d70 00000000 00000000 00000000 00000000  ................
 16cf4d80 00000000 00000000 80f7cf16 00000000  ................
 16cf4d90 903b670e 00000000 00000000 00000000  .;g.............
..
```

It is made of 32-byte rows.
The third column in the output points to the X$-column structure - the structure describing the corresponding X$ table:

```
[oracle@db-21 bin]$ for a in 16cfef00 16cff200 16cff400 16cff580
> do
>   nm oracle | grep $a
> done
0000000016cfef00 r kqfta_c
0000000016cff200 r kqfvi_c
0000000016cff400 r kqfvt_c
0000000016cff580 r kqfdt_c

[oracle@db-21 ~]$ xinfo list | head -10
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
```

Both `kqftab` and `kqftap` define tables and corresponding column structures in the same order: `X$KQFTA`'s columns are described in `kqfta_c`, `X$KQFVI`'s columns are described in `kqfvi_c`, etc.
Then, some X$ tables require additional processing, so that there are callback functions:

```
[oracle@db-21 bin]$ nm oracle | grep -E 'e673970|e673b90'
000000000e673970 T kqftbl_cb
000000000e673b90 T kqftco
```

The [xinfo](/tools.md#xinfo) tool was enhanced to output the corresponding `kqftap` rows when the `--with-kqftap` option is specified:

```
[oracle@db-21 ~]$ xinfo list 'X$KSMLRU' --with-kqftap -o json
{
  "88": {
    "obj": 4294951099,
    "ver": 7,
    "nam_ptr": 383991380,
    "nam": "X$KSMLRU",
    "xstruct_nam_ptr": 383991392,
    "xstruct": "ksmlr",
    "typ": 4,
    "flg": 0,
    "rsz": 112,
    "coc": 18,
    "kqftap": {
      "xstruct_ptr": 382474144,
      "cb1_ptr": 132689584,
      "xstruct": "ksmlru_c",
      "cb1": "ksmlrs"
    }
  }
}
```

I will explain how to extract the column definitions in the next post.
