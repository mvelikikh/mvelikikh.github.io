---
categories:
  - Oracle
date:
  created: 2025-08-07
description: >-
  Некоторые числовые диагностические события преобразуются Oracle в эквивалентные Unified Tracing Service (UTS).
  Показано, как это происходит, и какие это события
tags:
  - 19c
  - Code symbol
  - Diagnostic event
  - OERR
---

# Преобразование некоторых числовых диагностических событий к эквивалентному Unified Tracing Service синтаксису

В ходе чтения предыдущей заметки [Текстовые синонимы числовых диагностических событий](text-aliases-of-numeric-events.md) может возникнуть вопрос: а что происходит с, пожалуй, самыми популярными числовыми событиями 10046 и 10053?
Ответ на этот вопрос требует отдельного изучения и анализа.

<!-- more -->

## Событие 10046 и sql\_trace {: #10046 }

Рассмотрим несколько примеров использования событий 10046 и `sql_trace`:

```sql
SQL> alter session set events '10046 level 1';

Session altered.

SQL> alter session set events 'sql_trace level 1';

Session altered.
```

На первый взгляд, синтаксис идентичен. Однако, `sql_trace` предоставляет ряд дополнительных параметров, которые могут быть заданы в 10046 установкой подходящего уровня:

```
SQL> oradebug doc event name sql_trace
                                                                                                                                                                          sql_trace: event for sql trace

Usage
-------
sql_trace
   wait            < false | true >,
   bind            < false | true >,
   plan_stat       < never | first_execution | all_executions | adaptive >,
   level           <ub4>
```

Рассмотрим некоторые сценарии отдельного и совместного использования событий 10046 и `sql_trace`:

```sql title="Преобразование 10046 level 12 в sql_trace level 12"
SQL> alter session set events '10046 level 12';

Session altered.

SQL> oradebug setmypid
Statement processed.
SQL> oradebug eventdump session
sql_trace level=12
```

```sql title="sql_trace off отключает 10046"
SQL> alter session set events '10046 level 1';

Session altered.

SQL> oradebug eventdump session
sql_trace level=1
SQL> alter session set events 'sql_trace off';

Session altered.

SQL> oradebug eventdump session
Statement processed.
```

```sql title="10046 off отключает sql_trace"
SQL> alter session set events 'sql_trace wait=true';

Session altered.

SQL> oradebug eventdump session
sql_trace wait=true
SQL>
SQL> alter session set events '10046 off';

Session altered.

SQL> oradebug eventdump session
Statement processed.
```

```sql title="Попытка использования scope для 10046 завершается ошибкой, но работает для случайного события 12345"
SQL> alter session set events '10046 [sql: 1111111111111 | 2222222222222]';
ERROR:
ORA-49100: Failed to process event statement [10046 [sql: 1111111111111 |
2222222222222]]
ORA-49160: Scope or Filter cannot be specified for mapped event, use [sql_trace
level=1]

SQL> alter session set events '12345 [sql: 1111111111111 | 2222222222222]';

Session altered.
```

!!! abstract "Вывод"

    Синтаксис, использующий событие 10046, преобразуется к эквивалентному UTS синтаксису, использующему событие `sql_trace`.

## Событие 10053 и trace[SQL\_Optimizer.\*] {: #10053 }

Аналогично [предыдущему разделу](#10046), рассмотрим некоторые примеры использования событий 10053 и `trace[SQL_Optimizer.*]`:

```sql title="Преобразование 10053 level 1 в trace[SQL_Optimizer.*]"
SQL> alter session set events '10053 level 1';

Session altered.

SQL> oradebug setmypid
Statement processed.
SQL> oradebug eventdump session
trace [RDBMS.SQL_Quarantine]
trace [RDBMS.Vector_Processing]
trace [RDBMS.AQP]
trace [RDBMS.SQL_Optimizer_Stats_Advisor]
trace [RDBMS.SQL_Optimizer_Stats]
trace [RDBMS.SQL_Plan_Directive]
trace [RDBMS.SQL_Plan_Management]
trace [RDBMS.SQL_Parallel_Optimization]
trace [RDBMS.SQL_Costing]
trace [RDBMS.SQL_APA]
trace [RDBMS.SQL_Virtual]
trace [RDBMS.SQL_VMerge]
trace [RDBMS.SQL_MVRW]
trace [RDBMS.SQL_Transform]
trace [RDBMS.SQL_OPTIMIZER]
```

```sql title="trace[SQL_Optimizer.*] off отключает 10053"
SQL> alter session set events '10053 level 1';

Session altered.

SQL> oradebug eventdump session
trace [RDBMS.SQL_Quarantine]
trace [RDBMS.Vector_Processing]
trace [RDBMS.AQP]
trace [RDBMS.SQL_Optimizer_Stats_Advisor]
trace [RDBMS.SQL_Optimizer_Stats]
trace [RDBMS.SQL_Plan_Directive]
trace [RDBMS.SQL_Plan_Management]
trace [RDBMS.SQL_Parallel_Optimization]
trace [RDBMS.SQL_Costing]
trace [RDBMS.SQL_APA]
trace [RDBMS.SQL_Virtual]
trace [RDBMS.SQL_VMerge]
trace [RDBMS.SQL_MVRW]
trace [RDBMS.SQL_Transform]
trace [RDBMS.SQL_OPTIMIZER]
SQL> alter session set events 'trace[SQL_Optimizer.*] off';

Session altered.

SQL> oradebug eventdump session
Statement processed.
```

```sql title="10053 off отключает trace[SQL_Optimizer.*]"
SQL> alter session set events 'trace[SQL_Optimizer.*]';

Session altered.

SQL> oradebug eventdump session
trace [RDBMS.SQL_OPTIMIZER]
trace [RDBMS.SQL_Transform]
trace [RDBMS.SQL_MVRW]
trace [RDBMS.SQL_VMerge]
trace [RDBMS.SQL_Virtual]
trace [RDBMS.SQL_APA]
trace [RDBMS.SQL_Costing]
trace [RDBMS.SQL_Parallel_Optimization]
trace [RDBMS.SQL_Plan_Management]
trace [RDBMS.SQL_Plan_Directive]
trace [RDBMS.SQL_Optimizer_Stats]
trace [RDBMS.SQL_Optimizer_Stats_Advisor]
trace [RDBMS.AQP]
trace [RDBMS.Vector_Processing]
trace [RDBMS.SQL_Quarantine]
SQL>
SQL> alter session set events '10053 off';

Session altered.

SQL> oradebug eventdump session
Statement processed.
```

```sql title="Попытка использования scope для 10053 завершается ошибкой, но работает для случайного события 12345"
SQL> alter session set events '10053 [sql: 1111111111111 | 2222222222222]';
ERROR:
ORA-49100: Failed to process event statement [10053 [sql: 1111111111111 |
2222222222222]]
ORA-49160: Scope or Filter cannot be specified for mapped event, use
[trace[rdbms.SQL_Optimizer.*]

SQL> alter session set events '12345 [sql: 1111111111111 | 2222222222222]';

Session altered.
```


!!! note "Примечание"

    Дополнительные компоненты (такие как `SQL_Transform`) возникают, т.к. они включены в компонент `SQL_Optimizer` библиотеки RDBMS:

    ```
    SQL> oradebug doc component
    ...
    Components in library RDBMS:
    --------------------------
      SQL_Compiler                 SQL Compiler ((null))
        SQL_Parser                 SQL Parser (qcs)
        SQL_Semantic               SQL Semantic Analysis (kkm)
        SQL_Optimizer              SQL Optimizer ((null))
          SQL_Transform            SQL Transformation (kkq, vop, nso)
            SQL_MVRW               SQL Materialized View Rewrite ((null))
            SQL_VMerge             SQL View Merging (kkqvm)
            SQL_Virtual            SQL Virtual Column (qksvc, kkfi)
          SQL_APA                  SQL Access Path Analysis (apa)
          SQL_Costing              SQL Cost-based Analysis (kko, kke)
            SQL_Parallel_Optimization SQL Parallel Optimization (kkopq)
            Vector_Processing      Vector Processing (kkevp)
          SQL_Plan_Management      SQL Plan Managment (kkopm)
          SQL_Plan_Directive       SQL Plan Directive (qosd)
          SQL_Optimizer_Stats      SQL Optimizer Statistics (qos)
            SQL_Optimizer_Stats_Advisor SQL Optimizer Statistics Advisor (qosadv)
          AQP                      AQP (kkodp, qesdp, qersc)
          SQL_Quarantine           SQL Quarantine (qsfc)
    ```

!!! abstract "Вывод"

    Резюмируем, что как и в случае с событием [10046](#10046), событие [10053](#10053) преобразуется к UTS синтаксису, использующему `trace[SQL_Optimizer.*]`.
    Oracle называет такие события "mapped event", судя по ошибке `ORA-49160`:

    ```
    oerr ora 49160
    49160, 0000, "Scope or Filter cannot be specified for mapped event, use [%s]"
    ```

## Структура ksdUTSEvt

Структурой, с помощью которой Oracle осуществляет преобразование некоторых числовых событий в UTS синтаксис, является `ksdUTSEvt`.
Для просмотра структуры можно использовать [bide](/tools.md#bide):

```
bide dump-table ksdUTSEvt --format event:L trace_on:string on_len:L trace_off:string off_len:L callback:symbol L
+-------+-----------------------------------+--------+----------------------------------+---------+----------------------+----------+
| event | trace_on                          | on_len | trace_off                        | off_len | callback             | unnamed6 |
+-------+-----------------------------------+--------+----------------------------------+---------+----------------------+----------+
| 10298 | 0                                 |      8 | trace[OFS.*] off                 |      17 | ksfs_morphtrc_cbk    |        0 |
| 10299 | trace[MBR] disk=high              |     21 | trace[MBR] off                   |      15 | 0                    |        0 |
| 10730 | trace[rdbms.VPD.*] disk = highest |     34 | trace[rdbms.VPD.*] off           |      23 | 0                    |        0 |
| 10046 | 0                                 |      8 | sql_trace off                    |      14 | kxstMorphSqlTraceCbk |        0 |
| 10053 | trace[rdbms.SQL_Optimizer.*]      |     29 | trace[rdbms.SQL_Optimizer.*] off |      33 | 0                    |        0 |
|     0 | 0                                 |      0 | 0                                |       0 | 0                    |        0 |
+-------+-----------------------------------+--------+----------------------------------+---------+----------------------+----------+
```

Пояснения к полям таблицы:

- `trace_on`: UTS синтаксис включения события.
- `trace_off`: UTS синтаксис выключения события.
- `callback`: вызывается для включения событий, зависящих от переданного уровня.

## Короче говоря

- Некоторые числовые события (например, 10046 и 10053) преобразуются к эквивалентному UTS синтаксису при использовании.
- Правила преобразования определены в структуре `ksdUTSEvt`.
- Для просмотра структуры можно использовать [bide](/tools.md#bide).

*[UTS]: Unified Tracing Service
