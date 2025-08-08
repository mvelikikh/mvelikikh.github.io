---
categories:
  - Oracle
date:
  created: 2025-08-08
description: >-
  Показано как добавлять свои текстовые синонимы для числовых диагностических событий путём создания изменённой структуры ksdtevt и последующей перелинковки бинарника Oracle.
  Продемонстирована работа тестового SQL*Plus скрипта, использующего добавленные синонимы.
tags:
  - 19c
  - Code symbol
  - Diagnostic event
  - OERR
---

# Расширение текстовых синонимов числовых диагностических событий

В продолжение [Текстовые синонимы числовых диагностических событий](text-aliases-of-numeric-events.md), рассмотрим, как добавить новые синонимы для числовых диагностических событий в версии Oracle Database 19c.

<!-- more -->

## Исходные и целевые данные

Исходная структура `ksdtevt` может быть просмотрена с помощью [bide](/tools.md#bide):

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

Целью данной заметки будет добавление двух новых синонимов для кодов ошибок `ORA-942` и `ORA-1400`:

| name                 | code |
| -------------------- | ----:|
| `NO_SUCH_TABLE`      |  942 |
| `CANNOT_INSERT_NULL` | 1400 |

Попытки использования данных синонимов завершаются с ошибками `ORA-49100`/`ORA-49108`:

```sql
SQL> alter session set events 'no_such_table errorstack(1)';
ERROR:
ORA-49100: Failed to process event statement [no_such_table errorstack(1)]
ORA-49108: Event Name [NO_SUCH_TABLE] not found

SQL> alter session set events 'cannot_insert_null incident("NULL_INSERTION")';
ERROR:
ORA-49100: Failed to process event statement [cannot_insert_null
incident("NULL_INSERTION")]
ORA-49108: Event Name [CANNOT_INSERT_NULL] not found
```

## Реализация

1. Создать файл `ksdtevt.c` со следующим содержимым:
   ```c title="ksdtevt.c"
   --8<-- "extending-text-aliases-of-numeric-events/ksdtevt.c"
   ```
   Как видно, в файл включены текущие данные, а также два новых синонима.

1. Создать резервную копию `libserver`:
   ```shell
   cd $ORACLE_HOME/lib
   # создание резервной копии libserver
   cp libserver19.a{,.backup}
   ```

1. Замена символа `ksdtevt`:
   ```shell
   # извлечение ksdt.o
   ar xv libserver19.a ksdt.o
   # замена символа ksdtevt
   sed -i 's/\(ksdtevt\)/\u\1/g' ksdt.o
   # замена ksdt.o в libserver изменённым
   ar rv libserver19.a ksdt.o
   ```

1. Компиляция нового `ksdtevt`:
   ```shell
   # компиляция ksdtevt.c
   gcc -c ksdtevt.c
   ```

1. Добавление нового `ksdtevt` в `libserver`:
   ```shell
   # добавление ksdtevt.o в libserver
   ar rv libserver19.a ksdtevt.o
   ```

1. Линковка `oracle`:
   ```shell
   # линковка oracle
   cd $ORACLE_HOME/rdbms/lib
   make -f ins_rdbms.mk ioracle
   ```

```shell title="Полный скрипт для удобства"
cd $ORACLE_HOME/lib
# создание резервной копии libserver
cp libserver19.a{,.backup}
# извлечение ksdt.o
ar xv libserver19.a ksdt.o
# замена символа ksdtevt
sed -i 's/\(ksdtevt\)/\u\1/g' ksdt.o
# замена ksdt.o в libserver изменённым
ar rv libserver19.a ksdt.o
# компиляция ksdtevt.c
gcc -c ksdtevt.c
# добавление ksdtevt.o в libserver
ar rv libserver19.a ksdtevt.o
# линковка oracle
cd $ORACLE_HOME/rdbms/lib
make -f ins_rdbms.mk ioracle
```

## Демонстрация

Будет использоваться следующий SQL\*Plus скрипт:

```sql title="ksdtevt.sql"
--8<-- "extending-text-aliases-of-numeric-events/ksdtevt.sql"
```

Его вывод:

```sql title="Вывод работы скрипта с изменённым ksdtevt"
--8<-- "extending-text-aliases-of-numeric-events/output.txt"
```

Таким образом, продемонстрирована работа обоих новых синонимов.

## Короче говоря

- Возможно добавление своих текстовых синонимов для числовых диагностических событий.
- Приведён вариант реализации, использующий подмену символа `ksdtevt` и добавление изменённой структуры `ksdtevt`.
- Продемонстирована работа тестового SQL\*Plus скрипта, использующего добавленные синонимы.
