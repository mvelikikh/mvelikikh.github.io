---
categories:
  - Oracle
date:
  created: 2015-02-09T12:47:00
  updated: 2016-05-14T12:32:18
description: >-
  How to suspend a user session on a specific Oracle enqueue using DTrace
tags:
  - 11g
  - Code symbol
  - Diagnostic event
  - OS
  - X$
---

# Suspending user session on specific enqueue

Recently I faced a strange issue with EBR (Edition-Based Redefinition).
In order to understand how things work internally I decided to use DTrace.

<!-- more -->

I wanted to suspend a specific user session when the session acquired an AE (Edition enqueue) lock.
There is a similar `enq_trace.sh` script that was written by [Tanel Poder](http://blog.tanelpoder.com).
Tanel's script could be extended to accommodate to my specific requirements if needed.

## `enq_suspend.d` script { #script }

My `enq_suspend.d` script with code annotations is below:

```c { .annotate }
#!/usr/sbin/dtrace -s
/*(1)!*/
#pragma D option quiet
#pragma D option destructive
/*(2)!*/
struct ksqrs_t {
  long     addr;
  char     b1[72];
  uint32_t id1;/*(3)!*/
  uint32_t id2;
  char     b2[4];
  char     idt[2];/*92=offset of X$KSQRS.KSQRSIDT column from x$kqfco*/
  char     b3[18];
};

struct ksqrs_t ksqrs;
/*(4)!*/
pid$target:oracle:ksqgtl*:entry
{
  ksqeq_lkadr = arg0; /* X$KSQEQ.KSQLKADR*/
  mode = arg1;
  timeout = arg3;
  lock_indx = arg4; /*X$KSIRESTYP.INDX*/
  flags = arg7;
}
/*(5)!*/
pid$target:oracle:ksqgtl*:return
{
  ksqeq_lkres = *(long *)copyin(ksqeq_lkadr+8,8);
  ksqrs = *(struct ksqrs_t *)copyin(ksqeq_lkres,112);
  ksqrs.addr = ksqeq_lkres;
  printf("%d [%Y] %s: *** %s-%08x-%08x mode=%d flags=0x%x timeout=%d\n",
    timestamp,
    walltimestamp,
    probefunc,
    ksqrs.idt,
    ksqrs.id1,
    ksqrs.id2,
    mode,
    flags,
    timeout
  );
}
/*(6)!*/
pid$target:oracle:ksqrcl*:entry
{
  enqrs_addr = *(long *)copyin(arg0+8,8); /*X$KSQRS.ADDR enQueue Resource*/
  ksqrs = *(struct ksqrs_t *)copyin(enqrs_addr, 112);
  ksqrs.addr = enqrs_addr;
  printf("%d [%Y] %s: *** %s-%08x-%08x x$ksqrs.addr=0x%016x\n",
    timestamp,
    walltimestamp,
    probefunc,
    ksqrs.idt,
    ksqrs.id1,
    ksqrs.id2,
    ksqrs.addr
  );
}
/*(7)!*/
pid$target:oracle:ksqrcl*:entry
/ksqrs.idt==$$1/
{
  printf("%d [%Y] %s.%s: lock_type=%s suspending execution\n", timestamp, walltimestamp, probefunc, probename, ksqrs.idt);
  stop();
}

pid$target:oracle:ksqrcl*:return {}
```

1. The pragmas are to minimize output and to allow destructive actions.
   We will use the `stop()` action further that is considered destructive.

2. The structure describes an `X$KSQRS` row (Kernel Services enQueue ReSource):
   ```sql hl_lines="17 18 19"
   SQL> select c.kqfconam column_name,
     2         c.kqfcodty datatype,
     3         c.kqfcosiz size_byte,
     4         c.kqfcooff offset
     5    from x$kqfta t,
     6         x$kqfco c
     7   where t.kqftanam = 'X$KSQRS'
     8     and c.kqfcotab = t.indx
     9   order by c.indx
    10  /

   COLUMN_NAME   DATATYPE  SIZE_BYTE     OFFSET
   ----------- ---------- ---------- ----------
   ADDR                23          8          0
   INDX                 2          4          0
   INST_ID              2          4          0
   KSQRSID1             2          4         80
   KSQRSID2             2          4         84
   KSQRSIDT             1          2         92
   KSQRSFLG             2          1        111
   ```

3. ID1, ID2, IDT columns maps to the relevant `GV$LOCK` columns. This can be obtained from `V$FIXED_VIEW_DEFINITION`:
   ```sql
   select s.inst_id,
          l.laddr,
          l.kaddr,
          s.ksusenum,
          r.ksqrsidt,
          r.ksqrsid1,
          r.ksqrsid2,
          l.lmode,
          l.request,
          l.ctime,
          decode(l.lmode,0,0,l.block)
     from v$_lock l,
          x$ksuse s,
          x$ksqrs r
    where l.saddr=s.addr
      and concat(USERENV('Instance'),l.raddr)=concat(r.inst_id,r.addr)
   ```

4. `ksqgtl*.entry` - get the lock function, entry point.
   Interesting `ksqgtl` function arguments saved for further usage.
   In particularly, `arg0` - is `X$KSQEQ.KSQLKADR` (lock address?).


5. `ksqgtl*.return` - get lock function, return.
    We are interested in "ID1", "ID2", "TYPE" lock attributes.
    We can fully decode them from the `X$KSQRS` fixed table.
    But `ksqgtl` is called with `X$KSQEQ.KSQLKADR`.
    `X$KSQEQ.KSQLKRES` maps to `X$KSQRS.ADDR`.
    ```sql hl_lines="19 20"
    SQL> select c.kqfconam column_name,
      2         c.kqfcodty datatype,
      3         c.kqfcosiz size_byte,
      4         c.kqfcooff offset
      5    from x$kqfta t,
      6         x$kqfco c
      7   where t.kqftanam = 'X$KSQEQ'
      8     and c.kqfcotab = t.indx
      9   order by c.indx
     10  /

    COLUMN_NAME   DATATYPE  SIZE_BYTE     OFFSET
    ----------- ---------- ---------- ----------
    ADDR                23          8          0
    INDX                 2          4          0
    INST_ID              2          4          0
    KSSOBFLG             2          4          0
    KSSOBOWN            23          8          0
    KSQLKADR            23          8         88
    KSQLKRES            23          8         96
    KSQLKMOD             2          1        176
    KSQLKREQ             2          1        177
    KSQLKMXH             2          2        178
    KSQLKSES            23          8          0
    KSQLKCTIM            2          4          0
    KSQLKLBLK            2          4          0
    ```
    We will print debug output similar to Tanel's script and event 10704 format.

6. `ksqrcl` function (release lock) entry point.
    We will populate the `ksqrs` struct again.

7. If the lock type equals to the parameter passed to script, we will suspend process execution using `stop()`

## Demonstration

Short demonstration of how this works.
Suppose I would like to suspend the server process when a session acquires a TM lock.

1. I open a new database session and determine its server process ID along with the tracefile location:

    ```sql
    SQL> select p.spid,
      2         p.tracefile
      3    from v$session s,
      4         v$process p
      5   where s.sid = sys_context( 'userenv', 'sid')
      6     and p.addr = s.paddr
      7  /

    SPID  TRACEFILE
    ----- ----------------------------------------------------------------------------------------------------
    1968  /pub/home/oracle/diag/rdbms/orcl/orcl/trace/orcl_ora_1968.trc
    ```

2. I create a test table and get its object ID in hex. The event 10704 trace file uses hexadecimal output:

    ```sql
    SQL> create table t (x int);

    Table created.
    SQL> select object_id,
      2         to_char(object_id, 'fm0xxxxxxx') object_id_hex
      3    from obj
      4   where object_name='T';

     OBJECT_ID OBJECT_ID_HEX
    ---------- ---------------------------
        349673 000555e9
    ```

3. Now I enable additional diagnostics - event 10704 to trace enqueues:

    ```sql
    SQL> alter session set events '10704 level 2';

    Session altered.
    ```

4. Next I run the DTrace script [enq\_suspend.d](#script) passing the session's server process ID and TM enqueue as parameters:

    ```bash
    oracle@localhost dtrace$ ./enq_suspend.d -p 1968 TM
    ```

5. Try to truncate table T (the command gets hung):

    ```sql
    truncate table t;
    ```

6. Observed the following output into the console with the DTrace script running:

    ``` hl_lines="6 7"
    oracle@localhost dtrace$ ./enq_suspend.d -p 1968 TM
    33969273235645237 [2015 Feb  9 12:42:21] ksqgtlctx: *** TM-000555e9-00000000 mode=6 flags=0x401 timeout=0
    33969273240887878 [2015 Feb  9 12:42:21] ksqgtlctx: *** TX-0004001b-0000f92e mode=6 flags=0x401 timeout=0
    33969273245689382 [2015 Feb  9 12:42:21] ksqrcl: *** TX-0004001b-0000f92e x$ksqrs.addr=0x000000041cda5c90
    33969273245764458 [2015 Feb  9 12:42:21] ksqrcli: *** TX-0004001b-0000f92e x$ksqrs.addr=0x000000041cda5c90
    33969273246279405 [2015 Feb  9 12:42:21] ksqrcl: *** TM-000555e9-00000000 x$ksqrs.addr=0x000000041cda25d0
    33969273246301204 [2015 Feb  9 12:42:21] ksqrcl.entry: lock_type=TM suspending execution
    ```

     It can be seen that when calling `ksqrcl` with `TM-000555e9-00000000` (the object ID) the execution gets suspended.
     Any additional diagnostics can be gathered at this step.

7. event 10704 data in the trace file:

    ```
    *** 2015-02-09 12:42:21.102
    ksqgtl *** TM-000555e9-00000000 mode=6 flags=0x401 timeout=0 ***
    ksqgtl: xcb=0x419a6f068, ktcdix=2147483647, topxcb=0x419a6f068
            ktcipt(topxcb)=0x0
    ksucti: init txn DID from session DID
    ksqgtl:
            ksqlkdid: 0001-0019-00000142
    *** ksudidTrace: ksqgtl
            ktcmydid(): 0001-0019-00000142
            ksusesdi:   0001-0019-00000143
            ksusetxn:   0001-0019-00000142
    ksqgtl: RETURNS 0
    ksqgtl *** TX-0004001b-0000f92e mode=6 flags=0x401 timeout=0 ***
    ksqgtl: xcb=0x419a6f068, ktcdix=2147483647, topxcb=0x419a6f068
            ktcipt(topxcb)=0x0
    ksucti: init session DID from txn DID:
    ksqgtl:
            ksqlkdid: 0001-0019-00000142
    *** ksudidTrace: ksqgtl
            ktcmydid(): 0001-0019-00000142
            ksusesdi:   0001-0019-00000143
            ksusetxn:   0001-0019-00000142
    ksqgtl: RETURNS 0
    ksqrcl: TX,4001b,f92e
    ksqrcl: returns 0
    ```

## Summary

[enq\_suspend.d](#script) script can be further extending for more complex conditions: such as stopping the execution when a session acquires a TM lock with a particular object ID and mode, and so on.
The script was verified in my environment: Oracle Database version 11.2.0.3 on Solaris 10 SPARC64.
