---
categories:
  - Oracle
date:
  created: 2020-06-13T01:07:00
description: >-
  Encountered a wrong results issue on a query with a CURSOR expression.
  Found out the root cause in the trace file.
  It turns out to be an Oracle Bug 30528947 - Nested Query Using CURSOR Expression Returns Wrong Result (Doc ID 30528947.8).
tags:
  - 18c
  - 19c
  - Bug
---

# CURSOR Expressions Return Wrong Results in 18c/19c

There is a wrong results issue I stumbled upon this morning.
A developer told me that one of their queries started returning wrong results after we upgraded one of our databases from 12.2.0.1 to 19.7.

<!-- more -->

I constructed a simplified test case to demonstrate this issue which I ran on 19.4.
I have been able to reproduce it on 18.3, 19.7, and [Live SQL](https://livesql.oracle.com) as well.

```sql
SQL> create table t1(id int);

Table created.

SQL> create table t2(id int);

Table created.

SQL>
SQL> insert into t1 values (1);

1 row created.

SQL> insert into t2 values (1);

1 row created.
```

In a nutshell, I created two tables that have one row with a numeric 1 value.
Let's now run the following query:

```sql hl_lines="19"
SQL> select query_type
  2    from (select 'A' query_type
  3            from t1 t11
  4           where exists (
  5                   select null
  6                     from t2 t21
  7                    where t21.id = t11.id)
  8           union all
  9          select 'B' query_type
 10            from t1 t12
 11           where not exists (
 12                   select null
 13                     from t2 t22
 14                    where t22.id = t12.id)
 15         );

Q
-
A
```

Then, I am going to put that query into a `CURSOR` expression:

```sql hl_lines="28"
SQL> select cursor(
  2           select query_type
  3             from (select 'A' query_type
  4                     from t1 t11
  5                    where exists (
  6                            select null
  7                              from t2 t21
  8                             where t21.id = t11.id)
  9                    union all
 10                   select 'B' query_type
 11                     from t1 t12
 12                    where not exists (
 13                            select null
 14                              from t2 t22
 15                             where t22.id = t12.id)
 16                  )
 17         ) data
 18    from dual;

DATA
--------------------
CURSOR STATEMENT : 1

CURSOR STATEMENT : 1

Q
-
B
```

That is when it gets interesting.
Somehow the query which returned `'A'` being run separately starts returning `'B'` after it comes as an input subquery into a `CURSOR` expression.

I initially started looking at the execution plan in an attempt to figure out what changed in the execution plan between 12.2 and 19c.
There are some changes but nothing that drew my eye.

```sql
PLAN_TABLE_OUTPUT
--------------------------------------------------------------------------------
Plan hash value: 2197603499

-----------------------------------------------------------------------------
| Id  | Operation            | Name | Rows  | Bytes | Cost (%CPU)| Time     |
-----------------------------------------------------------------------------
|   0 | SELECT STATEMENT     |      |     1 |       |    14   (0)| 00:00:01 |
|   1 |  VIEW                |      |     2 |     6 |    12   (0)| 00:00:01 |
|   2 |   UNION-ALL          |      |       |       |            |          |
|*  3 |    FILTER            |      |       |       |            |          |
|   4 |     TABLE ACCESS FULL| T1   |     1 |    13 |     3   (0)| 00:00:01 |
|*  5 |     TABLE ACCESS FULL| T2   |     1 |    13 |     3   (0)| 00:00:01 |
|*  6 |    FILTER            |      |       |       |            |          |
|   7 |     TABLE ACCESS FULL| T1   |     1 |    13 |     3   (0)| 00:00:01 |
|*  8 |     TABLE ACCESS FULL| T2   |     1 |    13 |     3   (0)| 00:00:01 |
|   9 |  FAST DUAL           |      |     1 |       |     2   (0)| 00:00:01 |
-----------------------------------------------------------------------------

Query Block Name / Object Alias (identified by operation id):
-------------------------------------------------------------

   1 - SET$1 / from$_subquery$_001@SEL$2
   2 - SET$1
   3 - SEL$3
   4 - SEL$3 / T11@SEL$3
   5 - SEL$4 / T21@SEL$4
   6 - SEL$5
   7 - SEL$5 / T12@SEL$5
   8 - SEL$6 / T22@SEL$6
   9 - SEL$1 / DUAL@SEL$1

Outline Data
-------------

  /*+
      BEGIN_OUTLINE_DATA
      FULL(@"SEL$6" "T22"@"SEL$6")
      FULL(@"SEL$4" "T21"@"SEL$4")
      PQ_FILTER(@"SEL$3" SERIAL)
      FULL(@"SEL$3" "T11"@"SEL$3")
      PQ_FILTER(@"SEL$5" SERIAL)
      FULL(@"SEL$5" "T12"@"SEL$5")
      NO_ACCESS(@"SEL$2" "from$_subquery$_001"@"SEL$2")
      OUTLINE_LEAF(@"SEL$1")
      OUTLINE_LEAF(@"SEL$2")
      OUTLINE_LEAF(@"SET$1")
      OUTLINE_LEAF(@"SEL$5")
      OUTLINE_LEAF(@"SEL$6")
      OUTLINE_LEAF(@"SEL$3")
      OUTLINE_LEAF(@"SEL$4")
      ALL_ROWS
      DB_VERSION('19.1.0')
      OPTIMIZER_FEATURES_ENABLE('19.1.0')
      IGNORE_OPTIM_EMBEDDED_HINTS
      END_OUTLINE_DATA
  */

Predicate Information (identified by operation id):
---------------------------------------------------

   3 - filter( EXISTS (SELECT 0 FROM "T2" "T21" WHERE "T21"."ID"=:B1))
   5 - filter("T21"."ID"=:B1)
   6 - filter( NOT EXISTS (SELECT 0 FROM "T2" "T22" WHERE
              "T22"."ID"=:B1))
   8 - filter("T22"."ID"=:B1)

Note
-----
   - dynamic statistics used: dynamic sampling (level=2)

68 rows selected.
```

The `gather_plan_statistics` hint was not really helpful as it is a nested cursor, so that it does not show the rowsource statistics from that level - the nested cursor runs separately and its rowsource statistics are not included in the top-level cursor ones:

```sql
-----------------------------------------------------------------------------
| Id  | Operation            | Name | Starts | E-Rows | A-Rows |   A-Time   |
-----------------------------------------------------------------------------
|   0 | SELECT STATEMENT     |      |      1 |        |      1 |00:00:00.01 |
|   1 |  VIEW                |      |      0 |      2 |      0 |00:00:00.01 |
|   2 |   UNION-ALL          |      |      0 |        |      0 |00:00:00.01 |
|*  3 |    FILTER            |      |      0 |        |      0 |00:00:00.01 |
|   4 |     TABLE ACCESS FULL| T1   |      0 |      1 |      0 |00:00:00.01 |
|*  5 |     TABLE ACCESS FULL| T2   |      0 |      1 |      0 |00:00:00.01 |
|*  6 |    FILTER            |      |      0 |        |      0 |00:00:00.01 |
|   7 |     TABLE ACCESS FULL| T1   |      0 |      1 |      0 |00:00:00.01 |
|*  8 |     TABLE ACCESS FULL| T2   |      0 |      1 |      0 |00:00:00.01 |
|   9 |  FAST DUAL           |      |      1 |      1 |      1 |00:00:00.01 |
-----------------------------------------------------------------------------

Predicate Information (identified by operation id):
---------------------------------------------------

   3 - filter( IS NOT NULL)
   5 - filter("T21"."ID"=:B1)
   6 - filter( IS NULL)
   8 - filter("T22"."ID"=:B1)
```

I found the explanation of this issue in the SQL trace file:

``` hl_lines="34 41 45"
=====================
PARSING IN CURSOR #139973723001152 len=579 dep=0 uid=78 oct=3 lid=78 tim=4622189819 hv=2185287422 ad='68d3c950' sql
id='0mkkpha141pry'
select cursor(
         select query_type
           from (select 'A' query_type
                   from t1 t11
                  where exists (
                          select null
                            from t2 t21
                           where t21.id = t11.id)
                  union all
                 select 'B' query_type
                   from t1 t12
                  where not exists (
                          select null
                            from t2 t22
                           where t22.id = t12.id)
                )
       ) data
  from dual
END OF STMT
PARSE #139973723001152:c=11048,e=12511,p=0,cr=45,cu=12,mis=1,r=0,dep=0,og=1,plh=2197603499,tim=4622189819
EXEC #139973723001152:c=13,e=13,p=0,cr=0,cu=0,mis=0,r=0,dep=0,og=1,plh=2197603499,tim=4622189873
=====================
PARSING IN CURSOR #139973720520408 len=272 dep=2 uid=78 oct=3 lid=78 tim=4622190302 hv=3362864010 ad='68d141b0' sqlid='faj0udr472fwa'
SELECT "A2"."QUERY_TYPE" "QUERY_TYPE"
  FROM  (
          (SELECT 'A' "QUERY_TYPE"
             FROM "T1" "A5"
            WHERE  EXISTS (
                     SELECT 0
                       FROM "T2" "A6"
                      WHERE "A6"."ID"=:CV1$))
           UNION ALL
          (SELECT 'B' "QUERY_TYPE"
             FROM "T1" "A4"
            WHERE  NOT EXISTS (
                     SELECT 0
                       FROM "T2" "A7"
                      WHERE "A7"."ID"=:CV2$))) "A2"
END OF STMT
PARSE #139973720520408:c=375,e=375,p=0,cr=0,cu=0,mis=1,r=0,dep=2,og=1,plh=0,tim=4622190302
..skip..
BINDS #139973720520408:

 Bind#0
  oacdty=02 mxl=22(00) mxlc=00 mal=00 scl=00 pre=00
  oacflg=11 fl2=0001 frm=00 csi=00 siz=48 off=0
  kxsbbbfp=7f4e2be3b278  bln=22  avl=00  flg=05
 Bind#1
  oacdty=02 mxl=22(00) mxlc=00 mal=00 scl=00 pre=00
  oacflg=11 fl2=0001 frm=00 csi=00 siz=0 off=24
  kxsbbbfp=7f4e2be3b290  bln=22  avl=00  flg=01
EXEC #139973720520408:c=9732,e=9360,p=0,cr=37,cu=0,mis=1,r=0,dep=2,og=1,plh=489056501,tim=4622199711
FETCH #139973723001152:c=10218,e=9845,p=0,cr=37,cu=0,mis=0,r=1,dep=0,og=1,plh=2197603499,tim=4622199753
STAT #139973723001152 id=1 cnt=0 pid=0 pos=1 obj=0 op='VIEW  (cr=0 pr=0 pw=0 str=0 time=0 us cost=12 size=6 card=2)'
STAT #139973723001152 id=2 cnt=0 pid=1 pos=1 obj=0 op='UNION-ALL  (cr=0 pr=0 pw=0 str=0 time=0 us)'
STAT #139973723001152 id=3 cnt=0 pid=2 pos=1 obj=0 op='FILTER  (cr=0 pr=0 pw=0 str=0 time=0 us)'
STAT #139973723001152 id=4 cnt=0 pid=3 pos=1 obj=25013 op='TABLE ACCESS FULL T1 (cr=0 pr=0 pw=0 str=0 time=0 us cost=3 size=13 card=1)'
STAT #139973723001152 id=5 cnt=0 pid=3 pos=2 obj=25014 op='TABLE ACCESS FULL T2 (cr=0 pr=0 pw=0 str=0 time=0 us cost=3 size=13 card=1)'
STAT #139973723001152 id=6 cnt=0 pid=2 pos=2 obj=0 op='FILTER  (cr=0 pr=0 pw=0 str=0 time=0 us)'
STAT #139973723001152 id=7 cnt=0 pid=6 pos=1 obj=25013 op='TABLE ACCESS FULL T1 (cr=0 pr=0 pw=0 str=0 time=0 us cost=3 size=13 card=1)'
STAT #139973723001152 id=8 cnt=0 pid=6 pos=2 obj=25014 op='TABLE ACCESS FULL T2 (cr=0 pr=0 pw=0 str=0 time=0 us cost=3 size=13 card=1)'
STAT #139973723001152 id=9 cnt=1 pid=0 pos=2 obj=0 op='FAST DUAL  (cr=0 pr=0 pw=0 str=1 time=0 us cost=2 size=0 card=1)'
FETCH #139973720520408:c=178,e=177,p=0,cr=8,cu=0,mis=0,r=1,dep=0,og=1,plh=489056501,tim=4622200599
STAT #139973720520408 id=1 cnt=1 pid=0 pos=1 obj=0 op='VIEW  (cr=9 pr=0 pw=0 str=1 time=179 us cost=12 size=6 card=2)'
STAT #139973720520408 id=2 cnt=1 pid=1 pos=1 obj=0 op='UNION-ALL  (cr=9 pr=0 pw=0 str=1 time=177 us)'
STAT #139973720520408 id=3 cnt=0 pid=2 pos=1 obj=0 op='FILTER  (cr=1 pr=0 pw=0 str=1 time=8 us)'
STAT #139973720520408 id=4 cnt=0 pid=3 pos=1 obj=25013 op='TABLE ACCESS FULL T1 (cr=0 pr=0 pw=0 str=0 time=0 us cost=3 size=0 card=1)'
STAT #139973720520408 id=5 cnt=0 pid=3 pos=2 obj=25014 op='TABLE ACCESS FULL T2 (cr=1 pr=0 pw=0 str=1 time=6 us cost=3 size=13 card=1)'
STAT #139973720520408 id=6 cnt=1 pid=2 pos=2 obj=0 op='FILTER  (cr=8 pr=0 pw=0 str=1 time=164 us)'
STAT #139973720520408 id=7 cnt=1 pid=6 pos=1 obj=25013 op='TABLE ACCESS FULL T1 (cr=7 pr=0 pw=0 str=1 time=144 us cost=3 size=0 card=1)'
STAT #139973720520408 id=8 cnt=0 pid=6 pos=2 obj=25014 op='TABLE ACCESS FULL T2 (cr=1 pr=0 pw=0 str=1 time=9 us cost=3 size=13 card=1)'
FETCH #139973723001152:c=0,e=0,p=0,cr=0,cu=0,mis=0,r=0,dep=0,og=0,plh=2197603499,tim=4622200901
CLOSE #139973720520408:c=3,e=2,dep=1,type=0,tim=4622201312
CLOSE #139973723001152:c=6,e=193,dep=0,type=0,tim=4622201500
```

That is where the most remarkable part happens.
The subquery is modified in an awfully wrong way: the columns of the outer queries disappear from the inner queries, and they are replaced with some bind variables: `CV1$`, `CV2$`.
Those variables, which are of the `NUMBER` data type, are set to `NULL`.
Then, the `'A'` branch of the `UNION ALL`, which uses `EXISTS`, returns nothing.
The `'B'` branch, which uses `NOT EXISTS`, returns the `'B'` row since the `NOT EXISTS` subquery brings back an empty result set.
At this stage the root cause of the wrong results issue is known.
Obviously, I have no clue why those variables were introduced but I know why that query returns that result.

I tried to tinker around with that query a little bit to see what can be done to make it work, and here is a short summary of my findings:

- Correlated subqueries are essential.
  The query starts returning the correct results (one `'A'` row) once I decorrelate the subqueries:
  ```sql hl_lines="26"
  SQL> select cursor(
    2           select query_type
    3             from (select 'A' query_type
    4                     from t1 t11
    5                    where id in (
    6                            select id
    7                              from t2 t21)
    8                    union all
    9                   select 'B' query_type
   10                     from t1 t12
   11                    where id not in (
   12                            select id
   13                              from t2 t22)
   14                  )
   15         ) data
   16    from dual;

  DATA
  --------------------
  CURSOR STATEMENT : 1

  CURSOR STATEMENT : 1

  Q
  -
  A
  ```

- Nesting of the subqueries does matter.
  For instance, the query returns the correct results after I reduce the nesting level:
  ```sql hl_lines="26"
  SQL> select cursor(
    2           select 'A' query_type
    3             from t1 t11
    4            where exists (
    5                    select null
    6                      from t2 t21
    7                     where t21.id = t11.id)
    8            union all
    9           select 'B' query_type
   10             from t1 t12
   11            where not exists (
   12                    select null
   13                      from t2 t22
   14                     where t22.id = t12.id)
   15         ) data
   16    from dual;

  DATA
  --------------------
  CURSOR STATEMENT : 1

  CURSOR STATEMENT : 1

  Q
  -
  A
  ```

Based on how Oracle modifies the subquery under the hood, certain CURSOR expressions can return:

- Less rows:
  ```sql hl_lines="32 58 59"
  SQL> doc
  DOC>##############################
  DOC>   Less rows
  DOC>##############################
  DOC>#
  SQL>
  SQL> select cursor(
    2           select query_type
    3             from (select 'A' query_type
    4                     from t1 t11
    5                    where exists (
    6                            select null
    7                              from t2 t21
    8                             where t21.id = t11.id)
    9                    union all
   10                   select 'B' query_type
   11                     from t1 t12
   12                    where exists (
   13                            select null
   14                              from t2 t22
   15                             where t22.id = t12.id)
   16                  )
   17         ) data
   18    from dual;

  DATA
  --------------------
  CURSOR STATEMENT : 1

  CURSOR STATEMENT : 1

  no rows selected


  SQL>
  SQL> doc
  DOC>   The cursor subquery
  DOC>#
  SQL> select query_type
    2    from (select 'A' query_type
    3            from t1 t11
    4           where exists (
    5                   select null
    6                     from t2 t21
    7                    where t21.id = t11.id)
    8           union all
    9          select 'B' query_type
   10            from t1 t12
   11           where exists (
   12                   select null
   13                     from t2 t22
   14                    where t22.id = t12.id)
   15         )
   16  ;

  Q
  -
  A
  B
  ```

- More rows:
  ```sql hl_lines="30 31 52"
  SQL> doc
  DOC>##############################
  DOC>   More rows
  DOC>##############################
  DOC>#
  SQL>
  SQL> select cursor(
    2           select query_type
    3             from (select 'A' query_type
    4                     from t1 t11
    5                    union all
    6                   select 'B' query_type
    7                     from t1 t12
    8                    where not exists (
    9                            select null
   10                              from t2 t22
   11                             where t22.id = t12.id)
   12                  )
   13         ) data
   14    from dual;

  DATA
  --------------------
  CURSOR STATEMENT : 1

  CURSOR STATEMENT : 1

  Q
  -
  A
  B


  SQL>
  SQL> doc
  DOC>   The cursor subquery
  DOC>#
  SQL> select query_type
    2    from (select 'A' query_type
    3            from t1 t11
    4           union all
    5          select 'B' query_type
    6            from t1 t12
    7           where not exists (
    8                   select null
    9                     from t2 t22
   10                    where t22.id = t12.id)
   11         );

  Q
  -
  A
  ```

- Different values as it was demostrated in the beginning of this post

The good news is that it is a known documented issue: [Bug 30528947 - Nested Query Using CURSOR Expression Returns Wrong Result (Doc ID 30528947.8)](https://support.oracle.com/rs?type=doc&id=30528947.8).
There are patches available for some release updates.
The bad news is that the issue is not mentioned on the document I would expect it to be: [Things to Consider to Avoid Prominent Wrong Result Problems on 19C Proactively (Doc ID 2606585.1)](https://support.oracle.com/rs?type=doc&id=2606585.1).
How is one supposed to avoid such issues?
I always read those 'things to consider' before I devise any upgrade plans.

The script, a sample trace file, and the spool file used in this post are below:

- ??? "Script"
      ```sql
      --8<-- "cursor-expressions-return-wrong-results-in-18c19c/cursor_expr.sql"
      ```

- [Sample trace file](cursor-expressions-return-wrong-results-in-18c19c/orcl_ora_4321.trc)

- [Spool file](cursor-expressions-return-wrong-results-in-18c19c/output.txt)
