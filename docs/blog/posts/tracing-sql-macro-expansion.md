---
categories:
  - Oracle
date:
  created: 2020-02-01T23:00:00
  updated: 2020-02-25T00:40:37
description: >-
  Using PTF_Comp diagnostic event to trace SQL Macro expansions.
tags:
  - 19c
  - Code symbol
  - Diagnostic event
  - OERR
  - PL/SQL
---

# Tracing SQL Macro Expansion

I decided to take a look at what events Oracle provides to diagnose or troubleshoot SQL Macro Expansions.

<!-- more -->

For that, I took almost the same code that I used before: [SQL Macro script](https://gist.github.com/mvelikikh/01eb283d6c053d8631f16f21e1bc58e3)

```sql
drop table t;
drop table t1;
drop table t2;

CREATE OR REPLACE FUNCTION sample(t DBMS_TF.Table_t, how_many number DEFAULT 5)
RETURN VARCHAR2 SQL_MACRO
AS
BEGIN
  RETURN q'[SELECT *
              FROM t
      WHERE rownum <= how_many]';
END sample;
/

create table t
as
select n
  from xmltable('1 to 10'
  columns
    n int path '.');

create table t1
as
select n,
       'val_'||to_char(n, 'fm00') val
  from xmltable('1 to 10'
  columns
    n int path '.');

create table t2
as
select 'val_'||to_char(n, 'fm00') s
  from xmltable('1 to 10'
  columns
    n int path '.');

select * from t1;
select * from t2;

select *
  from sample(t1, 3);

select *
  from sample(t1);

select *
  from sample(t2);
```

A query failed when I was trying to supply the table `T` - which is the same that is used in the SQL macro's definition:

```sql
SQL> select *
  2    from sample(t);
  from sample(t)
               *
ERROR at line 2:
ORA-32039: recursive WITH clause must have column alias list
```

The errorstack dump for `ORA-32039` (`level=3`) did not provide much information about the underlying cause:

```
----- Error Stack Dump -----
<error barrier> at 0x7ffd69f7aaf0 placed dbkda.c@296
ORA-32039: recursive WITH clause must have column alias list
----- Current SQL Statement for this session (sql_id=d3ktrfsd4s0sr) -----
select * from sample(t)
```

SQL Trace was referring to the same statement:

```
PARSE ERROR #140320112869816:len=24 dep=0 uid=119 oct=3 lid=119 tim=1054524149653 err=32039
select * from sample(t)
```

It showed the following statement, though:

```sql
PARSING IN CURSOR #140320116348624 len=446 dep=1 uid=119 oct=47 lid=119 tim=1054472624364 hv=3547957408 ad='7cda6688' sqlid='9awjhv79rm250'

declare
t0 DBMS_TF.Table_t := DBMS_TF.Table_t(column => :0);

begin
:macro_text := "SAMPLE"(t0);
end;
```

While studying those `qksptfSQM` functions, namely: `qksptfSQM_GetTxt` and `qksptfSQM_Template`, I found that they are calling to the `PTF_Comp` UTS component (Polymorphic Table Functions Compilation (`qksptf`)):

``` hl_lines="2"
   0x000000000f75c87a <+4202>:  mov    $0x6000,%ecx
   0x000000000f75c87f <+4207>:  mov    $0x205018b,%esi
   0x000000000f75c884 <+4212>:  mov    $0x2,%edx
   0x000000000f75c889 <+4217>:  mov    -0x200(%rbp),%r8
   0x000000000f75c890 <+4224>:  mov    -0xcb58(%rbx),%rdi
   0x000000000f75c897 <+4231>:  callq  0x485cef0 <dbgtCtrl_intEvalCtrlEvent>
```

Therefore, I enabled `PTF_Comp` tracing:

```sql
alter session set events 'trace[ptf_comp]' tracefile_identifier=ptf_comp;
```

Here is what I got in the trace file:

``` hl_lines="19"
qksptfSQM_GetTxt(): Anonymous Block
===================================

declare
t0 DBMS_TF.Table_t := DBMS_TF.Table_t(column => :0);

begin
:macro_text := "SAMPLE"(t0);
end;
qksptfSQM_GetTxt(): Macro Text
==============================

SELECT *
              FROM t
             WHERE rownum <= how_many
qksptfSQM_Template(): Template Text
===================================

with  T as (select  /*+ INLINE */ * from "MY_USER"."T")
select "SYS__$".*
from (select 5 "HOW_MANY" from SYS.DUAL) "SAMPLE",
     lateral(SELECT *
              FROM t
             WHERE rownum <= how_many) "SYS__$"
```

Obviously, the `ORA-32039` error is absolutely legit in this case and the `PTF_Comp` tracing clearly shows where the issue is.
It highlights one of the current limitations of that functionality in Oracle 19.6.
Beside it demonstrates how literals (`HOW_MANY` in the example above) are passed through a subquery and joined to a lateral view - that approach has certain restrictions.

Apparently there seem to be more restrictions than that according to `$ORACLE_HOME/plsql/mesg/pcmus.msg`:

??? "SQL Macro related errors from `$ORACLE_HOME/plsql/mesg/pcmus.msg`"

    ``` hl_lines="1 6 12 22 31 42 48"
    776, 0, "SQL macro can only return character return types"
    // INDEX: "SQL macro"
    // RELEASE: 20.1
    // CAUSE: A SQL macro function returned a type that was not a character type like VARCHAR2.
    // ACTION:  Change the return type to one of the character types.
    777, 0, "scalar SQL macro cannot have argument of type DBMS_TF.TABLE_T"
    // INDEX: "SQL macro"
    // RELEASE: 20.1
    // CAUSE: DBMS_TF.TABLE_T argument was used for scalar macros.
    // ACTION:  Change the argument type to a type other than
    //          DBMS_TF.TABLE_T.
    778, 0, "PARTITION BY, ORDER BY, CLUSTER BY, or PARALLEL_ENABLE are not allowed for SQL macros"
    // MANUAL: partition by, order by, cluster by, deterministic, authid or parallel_enable
    //         not allowed for SQL macros
    // INDEX: "SQL macro"
    // RELEASE: 20.1
    // CAUSE: An attempt was made to use the PARTITION BY, ORDER BY, CLUSTER BY,
    //        DETERMINISTIC, AUTHID, or PARALLEL_ENABLE clause in a
    //        SQL macro.
    // ACTION:  Do not specify the PARTITION BY, CLUSTER BY, ORDER BY, DETERMINISTIC, AUTHID, or
    //          PARALLEL_ENABLE clause with a SQL macro.
    779, 0, "Formal parameters of type TABLE cannot have a default value."
    // MANUAL: A default value cannot be specified for parameter of type TABLE.
    // INDEX:  "SQL macros"
    // RELEASE: 20.1
    // CAUSE: A default value was specified for a formal parameter of type TABLE
    //        in a SQL macro declaration.
    // ACTION: Remove the default value from the parameter of type TABLE in
    //         the SQL macro declaration.
    //
    780, 0, "Formal parameters of type COLUMNS may only have a NULL default value."
    // MANUAL:  Parameters of type COLUMNS can only have a NULL default value.
    // INDEX:  "SQL macros"
    // RELEASE: 20.1
    // CAUSE:  A non-NULL default value was specified for a formal parameter of type COLUMNS
    //        in a polymorphic table function.
    // ACTION: Change the default value for the parameter of type COLUMNS to
    //         have a NULL default value in the polymorphic table function
    //         specification.
    //
    //
    781, 0, "SQL macro cannot be a type method"
    // INDEX:  "SQL macros"
    // RELEASE: 20.1
    // CAUSE: The SQL macro could not be declared as a method in a type specification.
    // ACTION: Use the SQL macro as a package function or a top level function.
    //
    782, 0, "A package containing SQL macro cannot be an invoker's rights package."
    // INDEX:  "SQL macros"
    // RELEASE: 20.1
    // CAUSE: A package could not be declared as AUTHID CURRENT_USER if it had a SQL
    //        macro function declared inside.
    // ACTION: Declare the package as AUTHID DEFINER if it contains one or more
    //         SQL macro functions.
    ```

Keep in mind that this functionality is not officially released and only a limited subset of it is available in 19.6: [Bug 30324180 SQL Macro should be backported to 19.5](bug-30324180-sql-macro-should-be-backported-to-19.5.md).
Hence, the final version of SQL Macro in Oracle 20 might be different from what we have now in Oracle 19.6.
