---
categories:
  - Oracle
date:
  created: 2021-03-13T23:54:00
description: >-
  ORA-28094 error was thrown while selecting data from a view with a data redacation policy.
  I enable data redactiong tracing, and demonstrated that setting _strict_redaction_semantics to false can be used to work around the issue.
tags:
  - 19c
  - Diagnostic event
  - Initialization parameter
  - OERR
---

# Strict Redaction Semantics

A `DBMS_REDACT` issue has recently popped up on [SQL.RU](https://www.sql.ru/forum/1325742/pravilnoe-ispolzovanie-dbms-redact-add-policy).
This post analyzes the issue and shows a possible workaround.

<!-- more -->

## Demonstration

I constructed a simple test case to demonstrate the problem in 19.9:

```sql
set echo on lin 120

conn tc/tc@localhost/pdb

grant create table to scott identified by tiger;
alter user scott quota unlimited on users;

drop table scott.emp;
create table scott.emp(client_name varchar2(30));

insert into scott.emp values ('Larry Ellison');
insert into scott.emp values ('Jeff Bezos');
insert into scott.emp values ('Elon Musk');
insert into scott.emp values ('Vladimir Putin');
insert into scott.emp values (null);

exec dbms_redact.add_policy( -
       object_schema         => 'SCOTT', -
       object_name           => 'emp', -
       column_name           => 'CLIENT_NAME', -
       policy_name           => 'client_fio', -
       function_type         => dbms_redact.regexp, -
       regexp_pattern        => '(\S{3})(\S+)', -
       regexp_replace_string => '\1***', -
       expression            => '1 = 1' -
)

col client_name for a16
col c1 for a16
col c2 like c1
col c3 like c1
create or replace view scott.vw as
select client_name
     , nvl(client_name, 'zyzy') c1
     , case when client_name='Vla*** Put***' then 'y' else client_name end c2
     ,'Hello '||client_name c3
  from scott.emp;

grant alter session, create session to tc2 identified by tc2;

grant select on scott.vw to tc2;

conn tc2/tc2@localhost/pdb

select * from scott.vw;
```

In a nutshell, there is a table that has a data redaction policy.
There is a view built on top of it.
However, when a user tries to select from the view, it returns an error:

```sql
SQL> select * from scott.vw;
select * from scott.vw
                    *
ERROR at line 1:
ORA-28094: SQL construct not supported by data redaction
```

This restriction is mentioned in [the Advanced Security Guide](https://docs.oracle.com/en/database/oracle/oracle-database/19/asoag/oracle-data-redaction-use-with-oracle-database-features.html#GUID-FFCACD39-626A-4851-B4B2-D38225C91707):

> To avoid the `ORA-28094` error, ensure that the query has the following properties:
>
> In a CREATE VIEW definition or an inline view, there cannot be any SQL expression that involves a redacted column.

When I come across such restrictions, it is always interesting to explore if there is a way of getting around it.
Let us enable Data Redaction tracing and rerun the query:

```sql
SQL> alter session set events 'trace[radm]';

Session altered.

SQL> select * from scott.vw;
select * from scott.vw
                    *
ERROR at line 1:
ORA-28094: SQL construct not supported by data redaction
```

Here is the trace file:

``` hl_lines="50"
kzdmpci: Table obj# is: 23656
kzdmpci: Policy Name is: client_fio
kzdmpci: Policy Expression ID radm_mc$.pe# = 5001
kzdmpci: intcol# is: 1
kzdmpci: Masking Function is: 5
kzdmpci: RegExp pattern: (\S{3})(\S+) (len=12)
kzdmpci: RegExp replace: \1*** (len=5)
kzdmpci: RegExp match  :  (len=0), mpl=17
kzdmpci: no RADM policies exist, starting new RADM Policy Chain.
kzdmpci: new RADM Policy Chain ci->kkscdmpc=0x12da37ec started with  obj#=23656
kzdmpci:2: radm_pe$ lookup: for Policy Expression ID pe# 5001, pe_pexpr is [1 = 1], pe_name = [], pe_obj# = 23656
kzdmpci: added column 1 for object 23656
kzradm_vc_replace_expr_allowed: policy on table EMP

kzdmrfs: entered with opntyp of OPNTCOL
kzdmrfs: found redacted col CLIENT_NAME at 7
kzradm_vc_replace_expr_allowed: 0

kzdmchkerpna: kzpcxp(KZSERP) gave FALSE, no bypass.

kzdmchkerpna: kzpcxp(KZSERP) gave FALSE, no bypass.

kzdmchkerpna: kzpcxp(KZSERP) gave FALSE, no bypass.

kzdmchkerpna: kzpcxp(KZSERP) gave FALSE, no bypass.

kzdmchkerp: kzpcsp(KZSERP) gave FALSE, no bypass.
kzdmprqb: entered
kzdminsc: entered with opntyp=OPNTCOL

kzdminsc: view column CLIENT_NAME with KCCF2MASKDEP detected, calling kzdmpvc
kzdmpvc: level 0, column 'CLIENT_NAME' has KCCF2MASKDEP flag
kzdmpvc: level 0, calling kzdmcrmo to insert MASK operator around view column with name 'CLIENT_NAME'

kzdmcrmo: the pe# is 5001
kzdmcrmo: entered, creating MASK operator for column CLIENT_NAME of table EMP
kzdmcrmo: policy chain = 0x6319aa30
kzdmcrmo: obj# = 23656, intcol# = 1
kzdmcrmo: New ctxmask chain pgactx->ctxmask=0x62485db0 started with obj#=23656
kzdmcrmo: found object 23656
kzdmcrmo: found column 1, metadata=0x6319a988
kzdmcrmo: New ctxmask_re chain 0x62485d80 started with col=(23656,1)
kzdmcrmo: finished creating MASK operator
kzdmpvc: level 0, kzdmcrmo inserted MASK operator.
kzdminsc: entered with opntyp=OPNTCOL

kzdminsc: view column C1 with KCCF2MASKDEP detected, calling kzdmpvc
kzdmpvc: level 0, column 'C1' has KCCF2MASKDEP flag
kzdmpvc: level 0, processing SQL expression...
kzdmpvc: strict semantics disallow expression in VIEW


kzdmchkerpna: kzpcxp(KZSERP) gave FALSE, no bypass.
```

This `strict semantics disallow expression in VIEW` bit sounded intriguing, so that I decided to research what it is and how to change it:

```sql
SQL> select ksppinm, ksppdesc from x$ksppi where ksppinm like '%redaction%';

KSPPINM                        KSPPDESC
------------------------------ ----------------------------------------
_strict_redaction_semantics    Strict Data Redaction semantics
```

I set the parameter to `FALSE` and bounced the database:

```sql
SQL> alter system set "_strict_redaction_semantics"=false scope=spfile;

System altered.

$ srvctl stop database -db orcl ; srvctl start database -db orcl
```

Sure enough, that is what I got after selecting the data from the view:

```sql
SQL> select * from scott.vw;

CLIENT_NAME      C1                  C2               C3
---------------- ------------------- ---------------- -------------------
Lar*** Ell***    Lar*** Ell***       Lar*** Ell***    Hello Lar*** Ell***
Jef*** Bez***    Jef*** Bez***       Jef*** Bez***    Hello Jef*** Bez***
Elo*** Mus***    Elo*** Mus***       Elo*** Mus***    Hello Elo*** Mus***
Vla*** Put***    Vla*** Put***       y                Hello Vla*** Put***
                 zyzy                                 Hello
```

## Conclusion

Oracle obviously makes such restrictions on purpose.
There is no much information about this parameter, but there should be some corner cases due to which Oracle decided to keep the redaction semantics as strict by default.
It might be the case that Oracle will make this functionality officially available in a next release once it is ready for production use.
