---
categories:
  - Oracle
date:
  created: 2019-09-09T23:00:00
description: >-
  APEX application calling WWV_FLOW_SECURITY.GET_OWNER_OF_CALLING_CODE started returning an incorrect user after upgrading the database to 12.2.
  It turns out that it is due to the change in behavior in DBMS_UTILITY.FORMAT_CALL_STACK.
  Thankfully, there is a diagnostic event 10934 at level 64 that can bring back the old behavior.
tags:
  - 12c
  - Diagnostic event
  - OERR
  - PL/SQL
---

# APEX WWV_FLOW_SECURITY.GET_OWNER_OF_CALLING_CODE and 12.2

Our developers were using `WWV_FLOW_API.SET_SECURITY_GROUP_ID` and were surprised to find that that procedure behaves differently in 12.2 than in 12.1.

<!-- more -->

In a nutshell, the procedure could not determine the correct security group ID after we upgraded the database to 12.2.
They asked me to help to figure out what was going on as they claimed that the code had not been changed.

Here is some background on that issue. We are using the following version of APEX which is certified against 12.2:

```sql
SQL> SELECT VERSION_NO FROM APEX_RELEASE;

VERSION_NO
------------
5.1.2.00.09
```

The procedure in question calls `WWV_FLOW_SECURITY.GET_OWNER_OF_CALLING_CODE` which, according to its name, should be returning the owner of the calling code.
However, it does not do it in our version of APEX and 12.2 anymore.
I constructed a simple test case to demonstrate the changed behavior:

```sql
SQL> grant connect, create procedure to tc_owner identified by tc_owner;

Grant succeeded.

SQL>
SQL> grant execute on apex_050100.wwv_flow_security to tc_owner;

Grant succeeded.

SQL>
SQL> create or replace procedure tc_owner.p
  2  is
  3  begin
  4    dbms_output.put_line(apex_050100.wwv_flow_security.get_owner_of_calling_code);
  5  end;
  6  /

Procedure created.

SQL> create or replace package tc_owner.pkg
  2  is
  3    procedure p;
  4  end;
  5  /

Package created.

SQL>
SQL> create or replace package body tc_owner.pkg
  2  is
  3    procedure p
  4    is
  5    begin
  6      dbms_output.put_line(apex_050100.wwv_flow_security.get_owner_of_calling_code);
  7    end p;
  8  end;
  9  /

Package body created.

SQL> grant connect to tc_connect identified by tc_connect;

Grant succeeded.

SQL> grant execute on tc_owner.p to tc_connect;

Grant succeeded.

SQL> grant execute on tc_owner.pkg to tc_connect;

Grant succeeded.
```

Let's now connect as that `TC_CONNECT` user and try to call that procedure:

```sql hl_lines="2"
TC_CONNECT@SQL> exec tc_owner.p
TC_OWNER

PL/SQL procedure successfully completed.
```

It returns `TC_OWNER` here as expected.
The result is different, though, when the same user calls the package:

```sql hl_lines="2"
TC_CONNECT@SQL> exec tc_owner.pkg.p
TC_CONNECT

PL/SQL procedure successfully completed.
```

That seems to be an incorrect result and the developers claimed that the same code was working fine before I upgraded that database to 12.2.

I quickly reviewed `WWV_FLOW_SECURITY.GET_OWNER_OF_CALLING_CODE` and identified that it is using the `DBMS_UTILITY.FORMAT_CALL_STACK` function which appears to have been changed in 12.2: [DBMS\_UTILITY.FORMAT\_CALL\_STACK Returns Subprogram Names After Upgrade to 12.2 (Doc ID 2312198.1)](https://support.oracle.com/rs?type=doc&id=2312198.1).
Indeed, the same solution from the MOS note worked flawlessly for me, so that the problem code started to return the correct user after I applied it:

```sql hl_lines="6"
TC_CONNECT@SQL> alter session set events '10934 level 64';

Session altered.

TC_CONNECT@SQL> exec tc_owner.pkg.p
TC_OWNER
```
