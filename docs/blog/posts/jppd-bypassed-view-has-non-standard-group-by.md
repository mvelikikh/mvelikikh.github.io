---
categories:
  - Oracle
date:
  created: 2014-08-03T22:46:00
  updated: 2016-05-14T12:32:30
description: >-
  В ходе оптимизации запроса, выявил случай, когда JPPD (join predicate pushdown) не срабатывал для group by view.
  Указанную трансформацию удалось выполнить путём переписывания запроса в эквивалентный
tags:
  - 11g
  - 12c
  - Performance
---

# JPPD bypassed View has non-standard group by

В одной из БД Hibernate сгенерировал новый запрос, который вызвал повышенную загрузку. Я исследовал этот запрос, оптимизируется он легко, но я выявил один интересный случай, когда JPPD (join predicate pushdown) не срабатывает для group by view.

<!-- more -->

Test case (11.2.0.3):

```sql
drop table t1 cascade constraints purge;
drop table t2 cascade constraints purge;
create table t1(x,y) as select rownum, rownum from dual connect by level<=1e4;
alter table t1 modify x not null;
create index t1_y_i on t1(y);
create table t2(x,z) as select rownum, cast(dummy as char(20)) from dual connect by level<=1e5;
alter table t2 modify x not null;
create index t2_x_i on t2(x);
exec dbms_stats.gather_table_stats( '', 't1')
exec dbms_stats.gather_table_stats( '', 't2')
```

Hibernate генерировал следующий запрос:

```sql
select *
  from t1
 where y = :1
   and x not in (select x from t2 group by x);
```

С планом:

```sql
---------------------------------------------------------------------------------------
| Id  | Operation                    | Name   | Rows  | Bytes | Cost (%CPU)| Time     |
---------------------------------------------------------------------------------------
|   0 | SELECT STATEMENT             |        |     1 |     8 |    85  (25)| 00:00:02 |
|*  1 |  FILTER                      |        |       |       |            |          |
|   2 |   TABLE ACCESS BY INDEX ROWID| T1     |     1 |     8 |     2   (0)| 00:00:01 |
|*  3 |    INDEX RANGE SCAN          | T1_Y_I |     1 |       |     1   (0)| 00:00:01 |
|*  4 |   FILTER                     |        |       |       |            |          |
|   5 |    HASH GROUP BY             |        |     1 |     5 |    83  (26)| 00:00:01 |
|   6 |     INDEX FAST FULL SCAN     | T2_X_I |   100K|   488K|    65   (5)| 00:00:01 |
---------------------------------------------------------------------------------------
Predicate Information (identified by operation id):
---------------------------------------------------
   1 - filter( NOT EXISTS (SELECT 0 FROM "T2" "T2" GROUP BY "X" HAVING
              "X"=:B1))
   3 - access("Y"=TO_NUMBER(:1))
   4 - filter("X"=:B1)
```

Условие по T1 (`Y=:1`) - очень селективное. Как видно, subquery unnesting не срабатывает, а хотелось бы видеть анти-соединение, использующее INDEX RANGE SCAN индекса T2\_X\_I (индекс по T2(X)).
Рассмотрим эквивалентный запрос:

```sql
select *
  from t1
 where y = :1
   and x not in (select x from t2);
```

Его план, который бы хотелось получить для исходного запроса:

```sql
---------------------------------------------------------------------------------------
| Id  | Operation                    | Name   | Rows  | Bytes | Cost (%CPU)| Time     |
---------------------------------------------------------------------------------------
|   0 | SELECT STATEMENT             |        |     1 |    13 |     3   (0)| 00:00:01 |
|   1 |  NESTED LOOPS ANTI           |        |     1 |    13 |     3   (0)| 00:00:01 |
|   2 |   TABLE ACCESS BY INDEX ROWID| T1     |     1 |     8 |     2   (0)| 00:00:01 |
|*  3 |    INDEX RANGE SCAN          | T1_Y_I |     1 |       |     1   (0)| 00:00:01 |
|*  4 |   INDEX RANGE SCAN           | T2_X_I |   100K|   488K|     1   (0)| 00:00:01 |
---------------------------------------------------------------------------------------
Predicate Information (identified by operation id):
---------------------------------------------------
   3 - access("Y"=TO_NUMBER(:1))
   4 - access("X"="X")
```

Как еще можно переписать запрос? По логике, нужно выбрать строки из T1, которых нет в T2.
Такой запрос с Oracle синтаксисом Join:

```sql
select t1.*
  from t1,
       (select x
          from t2
         group by x) t2
 where y = :1
   and t1.x = t2.x(+)
   and t2.x is null;
```

Имеет план:

```sql
-----------------------------------------------------------------------------------------------
| Id  | Operation                    | Name   | Rows  | Bytes |TempSpc| Cost (%CPU)| Time     |
-----------------------------------------------------------------------------------------------
|   0 | SELECT STATEMENT             |        |     1 |    21 |       |   233   (4)| 00:00:03 |
|*  1 |  HASH JOIN ANTI              |        |     1 |    21 |       |   233   (4)| 00:00:03 |
|   2 |   TABLE ACCESS BY INDEX ROWID| T1     |     1 |     8 |       |     2   (0)| 00:00:01 |
|*  3 |    INDEX RANGE SCAN          | T1_Y_I |     1 |       |       |     1   (0)| 00:00:01 |
|   4 |   VIEW                       |        |   100K|  1269K|       |   228   (3)| 00:00:03 |
|   5 |    HASH GROUP BY             |        |   100K|   488K|  1192K|   228   (3)| 00:00:03 |
|   6 |     INDEX FULL SCAN          | T2_X_I |   100K|   488K|       |   228   (3)| 00:00:03 |
-----------------------------------------------------------------------------------------------
Predicate Information (identified by operation id):
---------------------------------------------------
   1 - access("T1"."X"="T2"."X")
   3 - access("Y"=TO_NUMBER(:1))
```

Мы видим, что происходит HASH JOIN ANTI (анти-соединение) без JPPD. Т.е. предикат соединения `T1.X=T2.X` - не был протолкнут внутрь GROUP BY VIEW по T2.

Выполнить проталкивание хинтами не получилось, что говорит о том, что такое VIEW для JPPD не подходит. Пришлось обратиться к трассировке CBO в поисках причин.

``` hl_lines="4"
JPPD:     JPPD bypassed: View has non-standard group by.
JPPD: Applying transformation directives
JPPD: Checking validity of push-down in query block SEL$6D455ABB (#1)
JPPD:   No valid views found to push predicate into.
```

Вот это уже информация для анализа. Мы видим, что JPPD не сработал, т.к. View: "has non-standard group by". Подумав, я написал следующий запрос:

```sql hl_lines="4"
select t1.*
  from t1,
       (select x,
               count(*)
          from t2
         group by x) t2
 where y=:1
   and t1.x = t2.x(+)
   and t2.x is null;
```

Его план:

```sql
---------------------------------------------------------------------------------------
| Id  | Operation                    | Name   | Rows  | Bytes | Cost (%CPU)| Time     |
---------------------------------------------------------------------------------------
|   0 | SELECT STATEMENT             |        |     1 |    10 |     3   (0)| 00:00:01 |
|   1 |  NESTED LOOPS ANTI           |        |     1 |    10 |     3   (0)| 00:00:01 |
|   2 |   TABLE ACCESS BY INDEX ROWID| T1     |     1 |     8 |     2   (0)| 00:00:01 |
|*  3 |    INDEX RANGE SCAN          | T1_Y_I |     1 |       |     1   (0)| 00:00:01 |
|   4 |   VIEW PUSHED PREDICATE      |        |     1 |     2 |     1   (0)| 00:00:01 |
|   5 |    SORT GROUP BY             |        |     1 |     5 |     1   (0)| 00:00:01 |
|*  6 |     INDEX RANGE SCAN         | T2_X_I |     1 |     5 |     1   (0)| 00:00:01 |
---------------------------------------------------------------------------------------
Predicate Information (identified by operation id):
---------------------------------------------------
   3 - access("Y"=TO_NUMBER(:1))
   6 - access("X"="T1"."X")
```

По сути дела, мы запрос:

```sql
select t1.*
  from t1,
       (select x
          from t2
         group by x) t2
 where y = :1
   and t1.x = t2.x(+)
   and t2.x is null;
```

Переписали в эквивалентный:

```sql hl_lines="4"
select t1.*
  from t1,
       (select x,
               count(*)
          from t2
         group by x) t2
 where y=:1
   and t1.x = t2.x(+)
   and t2.x is null;
```

И это позволило выполнить JPPD, что видно в плане и в трассе CBO:

``` hl_lines="7"
***********************************
Cost-Based Join Predicate Push-down
***********************************
JPPD: Checking validity of push-down in query block SEL$6D455ABB (#1)
JPPD:   Checking validity of push-down from query block SEL$6D455ABB (#1) to query block SEL$2 (#2)
Check Basic Validity for Non-Union View for query block SEL$2 (#2)
JPPD:     Passed validity checks
JPPD: JPPD:   Pushdown from query block SEL$6D455ABB (#1) passed validity checks.
Join-Predicate push-down on query block SEL$6D455ABB (#1)
JPPD: Using search type: linear
JPPD: Considering join predicate push-down
JPPD: Starting iteration 1, state space = (2) : (0)
JPPD: Performing join predicate push-down (no transformation phase) from query block SEL$6D455ABB (#1) to query block SEL$2 (#2)
```

Пока это похоже на существующее ограничение CBO.
Указанное поведение проверялось в 11.2.0.3 и 12.1.0.1.
