---
categories:
  - Oracle
date:
  created: 2025-07-30
description: >-
  Показано как получить текстовые синонимы числовых диагностических событий (например, DEADLOCK для ORA-60, и т.д.).
  Для всех синонимов также включен вывод oerr
tags:
  - 19c
  - Code symbol
  - Diagnostic event
  - OERR
---

# Текстовые синонимы числовых диагностических событий

Известно, что для некоторых числовых диагностических событий, Oracle позволяет использовать текстовые синонимы, например, `DEADLOCK` для `ORA-60`.
Данная заметка показывает, как получить такие синонимы в версии Oracle Database 19c.

<!-- more -->

## Введение

Заметим, что использование текстовых синонимов может быть достаточно удобным, т.к. обычно запоминаются только "популярные" числовые коды.
Также код с текстовыми синонимами может оказаться более понятным, чем код с числовыми событиями.

Приведём несколько примеров использования известных синонимов и соответствующих им эквивалентных числовых кодов.

```sql title="DEADLOCK и ORA-60"
SQL> alter session set events 'deadlock errorstack(1)';

Session altered.

SQL> alter session set events '60 errorstack(1)';

Session altered.
```

```sql title="LOGON и ORA-10029"
SQL> alter system set events 'logon oradebug';

System altered.

SQL> alter system set events '10029 oradebug';

System altered.
```

## Структура ksdtevt

Доступные синонимы можно посмотреть в структуре `ksdtevt`, например, с помощью [bide](/tools.md#bide):

```
bide dump-table ksdtevt --format name:string code:L
+---------------------+-------+
| name                |  code |
+---------------------+-------+
| LOGON               | 10029 |
| LOGOFF              | 10030 |
| DEADLOCK            |    60 |
| NOTIFYCRS           | 39505 |
| CONTROL_FILE        | 10000 |
| DB_FILES            | 10222 |
| BEGIN               | 10010 |
| END                 | 10011 |
| PQ_KILL_TEST        | 10370 |
| PQ_KILL_TEST_PROC   | 10372 |
| PQ_KILL_TEST_CODE   | 10373 |
| KXFX                | 10390 |
| SORT_END            | 10032 |
| SORT_RUN            | 10033 |
| PARSE_SQL_STATEMENT | 10035 |
| CREATE_REMOTE_RWS   | 10036 |
| ALLOC_REMOTE_RWS    | 10037 |
| QUERY_BLOCK_ALLOC   | 10038 |
| TYPE_CHECK          | 10039 |
| KFTRACE             | 15199 |
| KFDEBUG             | 15194 |
| KFSYNTAX            | 15195 |
| KEWA_ASH_TRACE      | 13740 |
| kea_debug_event     | 13698 |
| KEH_TRACE           | 13700 |
| 0                   |     0 |
+---------------------+-------+
```

## Расширение с помощью oerr

Т.к. события числовые, может быть полезно дополнить вывод с данными из oerr, например, для `DEADLOCK`/`ORA-60` выполнить:

```
oerr ora 60
00060, 00000, "deadlock detected while waiting for resource"
// *Cause:  Transactions deadlocked one another while waiting for resources.
// *Action: Look at the trace file to see the transactions and resources
//          involved. Retry if necessary.
```

И взять расшифровку числового события: "deadlock detected while waiting for resource".

Получается следующая таблица:

| name                  | code  | oerr                                                   |
| --------------------- | ----: | ------------------------------------------------------ |
| LOGON                 | 10029 | session logon (KSU)                                    |
| LOGOFF                | 10030 | session logoff (KSU)                                   |
| DEADLOCK              | 60    | deadlock detected while waiting for resource           |
| NOTIFYCRS             | 39505 | Transparent HA tracing event                           |
| CONTROL\_FILE         | 10000 | control file debug event, name 'control\_file'         |
| DB\_FILES             | 10222 | row cache                                              |
| BEGIN                 | 10010 | Begin Transaction                                      |
| END                   | 10011 | End   Transaction                                      |
| PQ\_KILL\_TEST        | 10370 | parallel query server kill event                       |
| PQ\_KILL\_TEST\_PROC  | 10372 | parallel query server kill event proc                  |
| PQ\_KILL\_TEST\_CODE  | 10373 | parallel query server kill event                       |
| KXFX                  | 10390 | Trace parallel query slave execution                   |
| SORT\_END             | 10032 | sort statistics (SOR\*)                                |
| SORT\_RUN             | 10033 | sort run information (SRD\*/SRS\*)                     |
| PARSE\_SQL\_STATEMENT | 10035 | Write parse failures to alert log file                 |
| CREATE\_REMOTE\_RWS   | 10036 | create remote row source (QKANET)                      |
| ALLOC\_REMOTE\_RWS    | 10037 | allocate remote row source (QKARWS)                    |
| QUERY\_BLOCK\_ALLOC   | 10038 | dump row source tree (QBADRV)                          |
| TYPE\_CHECK           | 10039 | type checking (OPITCA)                                 |
| KFTRACE               | 15199 | Internal ASM tracing event number 15199                |
| KFDEBUG               | 15194 | Internal ASM-DB interaction testing event number 15194 |
| KFSYNTAX              | 15195 | Internal ASM testing event number 15195                |
| KEWA\_ASH\_TRACE      | 13740 |                                                        |
| kea\_debug\_event     | 13698 |                                                        |
| KEH\_TRACE            | 13700 | Reserved for ADDM tracing.                             |

Нетрудно видеть, что:

- Некоторым синонимам нет соответствующего кода в oerr, например, `KEWA_ASH_TRACE` соответствует коду 13740, по которому в oerr нет информации.
- Некоторые синонимы или их описания из oerr не согласованы, например, `DB_FILES` соответствует коду 10222, которому соответствует описание "row cache" в oerr.

## Короче говоря

- Структура `ksdtevt` содержит текстовые синонимы числовых событий.
- Для просмотра структуры можно использовать [bide](/tools.md#bide).
- Можно дополнить вывод информацией из oerr, чтобы иметь описание числового кода события, но наблюдается некоторая несогласованность по части кодов и их синонимов.
