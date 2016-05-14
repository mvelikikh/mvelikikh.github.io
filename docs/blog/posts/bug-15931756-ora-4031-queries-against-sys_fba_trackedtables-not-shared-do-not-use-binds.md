---
categories:
  - Oracle
date:
  created: 2014-07-21T16:17:00
  updated: 2016-05-14T12:32:41
description: Столкнулся с Oracle Bug 15931756 - ORA-4031 Queries against SYS_FBA_TRACKEDTABLES not shared (do not use binds)
tags:
  - 11g
  - Bug
  - OERR
---

# Bug 15931756 - ORA-4031 Queries against SYS\_FBA\_TRACKEDTABLES not shared (do not use binds)

В одной из промышленных БД версии 11.2.0.3.7 обнаружил большое количество однотипных системных SQL, обращающихся к `SYS_FBA_TRACKEDTABLES` и использующих литералы.
В ходе анализа выяснил, что столкнулся с программной ошибкой Oracle.

<!-- more -->

Топ-10 запросов по кол-ву, которые не используют связанные переменные.

```sql
/*
Find queries that are not using bind variables
*/
select s.*,
      (select sql_text from v$sqlarea where force_matching_signature=sig and rownum=1) sql_text
  from (
       select inst_id, to_char(force_matching_signature) sig,
              count(exact_matching_signature) cnt
         from (
              select inst_id, force_matching_signature, exact_matching_signature
                from gv$sql
               group by inst_id, force_matching_signature, exact_matching_signature
              )
        group by inst_id, force_matching_signature
       having count(exact_matching_signature) > 1
        order by cnt desc
       ) s
 where rownum <= 10
```

В выводе оказалось множество запросов вида:

```sql
select FLAGS from SYS_FBA_TRACKEDTABLES where OBJ# = 1865226
select count(FA#) from SYS_FBA_TRACKEDTABLES where OBJ# = 1864581 and bitand(FLAGS, 128)=0
```

С кол-вом подобных курсоров в кол-ве 501 и 399 соответственно.

```sql
SQL> select sql_text from v$sql where force_matching_signature=15893216616221909352 and rownum<=10;
SQL_TEXT
---------------------------------------------------------------------------------
select FLAGS from SYS_FBA_TRACKEDTABLES where OBJ# = 1865226
select FLAGS from SYS_FBA_TRACKEDTABLES where OBJ# = 1865182
select FLAGS from SYS_FBA_TRACKEDTABLES where OBJ# = 1865129
select FLAGS from SYS_FBA_TRACKEDTABLES where OBJ# = 1864747
select FLAGS from SYS_FBA_TRACKEDTABLES where OBJ# = 1864989
select FLAGS from SYS_FBA_TRACKEDTABLES where OBJ# = 1865069
select FLAGS from SYS_FBA_TRACKEDTABLES where OBJ# = 1864718
select FLAGS from SYS_FBA_TRACKEDTABLES where OBJ# = 1864786
select FLAGS from SYS_FBA_TRACKEDTABLES where OBJ# = 1864815
select FLAGS from SYS_FBA_TRACKEDTABLES where OBJ# = 1864679
```

Поиск на MOS по `SYS_FBA_TRACKEDTABLES` тут же выдает, что имеет место быть:
[Bug 15931756 - ORA-4031 / Queries against SYS\_FBA\_TRACKEDTABLES not shared (do not use binds) (Doc ID 15931756.8)](https://support.oracle.com/rs?type=doc&id=15931756.8)
