---
categories:
  - Oracle
date:
  created: 2019-07-21T18:03:00
description: >-
  An investigation to find out how Oracle calculates hash values for pipes.
  Using Intel Pin Tools and GDB, it is found that Oracle uses the MD5 algorithm.
  Then it is found what input parameters are used, so that it becomes possible to calculate hash values by users.
  This knowledge helps to optimize queries against an extended version of V$DB_PIPES to check if a named pipe exists.
tags:
  - 19c
  - Code symbol
  - X$
---

# V$DB\_PIPES: Unveiling the Truth of Oracle Hash Value

A question about optimizing access to `V$DB_PIPES` just came up recently on [the SQL.RU Oracle database forum](https://www.sql.ru/forum/actualutils.aspx?action=gotomsg&tid=1314456&msg=21921329).
The Topic Starter wanted to find out if there is a way to speed up the query against `V$DB_PIPES`, or there are any other options to see if a named pipe exists.

<!-- more -->

## Initial investigation

So here is the query that was run and its plan:

```sql hl_lines="19"
SQL> explain plan for
  2  select count(*)
  3    from v$db_pipes
  4   where name = 'MY_PIPE';

Explained.

SQL> select * from table(dbms_xplan.display);

PLAN_TABLE_OUTPUT
--------------------------------------------------------------------------------
Plan hash value: 2656999297

-----------------------------------------------------------------------------
| Id  | Operation         | Name    | Rows  | Bytes | Cost (%CPU)| Time     |
-----------------------------------------------------------------------------
|   0 | SELECT STATEMENT  |         |     1 |   148 |     1 (100)| 00:00:01 |
|   1 |  SORT AGGREGATE   |         |     1 |   148 |            |          |
|*  2 |   FIXED TABLE FULL| X$KGLOB |     1 |   148 |     1 (100)| 00:00:01 |
-----------------------------------------------------------------------------

Predicate Information (identified by operation id):

PLAN_TABLE_OUTPUT
--------------------------------------------------------------------------------
---------------------------------------------------

   2 - filter("KGLNAOBJ"='MY_PIPE' AND "KGLHDNSP"=7 AND "KGLOBSTA"<>0
              AND "INST_ID"=USERENV('INSTANCE'))
```

It is seen that `V$DB_PIPES` is built on top of `X$KGLOB`, which is a fixed table.
Obviously, doing a full table scan against it is not the best thing to do, especially when we work with a large enough shared pool.
Fixed tables can have Oracle provided indexes, and `X$KGLOB` has the following ones:

```sql
SQL> select index_number, column_name from v$indexed_fixed_column where table_name='X$KGLOB';

INDEX_NUMBER COLUMN_NAME
------------ ------------
           1 KGLNAHSH
           2 KGLOBT03
```

- `KGLOBT03` is not populated for pipes and it stores the `SQL_ID` of a statement being executed.
- `KGLNAHSH` is a hash value and it seems to store last 4 bytes of `KGLNAHSV` which is a full hash value:
  ```sql
  SQL> select kglnaobj, kglnahsv, kglnahsh, to_char(kglnahsh, 'fm0xxxxxxx') hex_hash, kglhdnsp from x$kglob where kglnaobj in ('MY_PIPE',  'MY_PIPE1', 'MY_PIPE2');

  KGLNAOBJ                       KGLNAHSV                           KGLNAHSH HEX_HASH    KGLHDNSP
  ------------------------------ -------------------------------- ---------- --------- ----------
  MY_PIPE2                       53e58fa645a35847070108600b3043ce  187712462 0b3043ce           7
  MY_PIPE1                       1bb0749b381c19f0dd4d47413a125cc1  974281921 3a125cc1           7
  MY_PIPE                        cdff652a7449f169da313e5685b962d8 2243519192 85b962d8           7
  ```

If I knew a way to calculate the hash value upfront, then I could query `X$KGLOB` passing the hash value as a filter to get an indexed access path:

```sql hl_lines="8 24"
SQL> explain plan for
  2  select count(*)
  3    from x$kglob
  4   where kglnaobj = 'MY_PIPE'
  5     and kglhdnsp = 7
  6     and kglobsta <> 0
  7     and inst_id = userenv('instance')
  8     and kglnahsh = 2243519192;

Explained.

SQL>
SQL> select * from table(dbms_xplan.display);

PLAN_TABLE_OUTPUT
----------------------------------------------------------------------------------------------------
Plan hash value: 2109255596

--------------------------------------------------------------------------------------------
| Id  | Operation                | Name            | Rows  | Bytes | Cost (%CPU)| Time     |
--------------------------------------------------------------------------------------------
|   0 | SELECT STATEMENT         |                 |     1 |   155 |     0   (0)| 00:00:01 |
|   1 |  SORT AGGREGATE          |                 |     1 |   155 |            |          |
|*  2 |   FIXED TABLE FIXED INDEX| X$KGLOB (ind:1) |     1 |   155 |     0   (0)| 00:00:01 |
--------------------------------------------------------------------------------------------

Predicate Information (identified by operation id):

PLAN_TABLE_OUTPUT
----------------------------------------------------------------------------------------------------

   2 - filter("KGLNAHSH"=2243519192 AND "KGLNAOBJ"='MY_PIPE' AND "KGLHDNSP"=7 AND
              "KGLOBSTA"<>0 AND "INST_ID"=USERENV('INSTANCE'))
```

I decided to try to find out how the hash value is calculated.

Firstly, I took the library cache dump:

```
Bucket: #=90840 Mutex=0x6cb2aa60(283467841536, 2, 0, 6)
  LibraryHandle:  Address=0x654cc068 Hash=85b962d8 LockMode=0 PinMode=0 LoadLockMode=0 Status=VALD
    ObjectName:  Name=CDB$ROOT.MY_PIPE
      FullHashValue=cdff652a7449f169da313e5685b962d8 Namespace=PIPE(07) Type=PIPE(18) ContainerId=1 ContainerUid=1 Identifier=0 OwnerIdn=2147483644
    Statistics:  InvalidationCount=0 ExecutionCount=0 LoadCount=1 ActiveLocks=0 TotalLockCount=1 TotalPinCount=1
    Counters:  BrokenCount=1 RevocablePointer=1 KeepDependency=0 Version=0 BucketInUse=0 HandleInUse=0 HandleReferenceCount=0
    Concurrency:  DependencyMutex=0x654cc118(0, 0, 0, 0) Mutex=0x654cc1b8(66, 8, 0, 6)
    Flags=RON/PN0/[10012001] Flags2=[0000]
    WaitersLists:
      Lock=0x654cc0f8[0x654cc0f8,0x654cc0f8]
      Pin=0x654cc0d8[0x654cc0d8,0x654cc0d8]
      LoadLock=0x654cc150[0x654cc150,0x654cc150]
    Timestamp:
    LibraryObject:  Address=0x65f9cb98 HeapMask=0000-0001-0001-0000 Flags=EXS/NRC[0400] Flags2=[0000] Flags3=[0000] PublicFlags=[0000]
```

Based on my knowledge of Oracle internals, I supposed that the hash value should be somehow derived from the name of the object and possibly other attributes of it.
Unfortunately, I was not able to find a proper formula looking into the library cache dump (I was close, in fact, as I was combined the object name with the namespace, however, a proper formula is hard or even near to impossible to come by).
When my first attempts to solve this conundrum failed miserably, I took a break and returned to that task later on.

## Second attempt

That time I took more systematic approach and started by unwrapping the `DBMS_PIPE` package.
I found out that the `DBMS_PIPE.CREATE_PIPE` function calls the `CREATEPIPE` function that has a widely used `INTERFACE` pragma, which roughly means that the function is mapped to another C function within the Oracle kernel.
The function to which `CREATEPIPE` should be mapped should probably be called `kkxpcre` based on [the excellent Dennis Yurichev blog post](https://yurichev.com/blog/50/) (of course, Dennis' post was written a while ago but Oracle has not given much attention to pipes for a while, and I seriously doubt that they have changed that mapping since then).
All of this knowledge appears to be useless at a glance, however, it laid the groundwork for the next step.

The next step of my research started when I was using the DebugTrace program from [Intel Pintools](https://software.intel.com/en-us/articles/pin-a-dynamic-binary-instrumentation-tool).
I ran DebugTrace against the server process in which I created a new pipe named `MY_PIPE` that has the hash value 2243519192 which is `0x85b962d8` in hex.

Here is the relevant output of DebugTrace which I reformatted for brevity (this is the output that I obtained from Oracle 19c, I also got a 12.2 output initially that had a few minor differencies):

``` hl_lines="46"
Call 0x000000000f7775db $ORACLE_HOME/bin/oracle:kkxpcre+0x0000000002db -> 0x000000000b032100 $ORACLE_HOME/bin/oracle:kkxpcrep(0x7f0fd3e6fe80, 0x7, ...)
| Call 0x000000000b03225b $ORACLE_HOME/bin/oracle:kkxpcrep+0x00000000015b -> 0x000000001280c720 $ORACLE_HOME/bin/oracle:kglget(0x7f0fd3f889a0, 0x7fff3aea4d50, ...)
| | Call 0x000000001280c844 $ORACLE_HOME/bin/oracle:kglget+0x000000000124 -> 0x00000000128119f0 $ORACLE_HOME/bin/oracle:kglLock(0x7f0fd3f889a0, 0x7fff3aea4d50, ...)
| | | Call 0x0000000012811b4b $ORACLE_HOME/bin/oracle:kglLock+0x00000000015b -> 0x0000000012815280 $ORACLE_HOME/bin/oracle:kglComputeHash(0x7f0fd3f889a0, 0x7fff3aea4dd0, ...)
| | | Tailcall 0x000000001281528d $ORACLE_HOME/bin/oracle:kglComputeHash+0x00000000000d -> 0x00000000128152b0 $ORACLE_HOME/bin/oracle:kglComputeHash0(0x7f0fd3f889a0, 0x7fff3aea4dd0, ...)
| | | | Call 0x0000000012815399 $ORACLE_HOME/bin/oracle:kglComputeHash0+0x0000000000e9 -> 0x00000000127dca20 $ORACLE_HOME/bin/oracle:kggmd5Update(0x7fff3aea4580, 0x7f0fd3e6fe80, ...)
| | | | | Call 0x00000000127dcad5 $ORACLE_HOME/bin/oracle:kggmd5Update+0x0000000000b5 -> 0x0000000006b74060 $ORACLE_HOME/bin/oracle:_intel_fast_memcpy(0x7fff3aea4588, 0x7f0fd3e6fe80, ...)
| | | | | Tailcall 0x0000000006b740bc $ORACLE_HOME/bin/oracle:_intel_fast_memcpy+0x00000000005c -> 0x0000000006b74030 $ORACLE_HOME/bin/oracle:_intel_fast_memcpy.P(0x7fff3aea4588, 0x7f0fd3e6fe80, ...)
| | | | | Tailcall 0x0000000006b74030 $ORACLE_HOME/bin/oracle:_intel_fast_memcpy.P -> 0x0000000006b814e0 $ORACLE_HOME/bin/oracle:__intel_ssse3_rep_memcpy(0x7fff3aea4588, 0x7f0fd3e6fe80, ...)
| | | | | Return 0x0000000006b83cfa $ORACLE_HOME/bin/oracle:__intel_ssse3_rep_memcpy+0x00000000281a returns: 0x7fff3aea4588
| | | | Return 0x00000000127dcae8 $ORACLE_HOME/bin/oracle:kggmd5Update+0x0000000000c8 returns: 0x7fff3aea4588
| | | | Call 0x000000001281545e $ORACLE_HOME/bin/oracle:kglComputeHash0+0x0000000001ae -> 0x00000000127dca20 $ORACLE_HOME/bin/oracle:kggmd5Update(0x7fff3aea4580, 0x12976914, ...)
| | | | | Call 0x00000000127dcad5 $ORACLE_HOME/bin/oracle:kggmd5Update+0x0000000000b5 -> 0x0000000006b74060 $ORACLE_HOME/bin/oracle:_intel_fast_memcpy(0x7fff3aea458f, 0x12976914, ...)
| | | | | Tailcall 0x0000000006b740bc $ORACLE_HOME/bin/oracle:_intel_fast_memcpy+0x00000000005c -> 0x0000000006b74030 $ORACLE_HOME/bin/oracle:_intel_fast_memcpy.P(0x7fff3aea458f, 0x12976914, ...)
| | | | | Tailcall 0x0000000006b74030 $ORACLE_HOME/bin/oracle:_intel_fast_memcpy.P -> 0x0000000006b814e0 $ORACLE_HOME/bin/oracle:__intel_ssse3_rep_memcpy(0x7fff3aea458f, 0x12976914, ...)
| | | | | Return 0x0000000006b83f95 $ORACLE_HOME/bin/oracle:__intel_ssse3_rep_memcpy+0x000000002ab5 returns: 0x7fff3aea458f
| | | | Return 0x00000000127dcae8 $ORACLE_HOME/bin/oracle:kggmd5Update+0x0000000000c8 returns: 0x7fff3aea458f
| | | | Call 0x000000001281546f $ORACLE_HOME/bin/oracle:kglComputeHash0+0x0000000001bf -> 0x00000000127dca20 $ORACLE_HOME/bin/oracle:kggmd5Update(0x7fff3aea4580, 0x7580764c, ...)
| | | | | Call 0x00000000127dcad5 $ORACLE_HOME/bin/oracle:kggmd5Update+0x0000000000b5 -> 0x0000000006b74060 $ORACLE_HOME/bin/oracle:_intel_fast_memcpy(0x7fff3aea4590, 0x7580764c, ...)
| | | | | Tailcall 0x0000000006b740bc $ORACLE_HOME/bin/oracle:_intel_fast_memcpy+0x00000000005c -> 0x0000000006b74030 $ORACLE_HOME/bin/oracle:_intel_fast_memcpy.P(0x7fff3aea4590, 0x7580764c, ...)
| | | | | Tailcall 0x0000000006b74030 $ORACLE_HOME/bin/oracle:_intel_fast_memcpy.P -> 0x0000000006b814e0 $ORACLE_HOME/bin/oracle:__intel_ssse3_rep_memcpy(0x7fff3aea4590, 0x7580764c, ...)
| | | | | Return 0x0000000006b83c86 $ORACLE_HOME/bin/oracle:__intel_ssse3_rep_memcpy+0x0000000027a6 returns: 0x7fff3aea4590
| | | | Return 0x00000000127dcae8 $ORACLE_HOME/bin/oracle:kggmd5Update+0x0000000000c8 returns: 0x7fff3aea4590
| | | | Call 0x0000000012815415 $ORACLE_HOME/bin/oracle:kglComputeHash0+0x000000000165 -> 0x00000000127dca20 $ORACLE_HOME/bin/oracle:kggmd5Update(0x7fff3aea4580, 0x7fff3aea45f0, ...)
| | | | | Call 0x00000000127dcad5 $ORACLE_HOME/bin/oracle:kggmd5Update+0x0000000000b5 -> 0x0000000006b74060 $ORACLE_HOME/bin/oracle:_intel_fast_memcpy(0x7fff3aea4598, 0x7fff3aea45f0, ...)
| | | | | Tailcall 0x0000000006b740bc $ORACLE_HOME/bin/oracle:_intel_fast_memcpy+0x00000000005c -> 0x0000000006b74030 $ORACLE_HOME/bin/oracle:_intel_fast_memcpy.P(0x7fff3aea4598, 0x7fff3aea45f0, ...)
| | | | | Tailcall 0x0000000006b74030 $ORACLE_HOME/bin/oracle:_intel_fast_memcpy.P -> 0x0000000006b814e0 $ORACLE_HOME/bin/oracle:__intel_ssse3_rep_memcpy(0x7fff3aea4598, 0x7fff3aea45f0, ...)
| | | | | Return 0x0000000006b83726 $ORACLE_HOME/bin/oracle:__intel_ssse3_rep_memcpy+0x000000002246 returns: 0x7fff3aea4598
| | | | Return 0x00000000127dcae8 $ORACLE_HOME/bin/oracle:kggmd5Update+0x0000000000c8 returns: 0x7fff3aea4598
| | | | Call 0x0000000012815423 $ORACLE_HOME/bin/oracle:kglComputeHash0+0x000000000173 -> 0x00000000127dc8b0 $ORACLE_HOME/bin/oracle:kggmd5Finish(0x7fff3aea4580, 0, ...)
| | | | | Call 0x00000000127dc927 $ORACLE_HOME/bin/oracle:kggmd5Finish+0x000000000077 -> 0x00000000127dca20 $ORACLE_HOME/bin/oracle:kggmd5Update(0x7fff3aea4580, 0x14aa6460, ...)
| | | | | | Call 0x00000000127dcad5 $ORACLE_HOME/bin/oracle:kggmd5Update+0x0000000000b5 -> 0x0000000006b74060 $ORACLE_HOME/bin/oracle:_intel_fast_memcpy(0x7fff3aea459c, 0x14aa6460, ...)
| | | | | | Tailcall 0x0000000006b740bc $ORACLE_HOME/bin/oracle:_intel_fast_memcpy+0x00000000005c -> 0x0000000006b74030 $ORACLE_HOME/bin/oracle:_intel_fast_memcpy.P(0x7fff3aea459c, 0x14aa6460, ...)
| | | | | | Tailcall 0x0000000006b74030 $ORACLE_HOME/bin/oracle:_intel_fast_memcpy.P -> 0x0000000006b814e0 $ORACLE_HOME/bin/oracle:__intel_ssse3_rep_memcpy(0x7fff3aea459c, 0x14aa6460, ...)
| | | | | | Return 0x0000000006b83e38 $ORACLE_HOME/bin/oracle:__intel_ssse3_rep_memcpy+0x000000002958 returns: 0x7fff3aea459c
| | | | | Return 0x00000000127dcae8 $ORACLE_HOME/bin/oracle:kggmd5Update+0x0000000000c8 returns: 0x7fff3aea459c
| | | | | Call 0x00000000127dc938 $ORACLE_HOME/bin/oracle:kggmd5Finish+0x000000000088 -> 0x00000000127dca20 $ORACLE_HOME/bin/oracle:kggmd5Update(0x7fff3aea4580, 0x7fff3aea4550, ...)
| | | | | | Call 0x00000000127dcaa4 $ORACLE_HOME/bin/oracle:kggmd5Update+0x000000000084 -> 0x0000000006b74060 $ORACLE_HOME/bin/oracle:_intel_fast_memcpy(0x7fff3aea45c0, 0x7fff3aea4550, ...)
| | | | | | Tailcall 0x0000000006b740bc $ORACLE_HOME/bin/oracle:_intel_fast_memcpy+0x00000000005c -> 0x0000000006b74030 $ORACLE_HOME/bin/oracle:_intel_fast_memcpy.P(0x7fff3aea45c0, 0x7fff3aea4550, ...)
| | | | | | Tailcall 0x0000000006b74030 $ORACLE_HOME/bin/oracle:_intel_fast_memcpy.P -> 0x0000000006b814e0 $ORACLE_HOME/bin/oracle:__intel_ssse3_rep_memcpy(0x7fff3aea45c0, 0x7fff3aea4550, ...)
| | | | | | Return 0x0000000006b83c86 $ORACLE_HOME/bin/oracle:__intel_ssse3_rep_memcpy+0x0000000027a6 returns: 0x7fff3aea45c0
| | | | | | Call 0x00000000127dcab1 $ORACLE_HOME/bin/oracle:kggmd5Update+0x000000000091 -> 0x00000000127dcba0 $ORACLE_HOME/bin/oracle:kggmd5Process(0x7fff3aea4a70, 0x7fff3aea4588, ...)
| | | | | | Return 0x00000000127dd68d $ORACLE_HOME/bin/oracle:kggmd5Process+0x000000000aed returns: 0x66ba4229
| | | | | Return 0x00000000127dcae8 $ORACLE_HOME/bin/oracle:kggmd5Update+0x0000000000c8 returns: 0x66ba4229
| | | | Return 0x00000000127dc94a $ORACLE_HOME/bin/oracle:kggmd5Finish+0x00000000009a returns: 0x66ba4229
| | | Return 0x000000001281543b $ORACLE_HOME/bin/oracle:kglComputeHash0+0x00000000018b returns: 0x85b962d8
```

There are several important observations that can be made about this output:

- `kkxpcre` is a C function mapped to `dbms_pipe.createpipe` through the `INTERFACE` pragma which is called by `dbms_pipe.create_pipe`, which is the only function exposed to public
- `kglComputeHash0` returns that hash value `0x85b962d8` that I am looking for, hence I need to look carefully at what is going on between `kkxpcre` and `kglComputeHash0` as the hash value is somewhere between
- The call stack is: `kkxpcre->kkxpcrep->kglget->kglLock->kglComputeHash->kglComputeHash0`, the latter calls `kggmdUpdate` multiple times, then it calls `kggmd5Finish`, which calls `kggmd5Update` twice.
  The last call to `kggmd5Update` also invokes `kggmd5Process`.
  In terms of Oracle code layers, the code can be split in the following ones:
  `KKX (Programmatic interfaces to/from PL/SQL) -> KGL (Library Cache) -> KGG (Generic Routines)`
- Based on the fact that we call MD5 functions, the underlying alrorithm is used MD5 somehow.

I have also disassembled `kglComputeHash0` to find out how exactly `kggmd5Update` functions are called (this is the first call):

``` hl_lines="2 4 6 8"
   0x0000000012815365 <+181>:   mov    %rax,-0x58(%rbp)
   0x0000000012815369 <+185>:   movl   $0x67452301,(%rax)
   0x000000001281536f <+191>:   mov    -0x58(%rbp),%rcx
   0x0000000012815373 <+195>:   movl   $0xefcdab89,0x4(%rcx)
   0x000000001281537a <+202>:   mov    -0x58(%rbp),%r8
   0x000000001281537e <+206>:   movl   $0x98badcfe,0x8(%r8)
   0x0000000012815386 <+214>:   mov    -0x58(%rbp),%r9
   0x000000001281538a <+218>:   movl   $0x10325476,0xc(%r9)
   0x0000000012815392 <+226>:   mov    0x10(%r14),%rsi
   0x0000000012815396 <+230>:   mov    (%r14),%edx
   0x0000000012815399 <+233>:   callq  0x127dca20 <kggmd5Update>
```

All of those constants: `0x67452301`, `0xefcdab89`, `0x98badcfe`, `0x10325476` - are [magic initialization constants](https://tools.ietf.org/html/rfc1321) in the MD5 algorithm.
Since the algorithm is known, in order to calculate a hash value, I need to know the input values to the MD5 functions.
Thus, I setup a few breakpoints in [GDB](https://www.gnu.org/s/gdb/) and spent a while reviewing the register values.

Finally, I came up with the following GDB breakpoints:

```
set pagination off

break kggmd5Update
  commands
    printf "Length: %d\n",$rdx
    x/8xc $rsi
    c
  end

break kglComputeHash
  commands
    c
  end

break kggmd5Process
  commands
    c
  end

break kggmd5Finish
  commands
    c
  end
```

I attached to the server process through GDB and ran the following command in SQL\*Plus:

```sql
SQL> var n number
SQL> exec :n:=dbms_pipe.create_pipe('MY_PIPE')
```

The debugger output showed this (my comments are inline):

``` hl_lines="5 10 15 20"
Breakpoint 5, 0x0000000012815280 in kglComputeHash ()

Breakpoint 4, 0x00000000127dca20 in kggmd5Update ()
Length: 7
0x7f7b9304ffe0: 77 'M'  89 'Y'  95 '_'  80 'P'  73 'I'  80 'P'  69 'E'  0 '\000'
-- MY_PIPE

Breakpoint 4, 0x00000000127dca20 in kggmd5Update ()
Length: 1
0x12976914:     46 '.'  0 '\000'        0 '\000'        0 '\000'        113 'q' 109 'm' 120 'x' 113 'q'
-- "." (just a dot)

Breakpoint 4, 0x00000000127dca20 in kggmd5Update ()
Length: 8
0x7580c61c:     67 'C'  68 'D'  66 'B'  36 '$'  82 'R'  79 'O'  79 'O'  84 'T'
-- CDB$ROOT

Breakpoint 4, 0x00000000127dca20 in kggmd5Update ()
Length: 4
0x7ffd3203e070: 7 '\a'  0 '\000'        0 '\000'        0 '\000'        0 '\000'        0 '\000'        0 '\000'  0 '\000'
-- 0x07000000 or chr(7)||chr(0)||chr(0)||chr(0)

Breakpoint 7, 0x00000000127dc8b0 in kggmd5Finish ()

Breakpoint 4, 0x00000000127dca20 in kggmd5Update ()
Length: 36
0x14aa6460 <kggmd5padding>:     -128 '\200'     0 '\000'        0 '\000'        0 '\000'        0 '\000'        0 '\000'   0 '\000'        0 '\000'

Breakpoint 4, 0x00000000127dca20 in kggmd5Update ()
Length: 8
0x7ffd3203dfd0: -96 '\240'      0 '\000'        0 '\000'        0 '\000'        0 '\000'        0 '\000'        0 '\000'   0 '\000'

Breakpoint 6, 0x00000000127dcba0 in kggmd5Process ()
```

Let me explain what this output means.
In accordance with: [System V ABI AMD64](http://refspecs.linuxfoundation.org/elf/x86_64-abi-0.99.pdf), the function parameters passed as follows (page 21):

- `%rdi` - first argument to functions
- `%rsi` - second argument to functions
- `%rdx` - third argument to functions

While I was looking at those registers, I produced a hypothesis that `kggmd5Update` has the signature similar to the one mentioned in [RFC-1321: The MD5 Message-Digest Algorithm](https://tools.ietf.org/html/rfc1321):

```
/* MD5 block update operation. Continues an MD5 message-digest
  operation, processing another message block, and updating the
  context.
 */
void MD5Update (context, input, inputLen)
MD5_CTX *context;                                        /* context */
unsigned char *input;                                /* input block */
unsigned int inputLen;                     /* length of input block */
```

As such, I was not really interested in the context variable - it holds the address of the context structure.
The second and third parameters, though, should hold the input string and its length, that is what I was getting in my GDB breakpoint (remember, that `rsi` and `rdx` are second and third parameters correspondingly):

```
break kggmd5Update
  commands
    printf "Length: %d\n",$rdx
    x/8xc $rsi
    c
  end
```

First three calls in the GDB output are self-explanatory: it is a string `MY_PIPE.CDB$ROOT`.
The last call requires a bit of explanation, though: what is `0x07000000`?
It seems to be the namespace, which is 7 for pipes (`X$KGLOB.KGLHDNSP`), with 3 trailing zero bytes.

I calculated MD5 hashes based on that formula and got this:

```sql
SQL> select dbms_crypto.hash(rawtohex('MY_PIPE1.CDB$ROOT'||chr(7)||chr(0)||chr(0)||chr(0)), 2) md5 from dual;

MD5
--------------------------------
9B74B01BF0191C3841474DDDC15C123A

SQL> select dbms_crypto.hash(rawtohex('MY_PIPE2.CDB$ROOT'||chr(7)||chr(0)||chr(0)||chr(0)), 2) md5 from dual;

MD5
--------------------------------
A68FE5534758A34560080107CE43300B

SQL> select dbms_crypto.hash(rawtohex('MY_PIPE.CDB$ROOT'||chr(7)||chr(0)||chr(0)||chr(0)), 2) md5 from dual;

MD5
--------------------------------
2A65FFCD69F14974563E31DAD862B985
```

Whereas the actual hashes were these:

```sql
SQL> select kglnaobj, kglnahsv, kglnahsh, to_char(kglnahsh, 'fm0xxxxxxx') hex_hash, kglhdnsp from x$kglob where kglnaobj in ('MY_PIPE',  'MY_PIPE1', 'MY_PIPE2');

KGLNAOBJ                       KGLNAHSV                           KGLNAHSH HEX_HASH    KGLHDNSP
------------------------------ -------------------------------- ---------- --------- ----------
MY_PIPE2                       53e58fa645a35847070108600b3043ce  187712462 0b3043ce           7
MY_PIPE1                       1bb0749b381c19f0dd4d47413a125cc1  974281921 3a125cc1           7
MY_PIPE                        cdff652a7449f169da313e5685b962d8 2243519192 85b962d8           7
```

Then it dawned on me that Oracle uses the same technique for these hashes as it uses for `SQL_ID`: [Function to compute SQL\_ID out of SQL\_TEXT](https://carlos-sierra.net/2013/09/12/function-to-compute-sql_id-out-of-sql_text/) - it reverses the order of each 4 bytes.
Look:

```sql hl_lines="20 21 22"
SQL> with pipes(pipe_name) as (
  2    select 'MY_PIPE' from dual union all
  3    select 'MY_PIPE1' from dual union all
  4    select 'MY_PIPE2' from dual
  5  )
  6  select pipe_name,
  7         utl_raw.concat(
  8           utl_raw.reverse(utl_raw.substr(hv, 1, 4)),
  9           utl_raw.reverse(utl_raw.substr(hv, 5, 4)),
 10           utl_raw.reverse(utl_raw.substr(hv, 9, 4)),
 11           utl_raw.reverse(utl_raw.substr(hv, 13, 4))
 12         ) ora_hash_value
 13    from (select pipe_name,
 14                 dbms_crypto.hash(rawtohex(pipe_name||'.CDB$ROOT'||chr(7)||chr(0)||chr(0)||chr(0)), 2) hv
 15            from pipes)
 16   order by pipe_name;

PIPE_NAM ORA_HASH_VALUE
-------- --------------------------------
MY_PIPE  CDFF652A7449F169DA313E5685B962D8
MY_PIPE1 1BB0749B381C19F0DD4D47413A125CC1
MY_PIPE2 53E58FA645A35847070108600B3043CE
```

These are exactly the values I was looking for!


## tl;dr

- The pipe *full hash value* can be calculated as below (where `ORA_HASH_VALUE` is the hash that I calculated based on the research made in this article):
  ```sql
  SQL> select lower(rawtohex(utl_raw.concat(
    2           utl_raw.reverse(utl_raw.substr(hv, 1, 4)),
    3           utl_raw.reverse(utl_raw.substr(hv, 5, 4)),
    4           utl_raw.reverse(utl_raw.substr(hv, 9, 4)),
    5           utl_raw.reverse(utl_raw.substr(hv, 13, 4))
    6         ))) ora_hash_value,
    7         kglnahsv, kglnahsh, hex_hash, kglhdnsp, kglhdnsd, kglnacon, kglnaown, kglnaobj
    8    from (select dbms_crypto.hash(rawtohex(kglnaobj||'.'||kglnacon||chr(kglhdnsp)||chr(0)||chr(0)||chr(0)), 2) hv,
    9                 kglnahsv, kglnahsh, to_char(kglnahsh, 'fm0xxxxxxx') hex_hash,
   10                 kglhdnsp, kglhdnsd, kglnacon, kglnaown, kglnaobj
   11            from x$kglob t
   12           where kglhdnsp = 7)
   13   order by kglnaobj
   14  /

  ORA_HASH_VALUE                   KGLNAHSV                           KGLNAHSH HEX_HASH    KGLHDNSP KGLHDNSD KGLNACON KGLNAOWN KGLNAOBJ
  -------------------------------- -------------------------------- ---------- --------- ---------- -------- -------- -------- --------
  cdff652a7449f169da313e5685b962d8 cdff652a7449f169da313e5685b962d8 2243519192 85b962d8           7 PIPE     CDB$ROOT          MY_PIPE
  1bb0749b381c19f0dd4d47413a125cc1 1bb0749b381c19f0dd4d47413a125cc1  974281921 3a125cc1           7 PIPE     CDB$ROOT          MY_PIPE1
  53e58fa645a35847070108600b3043ce 53e58fa645a35847070108600b3043ce  187712462 0b3043ce           7 PIPE     CDB$ROOT          MY_PIPE2
  ```

  1. We take: `<PIPE_NAME>.<CONTAINER_NAME> chr(7) chr(0) chr(0) chr(0)`.
  1. Compute an MD5 hash of it.
  1. Then the order of each 4 bytes is reversed and the final output is assembled.
  1. If you are interested in the numeric hash value, which is `X$KGLOB.KGLNAHSH`, you need to take last 4 bytes of *the full hash value*, which is `X$KGLOB.KGLNAHSV`.
  1. I do not consider the non-CDB architecture due to its deprecation but the general pattern should be applicable to it as well.

- Due to the fact that `V$DB_PIPES` does not expose the hash value, it is a good idea to create an extended version of that view including the hash value, since we now know how to calculate it (legal disclaimer: that is just my opinion).
  After all, Oracle has provided functions to calculate the `SQL_ID`.
  They might provide similar functions to calculate hash values one day.
