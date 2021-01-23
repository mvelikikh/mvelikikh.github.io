---
categories:
  - Oracle
date:
  created: 2021-01-23T00:11:00
description: >-
  Demonstrate how to use an undocumented CLONE INDEXES clause to create a table with indexes for exchange partition.
tags:
  - 19c
  - Diagnostic event
  - Indexing
---

# Creating a Table for Exchange and Copying Indexes

It is something Oracle added in one of the latest Release Updates of 19c.
I believe I discovered it either in 19.7 or 19.8 originally.

<!-- more -->

I used 19.10 in this post.

```sql
SQL> select banner_full from v$version;

BANNER_FULL
----------------------------------------------------------------------------------------------------
Oracle Database 19c Enterprise Edition Release 19.0.0.0.0 - Production
Version 19.10.0.0.0
```

Creating a partitioned table with several local indexes:

```sql
SQL> create table t (
  2    created date,
  3    c1 int,
  4    c2 int
  5  )
  6  partition by range(created) interval(numtoyminterval(1, 'year')) (
  7    partition values less than(date'2019-01-01')
  8  );

Table created.

SQL>
SQL> create index t_c1_i on t(c2) local;

Index created.

SQL> create index t_c1_c2_i on t(c1, c2) local;

Index created.

SQL> create index t_created_c1_i on t(trunc(created), c1) local;

Index created.

SQL> create index t_desc_i on t(c1 desc, c2) local;

Index created.
```

Populating it with some data:

```sql
SQL> insert into t values (date'2018-01-01', 1, 10);

1 row created.

SQL> insert into t values (date'2019-01-01', 2, 20);

1 row created.

SQL> insert into t values (date'2020-01-01', 3, 30);

1 row created.
```

Now is the actual enhancement - the `CLONE INDEXES` clause:

```sql hl_lines="5"
SQL> alter session set events 'trace[sql_ddl]';

Session altered.

SQL> create table tex for exchange with table t clone indexes;

Table created.

SQL> alter session set events 'trace[sql_ddl] off';

Session altered.
```

I enabled the `SQL_DDL` trace event to see the actual DDL statements executed under the hood.

Let us see what indexes are actually created:

```sql
SQL> exec dbms_metadata.set_transform_param( -
>   dbms_metadata.session_transform, -
>   'SQLTERMINATOR', true)

PL/SQL procedure successfully completed.

SQL>
SQL> select dbms_metadata.get_ddl('INDEX', index_name) from ind where table_name='TEX';

DBMS_METADATA.GET_DDL('INDEX',INDEX_NAME)
----------------------------------------------------------------------------------------------------

  CREATE INDEX "TC"."I_SYS_23689_T_C1_I" ON "TC"."TEX" ("C2")
  PCTFREE 10 INITRANS 2 MAXTRANS 255 COMPUTE STATISTICS
  TABLESPACE "USERS" ;


  CREATE INDEX "TC"."I_SYS_23689_T_C1_C2_I" ON "TC"."TEX" ("C1", "C2")
  PCTFREE 10 INITRANS 2 MAXTRANS 255 COMPUTE STATISTICS
  TABLESPACE "USERS" ;


  CREATE INDEX "TC"."I_SYS_23689_T_CREATED_C1_I" ON "TC"."TEX" (TRUNC("CREATED"), "C1")
  PCTFREE 10 INITRANS 2 MAXTRANS 255 COMPUTE STATISTICS
  TABLESPACE "USERS" ;


  CREATE INDEX "TC"."I_SYS_23689_T_DESC_I" ON "TC"."TEX" ("C1" DESC, "C2")
  PCTFREE 10 INITRANS 2 MAXTRANS 255 COMPUTE STATISTICS
  TABLESPACE "USERS" ;
```

Looks good.
Let us try to exchange a partition with that table:

```sql
SQL> alter table t
  2    exchange partition for (date'2018-01-01')
  3    with table tex
  4    including indexes;

Table altered.

SQL>
SQL> select * from t;

CREATED           C1         C2
--------- ---------- ----------
01-JAN-19          2         20
01-JAN-20          3         30

SQL> select * from tex;

CREATED           C1         C2
--------- ---------- ----------
01-JAN-18          1         10
```

??? "The entries in the trace file with the CREATE INDEX commands highlighted"

    ``` hl_lines="13 21 30 34 46 58 62 72 84 96 100 110 120 132 144 148 158 168 178 190"
    *** 2021-01-22T17:45:20.340547+00:00 (PDB2(3))
    *** SESSION ID:(5.40211) 2021-01-22T17:45:20.340569+00:00
    *** CLIENT ID:() 2021-01-22T17:45:20.340573+00:00
    *** SERVICE NAME:(pdb2) 2021-01-22T17:45:20.340576+00:00
    *** MODULE NAME:(SQL*Plus) 2021-01-22T17:45:20.340579+00:00
    *** ACTION NAME:() 2021-01-22T17:45:20.340583+00:00
    *** CLIENT DRIVER:(SQL*PLUS) 2021-01-22T17:45:20.340585+00:00
    *** CONTAINER ID:(3) 2021-01-22T17:45:20.340588+00:00

    DDL begin in opiprs
    session id 5 inc 40211 pgadep 0 sqlid fabsxw9ass76q oct 1 txn 0xaed56ac8 autocommit 1
    ----- Current SQL Statement for this session (sql_id=fabsxw9ass76q) -----
    create table tex for exchange with table t clone indexes

    DCSTRC: Deferred Segment Creation Enabled for objn 0.
    ctcdrv
    session id 5 inc 40211 pgadep 0 sqlid fabsxw9ass76q DDL on 23689 op-alter_table 0
    DCSTRC: Inserting into deferred_stg$ objn:23689
    stg:0x95fbff70 ts: objno:23689 dobjno:23689 pctfree:127 pctused:127 size:32767 initrans:2147483647 maxtrans:2147483647 initial:4294967295 next:4294967295 optimal:4294967295 minextents:2147483647 maxextents:2147483647 pctinc:2147483647 maxins:0 frlins:65535 tabno:0 NOCOMPRESS/NO ROW LEVEL LOCKING/
    flags: 0x8 imcflag: 0x0----- Current SQL Statement for this session (sql_id=fabsxw9ass76q) -----
    create table tex for exchange with table t clone indexes
    ----- Abridged Call Stack Trace -----
    ksedsts<-kkpoids_insert_deferred_stg<-ctcdrv<-opiexe<-opiosq0<-kpooprx<-kpoal8<-opiodr<-ttcpip<-opitsk<-opiino<-opiodr<-opidrv<-sou2o<-opimai_real<-ssthrdmain<-main<-__libc_start_main
    ----- End of Abridged Call Stack Trace -----
    Partial short call stack signature: 0x753b1c2f5bde975f
    DCSTRC: Data Segment for ObjNo: 23689 Not Created
    DDL begin in opiprs
    session id 17 inc 56060 pgadep 1 sqlid gpda0upp7xs4x oct 9 txn 0xaed56ac8 autocommit 0
    ----- Current SQL Statement for this session (sql_id=gpda0upp7xs4x) -----
    CREATE INDEX "TC"."I_SYS_23689_T_C1_I" ON "TC"."TEX"("C2") NOPARALLEL

    DCSTRC: Selecting from deferred_stg$ objn:23689
    ----- Current SQL Statement for this session (sql_id=gpda0upp7xs4x) -----
    CREATE INDEX "TC"."I_SYS_23689_T_C1_I" ON "TC"."TEX"("C2") NOPARALLEL
    ----- Abridged Call Stack Trace -----
    ksedsts<-kkposds_select_deferred_stg<-kkpo_rcinfo_defstg<-ktsircinfo<-kkdlgstd<-kkmfcbloCbk<-kkmpfcbk<-qcsprfro<-qcsprfro_tree<-qcsprfro_tree<-qcspafq<-qcspqbDescendents<-qcspqb<-kkmdrv<-opiSem<-opiprs<-kksParseChildCursor<-rpiswu2<-kksLoadChild<-kxsGetRuntimeLock
    <-kksfbc<-kkspsc0<-kksParseCursor<-opiosq0<-opiall0<-opikpr<-opiodr<-rpidrus<-skgmstack<-rpidru<-rpiswu2<-kprball<-kkpofmc_form_msq_cix<-kglsscn<-kkpocim_create_indexes_modpart<-ctcdrv<-opiexe<-opiosq0<-kpooprx<-kpoal8<-opiodr<-ttcpip<-opitsk<-opiino<-opiodr
    <-opidrv<-sou2o<-opimai_real<-ssthrdmain<-main<-__libc_start_main
    ----- End of Abridged Call Stack Trace -----
    Partial short call stack signature: 0x41a77ef85a8b5b0f
    stg:0x7fff61c4c838 ts: objno:0 dobjno:0 pctfree:127 pctused:127 size:32767 initrans:2147483647 maxtrans:2147483647 initial:4294967295 next:4294967295 optimal:4294967295 minextents:2147483647 maxextents:2147483647 pctinc:2147483647 maxins:0 frlins:65535 tabno:0 NOCOMPRESS/NO ROW LEVEL LOCKING/
    flags: 0x8 imcflag: 0x0ktagetg_ddl sessionid 17 inc 56060 pgadep 1 txn 0xaed56ac8 table 23689 mode 4
    DCSTRC: Inserting into deferred_stg$ objn:23690
    stg:0x98722108 ts: objno:23690 dobjno:23690 pctfree:10 pctused:127 size:32767 initrans:2 maxtrans:255 initial:4294967295 next:4294967295 optimal:4294967295 minextents:2147483647 maxextents:2147483647 pctinc:2147483647 maxins:0 frlins:65535 tabno:0 NOCOMPRESS/NO ROW LEVEL LOCKING/
    flags: 0x0 imcflag: 0x0----- Current SQL Statement for this session (sql_id=gpda0upp7xs4x) -----
    CREATE INDEX "TC"."I_SYS_23689_T_C1_I" ON "TC"."TEX"("C2") NOPARALLEL
    ----- Abridged Call Stack Trace -----
    ksedsts<-kkpoids_insert_deferred_stg<-kdicrws<-kdicdrv<-opiexe<-opiosq0<-opiall0<-opikpr<-opiodr<-rpidrus<-skgmstack<-rpidru<-rpiswu2<-kprball<-kkpofmc_form_msq_cix<-kglsscn<-kkpocim_create_indexes_modpart<-ctcdrv<-opiexe<-opiosq0<-kpooprx<-kpoal8<-opiodr<-ttcpip
    <-opitsk<-opiino<-opiodr<-opidrv<-sou2o<-opimai_real<-ssthrdmain<-main<-__libc_start_main
    ----- End of Abridged Call Stack Trace -----
    Partial short call stack signature: 0x67b767b3ee346cb2
    DCSTRC: Index Segment for ObjNo:23690 Not Created
    DDL end in opiexe
    session id 17 inc 56060 pgadep 1 sqlid gpda0upp7xs4x txn 0xaed56ac8 autocommit 0 commited 0
    DDL begin in opiprs
    session id 17 inc 56060 pgadep 1 sqlid 890bc4g127vkt oct 9 txn 0xaed56ac8 autocommit 0
    ----- Current SQL Statement for this session (sql_id=890bc4g127vkt) -----
    CREATE INDEX "TC"."I_SYS_23689_T_C1_C2_I" ON "TC"."TEX"("C1" , "C2") NOPARALLEL

    DCSTRC: Selecting from deferred_stg$ objn:23689
    ----- Current SQL Statement for this session (sql_id=890bc4g127vkt) -----
    CREATE INDEX "TC"."I_SYS_23689_T_C1_C2_I" ON "TC"."TEX"("C1" , "C2") NOPARALLEL
    ----- Abridged Call Stack Trace -----
    ksedsts<-kkposds_select_deferred_stg<-kkpo_rcinfo_defstg<-ktsircinfo<-kkdlgstd<-kkmfcbloCbk<-kkmpfcbk<-qcsprfro<-qcsprfro_tree<-qcsprfro_tree<-qcspafq<-qcspqbDescendents<-qcspqb<-kkmdrv<-opiSem<-opiprs<-kksParseChildCursor<-rpiswu2<-kksLoadChild<-kxsGetRuntimeLock
    <-kksfbc<-kkspsc0<-kksParseCursor<-opiosq0<-opiall0<-opikpr<-opiodr<-rpidrus<-skgmstack<-rpidru<-rpiswu2<-kprball<-kkpofmc_form_msq_cix<-kglsscn<-kkpocim_create_indexes_modpart<-ctcdrv<-opiexe<-opiosq0<-kpooprx<-kpoal8<-opiodr<-ttcpip<-opitsk<-opiino<-opiodr
    <-opidrv<-sou2o<-opimai_real<-ssthrdmain<-main<-__libc_start_main
    ----- End of Abridged Call Stack Trace -----
    Partial short call stack signature: 0x41a77ef85a8b5b0f
    stg:0x7fff61c4c838 ts: objno:0 dobjno:0 pctfree:127 pctused:127 size:32767 initrans:2147483647 maxtrans:2147483647 initial:4294967295 next:4294967295 optimal:4294967295 minextents:2147483647 maxextents:2147483647 pctinc:2147483647 maxins:0 frlins:65535 tabno:0 NOCOMPRESS/NO ROW LEVEL LOCKING/
    flags: 0x8 imcflag: 0x0DCSTRC: Selecting from deferred_stg$ objn:23690
    ----- Current SQL Statement for this session (sql_id=890bc4g127vkt) -----
    CREATE INDEX "TC"."I_SYS_23689_T_C1_C2_I" ON "TC"."TEX"("C1" , "C2") NOPARALLEL
    ----- Abridged Call Stack Trace -----
    ksedsts<-kkposds_select_deferred_stg<-kkpo_rcinfo_defstg<-ktsircinfo<-kdigetspace2<-kdigetspace<-kkdl1ck<-kkdlack<-kkmfcbbt<-kkmfcbloCbk<-kkmpfcbk<-qcsprfro<-qcsprfro_tree<-qcsprfro_tree<-qcspafq<-qcspqbDescendents<-qcspqb<-kkmdrv<-opiSem<-opiprs<-kksParseChildCursor
    <-rpiswu2<-kksLoadChild<-kxsGetRuntimeLock<-kksfbc<-kkspsc0<-kksParseCursor<-opiosq0<-opiall0<-opikpr<-opiodr<-rpidrus<-skgmstack<-rpidru<-rpiswu2<-kprball<-kkpofmc_form_msq_cix<-kglsscn<-kkpocim_create_indexes_modpart<-ctcdrv<-opiexe<-opiosq0<-kpooprx<-kpoal8
    <-opiodr<-ttcpip<-opitsk<-opiino<-opiodr<-opidrv<-sou2o<-opimai_real<-ssthrdmain<-main<-__libc_start_main
    ----- End of Abridged Call Stack Trace -----
    Partial short call stack signature: 0x2e48dfa364bfeef0
    stg:0x7fff61c4cd98 ts: objno:0 dobjno:0 pctfree:10 pctused:127 size:32767 initrans:2 maxtrans:255 initial:4294967295 next:4294967295 optimal:4294967295 minextents:2147483647 maxextents:2147483647 pctinc:2147483647 maxins:0 frlins:65535 tabno:0 NOCOMPRESS/NO ROW LEVEL LOCKING/
    flags: 0x0 imcflag: 0x0ktagetg_ddl sessionid 17 inc 56060 pgadep 1 txn 0xaed56ac8 table 23689 mode 4
    DCSTRC: Inserting into deferred_stg$ objn:23691
    stg:0x98701d48 ts: objno:23691 dobjno:23691 pctfree:10 pctused:127 size:32767 initrans:2 maxtrans:255 initial:4294967295 next:4294967295 optimal:4294967295 minextents:2147483647 maxextents:2147483647 pctinc:2147483647 maxins:0 frlins:65535 tabno:0 NOCOMPRESS/NO ROW LEVEL LOCKING/
    flags: 0x0 imcflag: 0x0----- Current SQL Statement for this session (sql_id=890bc4g127vkt) -----
    CREATE INDEX "TC"."I_SYS_23689_T_C1_C2_I" ON "TC"."TEX"("C1" , "C2") NOPARALLEL
    ----- Abridged Call Stack Trace -----
    ksedsts<-kkpoids_insert_deferred_stg<-kdicrws<-kdicdrv<-opiexe<-opiosq0<-opiall0<-opikpr<-opiodr<-rpidrus<-skgmstack<-rpidru<-rpiswu2<-kprball<-kkpofmc_form_msq_cix<-kglsscn<-kkpocim_create_indexes_modpart<-ctcdrv<-opiexe<-opiosq0<-kpooprx<-kpoal8<-opiodr<-ttcpip
    <-opitsk<-opiino<-opiodr<-opidrv<-sou2o<-opimai_real<-ssthrdmain<-main<-__libc_start_main
    ----- End of Abridged Call Stack Trace -----
    Partial short call stack signature: 0x67b767b3ee346cb2
    DCSTRC: Index Segment for ObjNo:23691 Not Created
    DDL end in opiexe
    session id 17 inc 56060 pgadep 1 sqlid 890bc4g127vkt txn 0xaed56ac8 autocommit 0 commited 0
    DDL begin in opiprs
    session id 17 inc 56060 pgadep 1 sqlid dv4r3pvxwh4az oct 9 txn 0xaed56ac8 autocommit 0
    ----- Current SQL Statement for this session (sql_id=dv4r3pvxwh4az) -----
    CREATE INDEX "TC"."I_SYS_23689_T_CREATED_C1_I" ON "TC"."TEX"(TRUNC("CREATED") , "C1") NOPARALLEL

    DCSTRC: Selecting from deferred_stg$ objn:23689
    ----- Current SQL Statement for this session (sql_id=dv4r3pvxwh4az) -----
    CREATE INDEX "TC"."I_SYS_23689_T_CREATED_C1_I" ON "TC"."TEX"(TRUNC("CREATED") , "C1") NOPARALLEL
    ----- Abridged Call Stack Trace -----
    ksedsts<-kkposds_select_deferred_stg<-kkpo_rcinfo_defstg<-ktsircinfo<-kkdlgstd<-kkmfcbloCbk<-kkmpfcbk<-qcsprfro<-qcsprfro_tree<-qcsprfro_tree<-qcspafq<-qcspqbDescendents<-qcspqb<-kkmdrv<-opiSem<-opiprs<-kksParseChildCursor<-rpiswu2<-kksLoadChild<-kxsGetRuntimeLock
    <-kksfbc<-kkspsc0<-kksParseCursor<-opiosq0<-opiall0<-opikpr<-opiodr<-rpidrus<-skgmstack<-rpidru<-rpiswu2<-kprball<-kkpofmc_form_msq_cix<-kglsscn<-kkpocim_create_indexes_modpart<-ctcdrv<-opiexe<-opiosq0<-kpooprx<-kpoal8<-opiodr<-ttcpip<-opitsk<-opiino<-opiodr
    <-opidrv<-sou2o<-opimai_real<-ssthrdmain<-main<-__libc_start_main
    ----- End of Abridged Call Stack Trace -----
    Partial short call stack signature: 0x41a77ef85a8b5b0f
    stg:0x7fff61c4c838 ts: objno:0 dobjno:0 pctfree:127 pctused:127 size:32767 initrans:2147483647 maxtrans:2147483647 initial:4294967295 next:4294967295 optimal:4294967295 minextents:2147483647 maxextents:2147483647 pctinc:2147483647 maxins:0 frlins:65535 tabno:0 NOCOMPRESS/NO ROW LEVEL LOCKING/
    flags: 0x8 imcflag: 0x0DCSTRC: Selecting from deferred_stg$ objn:23691
    ----- Current SQL Statement for this session (sql_id=dv4r3pvxwh4az) -----
    CREATE INDEX "TC"."I_SYS_23689_T_CREATED_C1_I" ON "TC"."TEX"(TRUNC("CREATED") , "C1") NOPARALLEL
    ----- Abridged Call Stack Trace -----
    ksedsts<-kkposds_select_deferred_stg<-kkpo_rcinfo_defstg<-ktsircinfo<-kdigetspace2<-kdigetspace<-kkdl1ck<-kkdlack<-kkmfcbbt<-kkmfcbloCbk<-kkmpfcbk<-qcsprfro<-qcsprfro_tree<-qcsprfro_tree<-qcspafq<-qcspqbDescendents<-qcspqb<-kkmdrv<-opiSem<-opiprs<-kksParseChildCursor
    <-rpiswu2<-kksLoadChild<-kxsGetRuntimeLock<-kksfbc<-kkspsc0<-kksParseCursor<-opiosq0<-opiall0<-opikpr<-opiodr<-rpidrus<-skgmstack<-rpidru<-rpiswu2<-kprball<-kkpofmc_form_msq_cix<-kglsscn<-kkpocim_create_indexes_modpart<-ctcdrv<-opiexe<-opiosq0<-kpooprx<-kpoal8
    <-opiodr<-ttcpip<-opitsk<-opiino<-opiodr<-opidrv<-sou2o<-opimai_real<-ssthrdmain<-main<-__libc_start_main
    ----- End of Abridged Call Stack Trace -----
    Partial short call stack signature: 0x2e48dfa364bfeef0
    stg:0x7fff61c4cd98 ts: objno:0 dobjno:0 pctfree:10 pctused:127 size:32767 initrans:2 maxtrans:255 initial:4294967295 next:4294967295 optimal:4294967295 minextents:2147483647 maxextents:2147483647 pctinc:2147483647 maxins:0 frlins:65535 tabno:0 NOCOMPRESS/NO ROW LEVEL LOCKING/
    flags: 0x0 imcflag: 0x0DCSTRC: Selecting from deferred_stg$ objn:23690
    ----- Current SQL Statement for this session (sql_id=dv4r3pvxwh4az) -----
    CREATE INDEX "TC"."I_SYS_23689_T_CREATED_C1_I" ON "TC"."TEX"(TRUNC("CREATED") , "C1") NOPARALLEL
    ----- Abridged Call Stack Trace -----
    ksedsts<-kkposds_select_deferred_stg<-kkpo_rcinfo_defstg<-ktsircinfo<-kdigetspace2<-kdigetspace<-kkdl1ck<-kkdlack<-kkmfcbbt<-kkmfcbloCbk<-kkmpfcbk<-qcsprfro<-qcsprfro_tree<-qcsprfro_tree<-qcspafq<-qcspqbDescendents<-qcspqb<-kkmdrv<-opiSem<-opiprs<-kksParseChildCursor
    <-rpiswu2<-kksLoadChild<-kxsGetRuntimeLock<-kksfbc<-kkspsc0<-kksParseCursor<-opiosq0<-opiall0<-opikpr<-opiodr<-rpidrus<-skgmstack<-rpidru<-rpiswu2<-kprball<-kkpofmc_form_msq_cix<-kglsscn<-kkpocim_create_indexes_modpart<-ctcdrv<-opiexe<-opiosq0<-kpooprx<-kpoal8
    <-opiodr<-ttcpip<-opitsk<-opiino<-opiodr<-opidrv<-sou2o<-opimai_real<-ssthrdmain<-main<-__libc_start_main
    ----- End of Abridged Call Stack Trace -----
    Partial short call stack signature: 0x2e48dfa364bfeef0
    stg:0x7fff61c4cd98 ts: objno:0 dobjno:0 pctfree:10 pctused:127 size:32767 initrans:2 maxtrans:255 initial:4294967295 next:4294967295 optimal:4294967295 minextents:2147483647 maxextents:2147483647 pctinc:2147483647 maxins:0 frlins:65535 tabno:0 NOCOMPRESS/NO ROW LEVEL LOCKING/
    flags: 0x0 imcflag: 0x0ktagetg_ddl sessionid 17 inc 56060 pgadep 1 txn 0xaed56ac8 table 23689 mode 4
    DCSTRC: Inserting into deferred_stg$ objn:23692
    stg:0x986e5b68 ts: objno:23692 dobjno:23692 pctfree:10 pctused:127 size:32767 initrans:2 maxtrans:255 initial:4294967295 next:4294967295 optimal:4294967295 minextents:2147483647 maxextents:2147483647 pctinc:2147483647 maxins:0 frlins:65535 tabno:0 NOCOMPRESS/NO ROW LEVEL LOCKING/
    flags: 0x0 imcflag: 0x0----- Current SQL Statement for this session (sql_id=dv4r3pvxwh4az) -----
    CREATE INDEX "TC"."I_SYS_23689_T_CREATED_C1_I" ON "TC"."TEX"(TRUNC("CREATED") , "C1") NOPARALLEL
    ----- Abridged Call Stack Trace -----
    ksedsts<-kkpoids_insert_deferred_stg<-kdicrws<-kdicdrv<-opiexe<-opiosq0<-opiall0<-opikpr<-opiodr<-rpidrus<-skgmstack<-rpidru<-rpiswu2<-kprball<-kkpofmc_form_msq_cix<-kglsscn<-kkpocim_create_indexes_modpart<-ctcdrv<-opiexe<-opiosq0<-kpooprx<-kpoal8<-opiodr<-ttcpip
    <-opitsk<-opiino<-opiodr<-opidrv<-sou2o<-opimai_real<-ssthrdmain<-main<-__libc_start_main
    ----- End of Abridged Call Stack Trace -----
    Partial short call stack signature: 0x67b767b3ee346cb2
    DCSTRC: Index Segment for ObjNo:23692 Not Created
    DDL end in opiexe
    session id 17 inc 56060 pgadep 1 sqlid dv4r3pvxwh4az txn 0xaed56ac8 autocommit 0 commited 0
    DDL begin in opiprs
    session id 17 inc 56060 pgadep 1 sqlid cukauv41bbw51 oct 9 txn 0xaed56ac8 autocommit 0
    ----- Current SQL Statement for this session (sql_id=cukauv41bbw51) -----
    CREATE INDEX "TC"."I_SYS_23689_T_DESC_I" ON "TC"."TEX"("C1" DESC , "C2") NOPARALLEL

    DCSTRC: Selecting from deferred_stg$ objn:23689
    ----- Current SQL Statement for this session (sql_id=cukauv41bbw51) -----
    CREATE INDEX "TC"."I_SYS_23689_T_DESC_I" ON "TC"."TEX"("C1" DESC , "C2") NOPARALLEL
    ----- Abridged Call Stack Trace -----
    ksedsts<-kkposds_select_deferred_stg<-kkpo_rcinfo_defstg<-ktsircinfo<-kkdlgstd<-kkmfcbloCbk<-kkmpfcbk<-qcsprfro<-qcsprfro_tree<-qcsprfro_tree<-qcspafq<-qcspqbDescendents<-qcspqb<-kkmdrv<-opiSem<-opiprs<-kksParseChildCursor<-rpiswu2<-kksLoadChild<-kxsGetRuntimeLock
    <-kksfbc<-kkspsc0<-kksParseCursor<-opiosq0<-opiall0<-opikpr<-opiodr<-rpidrus<-skgmstack<-rpidru<-rpiswu2<-kprball<-kkpofmc_form_msq_cix<-kglsscn<-kkpocim_create_indexes_modpart<-ctcdrv<-opiexe<-opiosq0<-kpooprx<-kpoal8<-opiodr<-ttcpip<-opitsk<-opiino<-opiodr
    <-opidrv<-sou2o<-opimai_real<-ssthrdmain<-main<-__libc_start_main
    ----- End of Abridged Call Stack Trace -----
    Partial short call stack signature: 0x41a77ef85a8b5b0f
    stg:0x7fff61c4c838 ts: objno:0 dobjno:0 pctfree:127 pctused:127 size:32767 initrans:2147483647 maxtrans:2147483647 initial:4294967295 next:4294967295 optimal:4294967295 minextents:2147483647 maxextents:2147483647 pctinc:2147483647 maxins:0 frlins:65535 tabno:0 NOCOMPRESS/NO ROW LEVEL LOCKING/
    flags: 0x8 imcflag: 0x0DCSTRC: Selecting from deferred_stg$ objn:23692
    ----- Current SQL Statement for this session (sql_id=cukauv41bbw51) -----
    CREATE INDEX "TC"."I_SYS_23689_T_DESC_I" ON "TC"."TEX"("C1" DESC , "C2") NOPARALLEL
    ----- Abridged Call Stack Trace -----
    ksedsts<-kkposds_select_deferred_stg<-kkpo_rcinfo_defstg<-ktsircinfo<-kdigetspace2<-kdigetspace<-kkdl1ck<-kkdlack<-kkmfcbbt<-kkmfcbloCbk<-kkmpfcbk<-qcsprfro<-qcsprfro_tree<-qcsprfro_tree<-qcspafq<-qcspqbDescendents<-qcspqb<-kkmdrv<-opiSem<-opiprs<-kksParseChildCursor
    <-rpiswu2<-kksLoadChild<-kxsGetRuntimeLock<-kksfbc<-kkspsc0<-kksParseCursor<-opiosq0<-opiall0<-opikpr<-opiodr<-rpidrus<-skgmstack<-rpidru<-rpiswu2<-kprball<-kkpofmc_form_msq_cix<-kglsscn<-kkpocim_create_indexes_modpart<-ctcdrv<-opiexe<-opiosq0<-kpooprx<-kpoal8
    <-opiodr<-ttcpip<-opitsk<-opiino<-opiodr<-opidrv<-sou2o<-opimai_real<-ssthrdmain<-main<-__libc_start_main
    ----- End of Abridged Call Stack Trace -----
    Partial short call stack signature: 0x2e48dfa364bfeef0
    stg:0x7fff61c4cd98 ts: objno:0 dobjno:0 pctfree:10 pctused:127 size:32767 initrans:2 maxtrans:255 initial:4294967295 next:4294967295 optimal:4294967295 minextents:2147483647 maxextents:2147483647 pctinc:2147483647 maxins:0 frlins:65535 tabno:0 NOCOMPRESS/NO ROW LEVEL LOCKING/
    flags: 0x0 imcflag: 0x0DCSTRC: Selecting from deferred_stg$ objn:23691
    ----- Current SQL Statement for this session (sql_id=cukauv41bbw51) -----
    CREATE INDEX "TC"."I_SYS_23689_T_DESC_I" ON "TC"."TEX"("C1" DESC , "C2") NOPARALLEL
    ----- Abridged Call Stack Trace -----
    ksedsts<-kkposds_select_deferred_stg<-kkpo_rcinfo_defstg<-ktsircinfo<-kdigetspace2<-kdigetspace<-kkdl1ck<-kkdlack<-kkmfcbbt<-kkmfcbloCbk<-kkmpfcbk<-qcsprfro<-qcsprfro_tree<-qcsprfro_tree<-qcspafq<-qcspqbDescendents<-qcspqb<-kkmdrv<-opiSem<-opiprs<-kksParseChildCursor
    <-rpiswu2<-kksLoadChild<-kxsGetRuntimeLock<-kksfbc<-kkspsc0<-kksParseCursor<-opiosq0<-opiall0<-opikpr<-opiodr<-rpidrus<-skgmstack<-rpidru<-rpiswu2<-kprball<-kkpofmc_form_msq_cix<-kglsscn<-kkpocim_create_indexes_modpart<-ctcdrv<-opiexe<-opiosq0<-kpooprx<-kpoal8
    <-opiodr<-ttcpip<-opitsk<-opiino<-opiodr<-opidrv<-sou2o<-opimai_real<-ssthrdmain<-main<-__libc_start_main
    ----- End of Abridged Call Stack Trace -----
    Partial short call stack signature: 0x2e48dfa364bfeef0
    stg:0x7fff61c4cd98 ts: objno:0 dobjno:0 pctfree:10 pctused:127 size:32767 initrans:2 maxtrans:255 initial:4294967295 next:4294967295 optimal:4294967295 minextents:2147483647 maxextents:2147483647 pctinc:2147483647 maxins:0 frlins:65535 tabno:0 NOCOMPRESS/NO ROW LEVEL LOCKING/
    flags: 0x0 imcflag: 0x0DCSTRC: Selecting from deferred_stg$ objn:23690
    ----- Current SQL Statement for this session (sql_id=cukauv41bbw51) -----
    CREATE INDEX "TC"."I_SYS_23689_T_DESC_I" ON "TC"."TEX"("C1" DESC , "C2") NOPARALLEL
    ----- Abridged Call Stack Trace -----
    ksedsts<-kkposds_select_deferred_stg<-kkpo_rcinfo_defstg<-ktsircinfo<-kdigetspace2<-kdigetspace<-kkdl1ck<-kkdlack<-kkmfcbbt<-kkmfcbloCbk<-kkmpfcbk<-qcsprfro<-qcsprfro_tree<-qcsprfro_tree<-qcspafq<-qcspqbDescendents<-qcspqb<-kkmdrv<-opiSem<-opiprs<-kksParseChildCursor
    <-rpiswu2<-kksLoadChild<-kxsGetRuntimeLock<-kksfbc<-kkspsc0<-kksParseCursor<-opiosq0<-opiall0<-opikpr<-opiodr<-rpidrus<-skgmstack<-rpidru<-rpiswu2<-kprball<-kkpofmc_form_msq_cix<-kglsscn<-kkpocim_create_indexes_modpart<-ctcdrv<-opiexe<-opiosq0<-kpooprx<-kpoal8
    <-opiodr<-ttcpip<-opitsk<-opiino<-opiodr<-opidrv<-sou2o<-opimai_real<-ssthrdmain<-main<-__libc_start_main
    ----- End of Abridged Call Stack Trace -----
    Partial short call stack signature: 0x2e48dfa364bfeef0
    stg:0x7fff61c4cd98 ts: objno:0 dobjno:0 pctfree:10 pctused:127 size:32767 initrans:2 maxtrans:255 initial:4294967295 next:4294967295 optimal:4294967295 minextents:2147483647 maxextents:2147483647 pctinc:2147483647 maxins:0 frlins:65535 tabno:0 NOCOMPRESS/NO ROW LEVEL LOCKING/
    flags: 0x0 imcflag: 0x0ktagetg_ddl sessionid 17 inc 56060 pgadep 1 txn 0xaed56ac8 table 23689 mode 4
    DCSTRC: Inserting into deferred_stg$ objn:23693
    stg:0x986caa78 ts: objno:23693 dobjno:23693 pctfree:10 pctused:127 size:32767 initrans:2 maxtrans:255 initial:4294967295 next:4294967295 optimal:4294967295 minextents:2147483647 maxextents:2147483647 pctinc:2147483647 maxins:0 frlins:65535 tabno:0 NOCOMPRESS/NO ROW LEVEL LOCKING/
    flags: 0x0 imcflag: 0x0----- Current SQL Statement for this session (sql_id=cukauv41bbw51) -----
    CREATE INDEX "TC"."I_SYS_23689_T_DESC_I" ON "TC"."TEX"("C1" DESC , "C2") NOPARALLEL
    ----- Abridged Call Stack Trace -----
    ksedsts<-kkpoids_insert_deferred_stg<-kdicrws<-kdicdrv<-opiexe<-opiosq0<-opiall0<-opikpr<-opiodr<-rpidrus<-skgmstack<-rpidru<-rpiswu2<-kprball<-kkpofmc_form_msq_cix<-kglsscn<-kkpocim_create_indexes_modpart<-ctcdrv<-opiexe<-opiosq0<-kpooprx<-kpoal8<-opiodr<-ttcpip
    <-opitsk<-opiino<-opiodr<-opidrv<-sou2o<-opimai_real<-ssthrdmain<-main<-__libc_start_main
    ----- End of Abridged Call Stack Trace -----
    Partial short call stack signature: 0x67b767b3ee346cb2
    DCSTRC: Index Segment for ObjNo:23693 Not Created
    DDL end in opiexe
    session id 17 inc 56060 pgadep 1 sqlid cukauv41bbw51 txn 0xaed56ac8 autocommit 0 commited 0
    DDL end in opiexe
    session id 5 inc 40211 pgadep 0 sqlid fabsxw9ass76q txn 0xaed56ac8 autocommit 1 commited 1
    ```

Probably we will see this improvement documented one day.
Not sure whether it is stable or not.
I have tested it for some simple examples and it was working well.
