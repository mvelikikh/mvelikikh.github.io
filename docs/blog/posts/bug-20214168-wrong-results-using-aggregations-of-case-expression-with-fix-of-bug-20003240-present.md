---
categories:
  - Oracle
date:
  created: 2015-09-30T18:19:00
  updated: 2016-05-14T12:30:25
description: >-
  Encountered Oracle bug 20214168 - Wrong Results using aggregations of CASE expression with fix of bug 20003240 present.
  Identified several ways to work around it: using a patch, and undocumented parameters
tags:
  - 12c
  - Bug
  - Diagnostic event
  - Initialization parameter
---

# Bug 20214168 - Wrong Results using aggregations of CASE expression with fix of bug 20003240 present

Encountered a wrong results issue caused by [Bug 20214168 - Wrong Results using aggregations of CASE expression with fix of bug 20003240 present](https://support.oracle.com/rs?type=doc&id=20214168.8).
This post discusses possible ways to get around it.

<!-- more -->

I started using Oracle 12c in early 2014 in non-production environments.
I have been extensively testing Automatic Data Optimization, and In-Memory, and as of now got a couple of databases in production.
Those databases already have Database Bundle Patch (DBBP) 10 for engineered systems and database in-memory applied, and several underscore parameters in effect.

Unfortunately, we faced a wrong results issue a few days ago caused by [Bug 20214168 - Wrong Results using aggregations of CASE expression with fix of bug 20003240 present](https://support.oracle.com/rs?type=doc&id=20214168.8).
The problem was already discussed on the Oracle-L thread [Strange Behaviour (with Test Case)](http://www.freelists.org/post/oracle-l/Strange-Behaviour-with-Test-Case).
The original thread was Exadata specific.
Although we do not use Exadata, we use Database In-Memory.
That is why we install DBBP patches.

I found out that the solution from the Oracle-L thread with event 10055 set does not help to resolve the wrong results issue in our environment.
Let us create a test table and data from the original bug to demonstrate this:

```sql
SQL> create table test_fact(chrtype varchar2(3), rate number);
SQL> insert into test_fact values('R03', 1.3);
SQL> insert into test_fact values('LDU', 0.21);
SQL>
SQL> select *
  2    from test_fact;

CHRTYPE         RATE
--------- ----------
R03              1.3
LDU              .21
```

Now execute the query below:

```sql hl_lines="10"
SQL> select sum(
  2           case
  3             when chrtype in ('R03', 'LDU')
  4             then rate/10
  5           end) result
  6    from test_fact;

    RESULT
----------
      .041
```

Notice the wrong results - the query above should have returned 0.151 rather than 0.041.

Let us execute the same query with event 10055 set:

```sql hl_lines="12"
SQL> alter session set events '10055 trace name context forever, level 0x200';
SQL>
SQL> select sum(
  2           case
  3             when chrtype in ('R03', 'LDU')
  4             then rate/10
  5           end) result
  6    from test_fact;

    RESULT
----------
      .041
```

It can be seen that the result is the same - which is obviously wrong.
It means that event 10055 set to level 0x200 does not really help here.
I observed these results in the environment with [Patch 21188742 - Database Patch for Engineered Systems and DB In-Memory 12.1.0.2.10 (Jul2015)](https://updates.oracle.com/ARULink/PatchSearch/process_form?bug=21188742) applied.

Maybe other levels of event 10055 could help?

```sql
[oracle@localhost ~]$ oerr ora 10055
10055, 00000, "Rowsets: turn off rowsets for various operations"
// *Document: NO
// *Cause:    N/A
// *Action:   Turns off rowsets for various operations
//            Level:
//            0x00000001 - turn off for table scan
//            0x00000002 - turn off for hash join consume
//            0x00000004 - turn off for hash join produce
//            0x00000008 - turn off for group by
//            0x00000010 - turn off for sort
//            0x00000020 - turn off for table-queue out
//            0x00000040 - turn off for table-queue in
//            0x00000080 - turn off for identity
//            0x00000100 - turn off for granule iterator
//            0x00000200 - turn off for EVA functions
//            0x00000400 - turn off for PL/SQL
//            0x00000800 - turn off for upgrade
//            0x00001000 - turn off for database startup
//            0x00002000 - turn off for blobs and clobs
//            0x00004000 - turn off for tracing row source
//            0x00008000 - turn off rowset information in explain plan
//            0x00010000 - disable hash join rowsets fast path
//            0x00020000 - turn off for bloom create
//            0x00040000 - turn off for bloom use
//            0x00080000 - disable prefetch for hash join
//            0x00100000 - disable prefetch for bloom
//            0x00200000 - disable semi blocking hash join
//            0x00400000 - turn off rowset for fixed table
//
```

Unfortunately, the other levels did not help either.

I found 2 possible solutions for this problem.

1. set `_rowsets_enabled` to false:
   ```sql hl_lines="10 12 23"
   SQL> select sum(
     2           case
     3             when chrtype in ('R03', 'LDU')
     4             then rate/10
     5           end) result
     6    from test_fact;

       RESULT
   ----------
         .041
   SQL>
   SQL> alter session set "_rowsets_enabled"=false;
   SQL>
   SQL> select sum(
     2           case
     3             when chrtype in ('R03', 'LDU')
     4             then rate/10
     5           end) result
     6    from test_fact;

       RESULT
   ----------
         .151
   ```

1. set `_rowsets_max_rows` to 1:
   ```sql hl_lines="10 12 23"
   SQL> select sum(
     2           case
     3             when chrtype in ('R03', 'LDU')
     4             then rate/10
     5           end) result
     6    from test_fact;

       RESULT
   ----------
         .041
   SQL>
   SQL> alter session set "_rowsets_max_rows"=1;
   SQL>
   SQL> select sum(
     2           case
     3             when chrtype in ('R03', 'LDU')
     4             then rate/10
     5           end) result
     6    from test_fact;

       RESULT
   ----------
         .151
   ```

Of course, underscore parameters should not be used without Oracle Support's blessing.
Instead we should apply the fix for bug 20214168 ASAP.

I tried to apply patch 20214168 to this Oracle Home but OPatch informed me that the patch was already applied!

```
Recommended actions: The fixes by this patch are currently in the Oracle Home. There is no need to apply this patch.
Patch : 20214168

        Bug SubSet of 21125181
        Subset bugs are:
        20214168
```

From the `opatch lsinv` output, I saw that indeed the fix for bug 20214168 was already installed:

??? Show

    ``` hl_lines="25"

    Local Machine Information::
    Hostname: localhost
    ARU platform id: 23
    ARU platform description:: Solaris Operating System (SPARC 64-bit)

    Installed Top-level Products (1):
    Oracle Database 12c                                                  12.1.0.2.0There are 1 products installed in this Oracle Home.
    Interim patches (5) :
    Patch  20831113     : applied on Wed Aug 05 15:01:24 NOVT 2015
    Unique Patch ID:  18927529
    Patch description:  "OCW Patch Set Update : 12.1.0.2.4 (20831113)"
       Created on 23 Jun 2015, 06:58:08 hrs UTC
       Bugs fixed:
         18589889, 19139608, 19280860, 19061429, 19133945, 19341538, 20011424
    ...skip...
    Patch  21125181     : applied on Wed Aug 05 14:50:35 NOVT 2015
    Unique Patch ID:  19005983
    Patch description:  "DATABASE BUNDLE PATCH: 12.1.0.2.10 (21125181)"
       Created on 1 Jul 2015, 22:01:24 hrs PST8PDT
    Sub-patch  20594149; "DATABASE BUNDLE PATCH: 12.1.0.2.7 (20594149)"
    Sub-patch  20415006; "DATABASE BUNDLE PATCH: 12.1.0.2.6 (20415006)"
    Sub-patch  20243804; "DATABASE BUNDLE PATCH: 12.1.0.2.5 (20243804)"
       Bugs fixed:
    ...skip...
         19990543, 19012044, 20214168, 20209481, 18885870, 13640676, 13498243
    ...skip...
    Patch  19396455     : applied on Mon Jul 13 17:43:01 NOVT 2015
    Unique Patch ID:  18154832
       Created on 15 Oct 2014, 20:19:28 hrs PST8PDT
       Bugs fixed:
         19396455
    Patch  19567916     : applied on Mon Jul 13 17:41:37 NOVT 2015
    Unique Patch ID:  18878751
       Created on 1 May 2015, 01:31:51 hrs PST8PDT
       Bugs fixed:
         19567916
    Patch  20879889     : applied on Mon Jul 13 17:33:26 NOVT 2015
    Unique Patch ID:  18969474
       Created on 27 May 2015, 10:30:29 hrs PST8PDT
       Bugs fixed:
         20879889
    ```

I found that bug 21214168 is incorrectly informed as fixed whereas it is actually not: [Bug 21553476 - Wrong Results using aggregations of CASE expression with fix of bug 20003240 present in Exadata (Doc ID 21553476.8)](https://support.oracle.com/rs?type=doc&id=21553476.8).
Therefore, rather than installing patch 21214168, we should install [Patch 21553476: EXADATA X5-2 RESULTS WRONG NUMERIC CALCULATION](https://updates.oracle.com/ARULink/PatchSearch/process_form?bug=21553476).
I was unable to reproduce the wrong results issue after installing patch 21553476!

```sql hl_lines="11"
SQL> select sum(
  2           case
  3             when chrtype in ('R03', 'LDU')
  4             then rate/10
  5           end) result
  6    from test_fact
  7  /

    RESULT
----------
      .151
```
