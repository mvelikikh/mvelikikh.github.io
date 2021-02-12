---
categories:
  - Oracle
date:
  created: 2021-02-12T22:39:00
description: >-
  Demonstrate how to use _kgl_debug=32 to trace library cache locks.
  The result trace file has XML data that is also loaded in the database for analysis.
tags:
  - 19c
  - Code symbol
  - Initialization parameter
---

# Tracing Library Cache Locks Using \_kgl\_debug

[A recent blog post](https://nenadnoveljic.com/blog/library-cache-lock-debugger/) from Nenad Noveljic prompted me to review the library cache tracing facilities available in Oracle database.

<!-- more -->

## Demonstration

After a bit of tinkering I discovered the actual library cache lock tracing is governed by the `_kgl_debug` parameter.
Here is a little sample code to demonstrate that - I borrowed part of it from [the excellent Nenad's blog post](https://nenadnoveljic.com/blog/library-cache-lock-debugger/):

```sql hl_lines="14"
SQL> create table t (n1 integer,n2 integer);

Table created.

SQL> create index ix_t on t(n1,n2);

Index created.

SQL> exec dbms_stats.gather_table_stats ('', 'T', cascade => true)

PL/SQL procedure successfully completed.

SQL>
SQL> alter system set "_kgl_debug"=32 scope=memory;

System altered.

SQL>
SQL> alter index ix_t invisible ;

Index altered.
```

In a nutshell, `_kgl_debug=32` appears to result in writing information about library cache locks in the trace file.
Here is how it looks:

```sql
SQL> col trace_file old_v tf for a72
SQL> col dirname old_v dn for a50
SQL> col basename old_v bn for a21
SQL>
SQL> select value trace_file,
  2         substr(value, 1, instr(value, '/', -1)-1) dirname,
  3         substr(value, instr(value, '/', -1)+1) basename
  4    from v$diag_info
  5   where name='Default Trace File';

TRACE_FILE                                                               DIRNAME                                            BASENAME
------------------------------------------------------------------------ -------------------------------------------------- ---------------------
/u01/app/oracle/diag/rdbms/racdba/racdba1/trace/racdba1_ora_16440.trc    /u01/app/oracle/diag/rdbms/racdba/racdba1/trace    racdba1_ora_16440.trc

SQL>
SQL> ho tail -64 &tf.
    <Mode>N</Mode>
  </LibraryObjectLock>
</KGLTRACE>
<KGLTRACE>
  <Timestamp>2021-02-12 15:41:23.656</Timestamp>
  <SID>136</SID>
  <Function>kglLock</Function>
  <Reason>TRACELOCK</Reason>
  <Param1>0x706c20e0</Param1>
  <Param2>1</Param2>
  <LibraryHandle>
    <Address>0x67f78888</Address>
    <Hash>94e2179b</Hash>
    <LockMode>N</LockMode>
    <PinMode>0</PinMode>
    <LoadLockMode>0</LoadLockMode>
    <Status>VALD</Status>
    <ObjectName>
      <Name>select value trace_file,
       substr(value, 1, instr(value, '/', -1)-1) dirname,
       substr(value, instr(value, '/', -1)+1) basename
  from v$diag_info
 where name='Default Trace File'</Name>
      <FullHashValue>8c302f585b9b9a83239f686f94e2179b</FullHashValue>
      <Namespace>SQL AREA(00)</Namespace>
      <Type>CURSOR(00)</Type>
      <ContainerId>1</ContainerId>
      <ContainerUid>1</ContainerUid>
      <Identifier>2497845147</Identifier>
      <OwnerIdn>89</OwnerIdn>
    </ObjectName>
  </LibraryHandle>
  <LibraryObjectLock>
    <Address>0x706c20e0</Address>
    <Handle>0x67f78888</Handle>
    <Mode>N</Mode>
  </LibraryObjectLock>
</KGLTRACE>
<KGLTRACE>
  <Timestamp>2021-02-12 15:41:23.657</Timestamp>
  <SID>136</SID>
  <Function>kgllkal</Function>
  <Reason>TRACELOCK</Reason>
  <Param1>0x706c1ff8</Param1>
  <Param2>0</Param2>
  <LibraryHandle>
    <Address>0x67f78328</Address>
    <Hash>0</Hash>
    <LockMode>N</LockMode>
    <PinMode>0</PinMode>
    <LoadLockMode>0</LoadLockMode>
    <Status>VALD</Status>
    <Name>
      <Namespace>SQL AREA(00)</Namespace>
      <Type>CURSOR(00)</Type>
      <ContainerId>3</ContainerId>
    </Name>
  </LibraryHandle>
  <LibraryObjectLock>
    <Address>0x706c1ff8</Address>
    <Handle>0x67f78328</Handle>
    <Mode>N</Mode>
  </LibraryObjectLock>
</KGLTRACE>
```

It is quite convenient that the trace data is provided in XML, such as follows:

```xml
<KGLTRACE>
  <Timestamp>2021-02-12 15:41:23.656</Timestamp>
  <SID>136</SID>
  <Function>kglLock</Function>
  <Reason>TRACELOCK</Reason>
  <Param1>0x706c20e0</Param1>
  <Param2>1</Param2>
  <LibraryHandle>
    <Address>0x67f78888</Address>
    <Hash>94e2179b</Hash>
    <LockMode>N</LockMode>
    <PinMode>0</PinMode>
    <LoadLockMode>0</LoadLockMode>
    <Status>VALD</Status>
    <ObjectName>
      <Name>select value trace_file,
       substr(value, 1, instr(value, '/', -1)-1) dirname,
       substr(value, instr(value, '/', -1)+1) basename
  from v$diag_info
 where name='Default Trace File'</Name>
      <FullHashValue>8c302f585b9b9a83239f686f94e2179b</FullHashValue>
      <Namespace>SQL AREA(00)</Namespace>
      <Type>CURSOR(00)</Type>
      <ContainerId>1</ContainerId>
      <ContainerUid>1</ContainerUid>
      <Identifier>2497845147</Identifier>
      <OwnerIdn>89</OwnerIdn>
    </ObjectName>
  </LibraryHandle>
  <LibraryObjectLock>
    <Address>0x706c20e0</Address>
    <Handle>0x67f78888</Handle>
    <Mode>N</Mode>
  </LibraryObjectLock>
</KGLTRACE>
<KGLTRACE>
  <Timestamp>2021-02-12 15:41:23.657</Timestamp>
  <SID>136</SID>
  <Function>kgllkal</Function>
  <Reason>TRACELOCK</Reason>
  <Param1>0x706c1ff8</Param1>
  <Param2>0</Param2>
  <LibraryHandle>
    <Address>0x67f78328</Address>
    <Hash>0</Hash>
    <LockMode>N</LockMode>
    <PinMode>0</PinMode>
    <LoadLockMode>0</LoadLockMode>
    <Status>VALD</Status>
    <Name>
      <Namespace>SQL AREA(00)</Namespace>
      <Type>CURSOR(00)</Type>
      <ContainerId>3</ContainerId>
    </Name>
  </LibraryHandle>
  <LibraryObjectLock>
    <Address>0x706c1ff8</Address>
    <Handle>0x67f78328</Handle>
    <Mode>N</Mode>
  </LibraryObjectLock>
</KGLTRACE>
```

It can be parsed easily:

```sql hl_lines="40 43"
SQL> create or replace directory trace_dir as '&dn.';
old   1: create or replace directory trace_dir as '&dn.'
new   1: create or replace directory trace_dir as '/u01/app/oracle/diag/rdbms/racdba/racdba1/trace'

Directory created.

SQL>
SQL> create table trace_ext (
  2    trace_data clob
  3  )
  4  organization external (
  5    type oracle_loader
  6    default directory trace_dir
  7    access parameters (
  8      records
  9      xmltag ("KGLTRACE")
 10      fields ldrtrim
 11      missing field values are null (
 12        trace_data char(1000000)
 13      )
 14    )
 15    location ('&bn.')
 16  )
 17  reject limit unlimited;
old  15:   location ('&bn.')
new  15:   location ('racdba1_ora_16440.trc')

Table created.

SQL>
SQL> select count(*) from trace_ext;

  COUNT(*)
----------
       275

SQL> ho grep KGLTRACE &tf. | wc -l
550
```

Looks good.
275 rows in the external table for 550 `KGLTRACE` tags - these are both opening and closing tags, so that the number of rows matches precisely the number of XML elements in the trace file.

Finally, we can retrieve the information about `kgllkal` calls for interesting objects:

```sql
SQL> select xt."Timestamp",
  2         xt."Function",
  3         xt."Reason",
  4         xt."Param1",
  5         lh."LockMode",
  6         lh."PinMode",
  7         obj."Name",
  8         obj."Namespace",
  9         obj."Type",
 10         lol."Address" lol_address,
 11         lol."Mode" lol_mode
 12    from trace_ext,
 13         xmltable('/KGLTRACE' passing xmltype(trace_data)
 14           columns "Timestamp" varchar2(24),
 15                   sid number,
 16                   "Function" varchar2(20),
 17                   "Reason" varchar2(10),
 18                   "Param1" varchar2(14),
 19                   "Param2" number,
 20                   "LibraryHandle" xmltype,
 21                   "LibraryObjectLock" xmltype
 22         )(+) xt,
 23         xmltable('/LibraryHandle' passing xt."LibraryHandle"
 24           columns "Address" varchar2(10),
 25                   "Hash" varchar2(10),
 26                   "LockMode" varchar2(8),
 27                   "PinMode" varchar2(8),
 28                   "LoadLockMode" varchar2(8),
 29                   "Status" varchar2(10),
 30                   "ObjectName" xmltype
 31         )(+) lh,
 32         xmltable('/ObjectName' passing lh."ObjectName"
 33           columns "Name" varchar2(64),
 34                   "FullHashValue" varchar2(32),
 35                   "Namespace" varchar2(32),
 36                   "Type" varchar2(32),
 37                   "ContainerId" number,
 38                   "ContainerUid" number,
 39                   "Identifier" number,
 40                   "OwnerIdn" number
 41         )(+) obj,
 42         xmltable('/LibraryObjectLock' passing xt."LibraryObjectLock"
 43           columns "Address" varchar2(10),
 44                   "Handle" varchar2(10),
 45                   "Mode"   varchar2(4)
 46         )(+) lol
 47   where 1=1
 48     and obj."Name" like '%PDB.TC.%'
 49     and xt."Function"='kgllkal';

Timestamp                Function Reason     Param1         LockMode PinMode  Name            Namespace            Type       LOL_ADDRES LOL_MODE
------------------------ -------- ---------- -------------- -------- -------- --------------- -------------------- ---------- ---------- --------
2021-02-12 15:41:23.595  kgllkal  TRACELOCK  0x62da2ef0     S        0        PDB.TC.IX_T     INDEX(04)            INDEX(01)  0x62da2ef0 S
2021-02-12 15:41:23.598  kgllkal  TRACELOCK  0x62da2ef0     S        0        PDB.TC.T        TABLE/PROCEDURE(01)  TABLE(02)  0x62da2ef0 S
2021-02-12 15:41:23.599  kgllkal  TRACELOCK  0x62c9f8d0     S        0        PDB.TC.IX_T     INDEX(04)            INDEX(01)  0x62c9f8d0 S
2021-02-12 15:41:23.601  kgllkal  TRACELOCK  0x62c9f8d0     S        S        PDB.TC.T        TABLE/PROCEDURE(01)  TABLE(02)  0x62c9f8d0 S
2021-02-12 15:41:23.613  kgllkal  TRACELOCK  0x65db4480     S        0        PDB.TC.IX_T     INDEX(04)            INDEX(01)  0x65db4480 S
2021-02-12 15:41:23.617  kgllkal  TRACELOCK  0x65db4480     S        0        PDB.TC.T        TABLE/PROCEDURE(01)  TABLE(02)  0x65db4480 S
2021-02-12 15:41:23.618  kgllkal  TRACELOCK  0x62db5708     S        0        PDB.TC.IX_T     INDEX(04)            INDEX(01)  0x62db5708 S
2021-02-12 15:41:23.626  kgllkal  TRACELOCK  0x65db4480     S        0        PDB.TC.IX_T     INDEX(04)            INDEX(01)  0x65db4480 S
2021-02-12 15:41:23.629  kgllkal  TRACELOCK  0x65db4480     X        0        PDB.TC.T        TABLE/PROCEDURE(01)  TABLE(02)  0x65db4480 X
2021-02-12 15:41:23.632  kgllkal  TRACELOCK  0x62da2ef0     X        0        PDB.TC.IX_T     INDEX(04)            INDEX(01)  0x62da2ef0 X

10 rows selected.
```

## Conclusion

We can trace library cache locks, or more specifically certain `kgllkal` calls.
The resulting trace data is written to the trace file in the XML format.
It can be loaded into the database for further analysis.

## Usual disclaimer

This blog post is a pure speculation.
Although the results might be be reasonable and suggestive, I have no idea whether or not `_kgl_debug=32` covers all or most library cache locks.
