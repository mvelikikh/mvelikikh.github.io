---
categories:
  - Oracle
date:
  created: 2014-12-22T21:53:00
description: >-
  Found a connection test query issued by the Play framework.
  Used SQL Trace to identify its bind variables.
  Sent recommendations to developers to use a lighter SQL query for the connection test purpose
tags:
  - Diagnostic event
  - Performance
---

# c3p0 PROBABLYNOT connection test query

Found a frequently executed SELECT query and decided to diagnose it further.

<!-- more -->

I am participating in the project, which uses the [Play framework](https://www.playframework.com/) version 1.x.
Business logic is at the application level while data is stored in the Oracle database.
An SQL query below caught my attention:

```sql
--sql_id=az33m61ym46y4
SELECT NULL AS table_cat,
       o.owner AS table_schem,
       o.object_name AS table_name,
       o.object_type AS table_type,
       NULL AS remarks
  FROM all_objects o
  WHERE o.owner LIKE :1 ESCAPE '/'
    AND o.object_name LIKE :2 ESCAPE '/'
    AND o.object_type IN ('xxx', 'TABLE')
  ORDER BY table_type, table_schem, table_name
```

This query was executed 100K times per hour.
I enabled SQL trace for a short time period to help diagnose this query further:

```sql
alter system set events 'sql_trace[sql:az33m61ym46y4] bind=true';
```

The query was executed by different users but has same bind variable data:

``` hl_lines="6 11"
BINDS #18446744071469205160:
Bind#0
  oacdty=01 mxl=32(04) mxlc=00 mal=00 scl=00 pre=00
  oacflg=03 fl2=1000010 frm=01 csi=873 siz=160 off=0
  kxsbbbfp=ffffffff7a760438  bln=32  avl=01  flg=05
  value="%"
Bind#1
  oacdty=01 mxl=128(44) mxlc=00 mal=00 scl=00 pre=00
  oacflg=03 fl2=1000010 frm=01 csi=873 siz=0 off=32
  kxsbbbfp=ffffffff7a760458  bln=128  avl=11  flg=01
  value="PROBABLYNOT"
```

Looks like we are faced with a [c3p0](http://sourceforge.net/projects/c3p0/) default connection test query.
[Play framework](https://www.playframework.com/) uses the popular [c3p0](http://sourceforge.net/projects/c3p0/) for its connection pool.
This query could be changed to something lightweight, such as:

```sql
select 'x' from dual
```

I sent that information to Java programmers and they promised to fix this issue.
