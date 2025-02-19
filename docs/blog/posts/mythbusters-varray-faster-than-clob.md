---
categories:
  - Oracle
date:
  created: 2021-12-18T17:36:00
description: >-
  There was a statement that VARRAY faster than CLOB for a specific query.
  I tested it and found that it is generally not the case.
  This post demonstrates the testing I conducted and its results.
tags:
  - 19c
  - LOB
  - Performance
---

# Mythbusters: VARRAY faster than CLOB

There has been a [tweet](https://twitter.com/dbms_xtender/status/1469476734240178178) recently saying that `VARRAY` is faster than `CLOB`.
I found that it is generally not the case, and conducted additional tests to support this statement in this post.

<!-- more -->

On the data set from the tweet with SQL\*Plus, the correctness of the statement largely depends on the underlying hardware on the database, and the network between the client and the server.
More specifically, `VARRAY` will be faster with a rather slow network.

A typical production environment that I work with includes one or more databases deploying across different availability zones (AZ) on the cloud.
The applications reside in the same AZ as the database server to avoid inter-AZ traffic that costs extra money.
I tested the script from [this Gist](https://gist.github.com/xtender/4ccc1bcae16883c0f1e80a0fb8404963) across two major cloud providers and `VARRAY` was never faster than `CLOB`.
In fact, it is significantly slower.
See the output from 19.13 below (the script is from [this Gist](https://gist.github.com/xtender/4ccc1bcae16883c0f1e80a0fb8404963) - I just added the last query with `DBMS_LOB`):

```sql hl_lines="25 45 80 115"
[oracle@rac2 ~]$ NLS_LANG=.AL32UTF8 sqlplus tc/tc@rac1:1522/pdb1 @test1

SQL*Plus: Release 19.0.0.0.0 - Production on Sat Dec 18 10:54:03 2021
Version 19.13.0.0.0

Copyright (c) 1982, 2021, Oracle.  All rights reserved.

Last Successful login time: Sat Dec 18 2021 10:53:17 +00:00

Connected to:
Oracle Database 19c Enterprise Edition Release 19.0.0.0.0 - Production
Version 19.13.0.0.0

SQL> set lobprefetch 32767
SQL> set long 10000000
SQL> set longchunksize 10000000
SQL> set timing on;
SQL> set arraysize 1000;
SQL> --set feedback only
SQL> set autotrace trace stat;
SQL> select id,c_lob from t_lob_1_mb where id<=25;

25 rows selected.

Elapsed: 00:00:01.50

Statistics
----------------------------------------------------------
          0  recursive calls
          0  db block gets
         82  consistent gets
       6475  physical reads
          0  redo size
   51655001  bytes sent via SQL*Net to client
      15345  bytes received via SQL*Net from client
         52  SQL*Net roundtrips to/from client
          0  sorts (memory)
          0  sorts (disk)
         25  rows processed

SQL> select id,lob_to_varray(c_lob) c_varray from t_lob_1_mb where id<=25;

25 rows selected.

Elapsed: 00:00:14.10

Statistics
----------------------------------------------------------
         33  recursive calls
          0  db block gets
        199  consistent gets
     653950  physical reads
          0  redo size
   25107664  bytes sent via SQL*Net to client
       9261  bytes received via SQL*Net from client
         61  SQL*Net roundtrips to/from client
         25  sorts (memory)
          0  sorts (disk)
         25  rows processed

SQL>
SQL> select
  2    c_varray
  3  from t_lob_1_mb
  4       outer apply (
  5         select
  6           cast(
  7             collect(
  8                cast(substr(c_lob,(level-1)*4000 + 1,4000) as varchar2(4000))
  9                )
 10             as sys.odcivarchar2list
 11           ) c_varray
 12         from dual
 13         connect by level<=ceil(length(c_lob)/4000)
 14       )
 15  where id<=25;

25 rows selected.

Elapsed: 00:00:14.16

Statistics
----------------------------------------------------------
          0  recursive calls
          0  db block gets
        176  consistent gets
     653950  physical reads
          0  redo size
   25106012  bytes sent via SQL*Net to client
       9086  bytes received via SQL*Net from client
         58  SQL*Net roundtrips to/from client
         50  sorts (memory)
          0  sorts (disk)
         25  rows processed

SQL>
SQL> select
  2    c_varray
  3  from t_lob_1_mb
  4       outer apply (
  5         select
  6           cast(
  7             collect(
  8                dbms_lob.substr(c_lob,4000,(level-1)*4000 + 1)
  9                )
 10             as sys.odcivarchar2list
 11           ) c_varray
 12         from dual
 13         connect by level<=ceil(length(c_lob)/4000)
 14       )
 15  where id<=25;

25 rows selected.

Elapsed: 00:00:03.19

Statistics
----------------------------------------------------------
          0  recursive calls
          0  db block gets
        176  consistent gets
      24900  physical reads
          0  redo size
   25106012  bytes sent via SQL*Net to client
       9071  bytes received via SQL*Net from client
         58  SQL*Net roundtrips to/from client
         50  sorts (memory)
          0  sorts (disk)
         25  rows processed
```

**NB**: the `DBMS_LOB` query is not mentioned in the original tweet, but I wrote why `SUBSTR` should not be used against LOB's in 2019: [Temporary LOBs](temporary-lobs.md).
As I said, it is quite a typical cloud environment in which the client is on a different VM from the DB server.
I can get even better results with `CLOB` if I run the same script on the DB server itself or use a proximity placement group (Azure)/cluster placement group (AWS).

It can be seen that there is twice as much data transfered with `CLOB` than with the other queries (**50MB** vs **25MB**).
It is a known issue that was already observed by several other authors, e.g. [LOB reads](https://jonathanlewis.wordpress.com/2019/08/01/lob-reads/).
In the specific example from this post, the extra `CLOB` data will become noticeable on a slow network, e.g. me pulling data from a different continent on a mobile broadband.
It is not the case in most environments (including non-productions) that I work with - `CLOB` will be faster than `VARRAY` (**1.5 seconds** vs **14.16 seconds**).

As always, rather than relying on any information, such as the tweet above, it is better to test it for yourself as this post demonstrates.
