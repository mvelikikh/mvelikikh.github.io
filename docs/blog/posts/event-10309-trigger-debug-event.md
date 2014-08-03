---
categories:
  - Oracle
date:
  created: 2014-07-22T20:26:00
  updated: 2014-08-03T21:21:56
description: Event 10309, or Trigger Debug event, can be used to show when and what triggers are fired
tags:
  - 11g
  - Diagnostic event
  - PL/SQL
---

# Event 10309: Trigger Debug event

Event 10309, or Trigger Debug event, can be used to show when and what triggers are fired.

<!-- more -->

```
[oracle@oracle ~]$ oerr ora 10309
10309, 00000, "Trigger Debug event"
// *Document: NO
// *Cause:
// *Action:
// *Comment: This event replaces the earlier event number 10250
//           which had multiple definitions
```

Test case (run on 11.2.0.3):

```sql
drop user tc cascade;
grant connect to tc identified by tc;
grant alter session to tc;
grant create table to tc;
grant create trigger to tc;
alter user tc quota 100M on users;

conn tc/tc
create table t(x int);
create trigger t_bi
  before insert on t
declare
begin
  null;
end;
/
create trigger t_bir
  before insert on t
  for each row
declare
begin
  null;
end;
/
create trigger t_air
  after insert on t
  for each row
declare
begin
  null;
end;
/
alter session set events '10309';
insert into t values (0);
select value from v$diag_info where name='Default Trace File';
```

Trace file:

```
*** 2014-07-21 09:42:05.051
*** SESSION ID:(76.9819) 2014-07-21 09:42:05.051
*** CLIENT ID:() 2014-07-21 09:42:05.051
*** SERVICE NAME:(SYS$USERS) 2014-07-21 09:42:05.051
*** MODULE NAME:(SQL*Plus) 2014-07-21 09:42:05.051
*** ACTION NAME:() 2014-07-21 09:42:05.051

--------Dumping Sorted Master Trigger List --------
Trigger Owner : TC
Trigger Name : T_AIR
Trigger Owner : TC
Trigger Name : T_BIR
Trigger Owner : TC
Trigger Name : T_BI
--------Dumping Trigger Sublists --------
 trigger sublist 0 :
Trigger Owner : TC
Trigger Name : T_BI
 trigger sublist 1 :
Trigger Owner : TC
Trigger Name : T_BIR
 trigger sublist 2 :
 trigger sublist 3 :
Trigger Owner : TC
Trigger Name : T_AIR
 trigger sublist 4 :
--------Dumping Sorted Master Trigger List --------
Trigger Owner : TC
Trigger Name : T_AIR
Trigger Owner : TC
Trigger Name : T_BIR
Trigger Owner : TC
Trigger Name : T_BI
--------Dumping Trigger Sublists --------
 trigger sublist 0 :
Trigger Owner : TC
Trigger Name : T_BI
 trigger sublist 1 :
Trigger Owner : TC
Trigger Name : T_BIR
 trigger sublist 2 :
 trigger sublist 3 :
Trigger Owner : TC
Trigger Name : T_AIR
 trigger sublist 4 :

*** 2014-07-21 09:42:05.073
Firing Insert Before Table Trigger. Name: T_BI Owner TC
Firing Insert Before Row Trigger. Name: T_BIR Owner TC
Firing Insert After Row Trigger. Name: T_AIR Owner TC
```
