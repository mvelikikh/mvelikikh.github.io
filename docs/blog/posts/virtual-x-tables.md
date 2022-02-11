---
categories:
  - Oracle
date:
  created: 2022-02-11T22:16:00
description: >-
  Explain that some X$ tables are not inside the kqftab structure.
  These are called virtual X$ tables and they are built inside the kqfbldtvrt function.
tags:
  - 21c
  - Code symbol
  - X$
---

# Virtual X$ tables

Some X$ tables are not coming from the `kqftab` structure.
Let us find out their origin.

<!-- more -->

It can be seen that the [xinfo](/tools.md#xinfo) tool outputs only 1,272 tables in 21.5, whereas `X$KQFTA` has 1,377 rows:

```
[oracle@db-21 sf_exchange]$ xinfo list -o json |
>   jq -r '.[] | .nam' |
>   awk '{printf "%4d %s\n",NR,$0}'
   1 X$KQFTA
   2 X$KQFVI
   3 X$KQFVT
   4 X$KQFDT
   5 X$KQFCO
..
1271 X$BCAPPLY_STATS
1272 X$FSDDBFS
```

What about extra 105 rows?
Let me show what the output of `X$KQFTA` is like in my database:

```sql hl_lines="10"
SQL> select * from x$kqfta;

ADDR                   INDX    INST_ID     CON_ID   KQFTAOBJ   KQFTAVER KQFTANAM                         KQFTATYP   KQFTAFLG   KQFTARSZ   KQFTACOC
---------------- ---------- ---------- ---------- ---------- ---------- ------------------------------ ---------- ---------- ---------- ----------
0000000016CDBF20          0          1          0 4294950912          6 X$KQFTA                                 4          0         80         11
0000000016CDBF70          1          1          0 4294950913          3 X$KQFVI                                 1          0         80          7
..
0000000016CF4C00       1270          1          0 4294956360          2 X$BCAPPLY_STATS                         4          2        260         16
0000000016CF4C50       1271          1          0 4294956225          2 X$FSDDBFS                               4          0       1144         14
000000008F8127C0       1272          1          0 4294953644          0 X$KSIPC_PROC_STATS                      9         18          0          0
000000008F812810       1273          1          0 4294953645          0 X$KSIPC_INFO                            9         18          0          0
000000008F812860       1274          1          0 4294952215          1 X$KSXPTESTTBL                          10          2        146         15
000000008F8128B0       1275          1          0 4294952216          0 X$KSXP_STATS                            9         18          0          0
000000008F812900       1276          1          0 4294952217          0 X$SKGXP_PORT                            9         18          0          0
000000008F812950       1277          1          0 4294952218          0 X$SKGXP_CONNECTION                      9         18          0          0
000000008F8129A0       1278          1          0 4294952219          0 X$SKGXP_MISC                            9         18          0          0
000000008F8129F0       1279          1          0 4294952227          1 X$KTCNQROW                              9          2       1480         47
..
000000008F8147F0       1375          1          0 4294954950          3 X$DIAG_VTEST_EXISTS                    10         34       1536         13
000000008F814840       1376          1          0 4294954964          3 X$DIAG_VADR_CONTROL                    10         34       1072         21

1377 rows selected.
```

It can be seen that starting at `INDX=1,272` (which is row `1,273` because `INDX` starts at 0) the `ADDR` value is quite different - it is `0x8F8127C0`.
It is not an address from the Oracle binary anymore:

```sql
SQL> select *
  2    from x$ksmsp
  3   where to_number('8F8127C0','XXXXXXXXXXXXXXXX')
  4           between to_number(ksmchptr,'XXXXXXXXXXXXXXXX')
  5               and to_number(ksmchptr,'XXXXXXXXXXXXXXXX') + ksmchsiz - 1;

ADDR                   INDX    INST_ID     CON_ID   KSMCHIDX   KSMCHDUR KSMCHCOM         KSMCHPTR           KSMCHSIZ KSMCHCLS   KSMCHTYP KSMCHPAR
---------------- ---------- ---------- ---------- ---------- ---------- ---------------- ---------------- ---------- -------- ---------- ----------------
00007F6C5E50DC10     106576          1          1          1          1 KQF runtime def  000000008F8127B0       8416 perm              0 000000008F101000
```

The address refers to the `KQF runtime def` area of SGA.
The X$ tables starting from `INDX=1,272` are what Oracle is called virtual tables in its code.
Of course, the `INDX` value is version dependent but these virtual tables always come after other X$ tables defined in `kqftab`.
The starting address of the virtual tables can be obtained from the `kqftvrt_` SGA variable:

```sql
SQL> oradebug dumpvar sga kqftvrt_
struct kqftv* kqftvrt_ [0600A7408, 0600A7410) = 8F8127C0 00000000
```

The virtual tables are built inside the `kqfbldtvrt` function.
