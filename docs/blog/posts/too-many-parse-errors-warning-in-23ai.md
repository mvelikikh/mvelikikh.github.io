---
categories:
  - Oracle
date:
  created: 2025-02-17
description: >-
  Too many parse errors warning пишутся в debug log в 23ai.
  Соответствующий сообщениям PL/SQL call stack пишется в alert log.
  Параметр _kks_parse_failure_time_period ограничивает частоту появлений данных сообщений по времени.
tags:
  - 12c
  - 23ai
  - Initialization parameter
  - OERR
---

# Too many parse errors warning в 23ai

Джонатан Льюис в своём блоге недавно написал, что скрипт, вызывающий too many parse errors warning в 12.2, более ничего не пишет в alert log в версии 23ai Free.
Рассмотрим более подробно, что конкретно поменялось в 23ai по этим сообщениям.

<!-- more -->

## Окружение и тестовая схема

Для тестов я буду использовать Oracle Database 23ai Free (23.6).
Все тесты будут проводиться под отдельным пользователем `TC`, который создан следующим скриптом:

```sql title="Создание тестового пользователя"
conn / as sysdba
alter session set container=freepdb1;
drop user tc cascade;
grant alter session, create session to tc identified by tc;
```

## Alert log и PL/SQL call stack {: #alert-log }

Для начала проверим утверждение Джонатана Льюиса о том, что его тестовый скрипт ничего не пишет в alert log:

> ***Update Jan 2025***: Something has changed by 23.4 (Free); and the demo code below no longer dumped anything in the alert log when I tested it on a local instance in a virtual machine.[^1]

[^1]: [12c Parse Errors] в блоге Джонатана Льюиса

Я позаимствую скрипт, который используется в [публикации Джонатана][12c Parse Errors]:

[12c Parse Errors]: https://jonathanlewis.wordpress.com/2017/10/06/12c-parse/

```sql title="Тестовый скрипт"
rem
rem     Script:         parse_fail_2.sql
rem     Author:         Jonathan Lewis
rem     Dated:          Oct 2017
rem

declare
        m1 number;
begin
        for i in 1..10000 loop
        begin
                execute immediate 'select count(*) frm dual' into m1;
                dbms_output.put_line(m1);
        exception
                when others then null;
        end;
        end loop;
end;
/
```

После запуска данного скрипта под пользователем `TC` в alert log сбрасывается PL/SQL call stack:

``` title="PL/SQL call stack в alert.log"
2025-02-17T17:43:59.586037+00:00
FREEPDB1(3):----- PL/SQL Call Stack -----
  object      line  object
  handle    number  name
0x69eaa2b8         6  anonymous block
```

Если запустить скрипт второй раз, то сброс PL/SQL call stack более не происходит.
Полагаю, что Джонатан запускал скрипт многократно и просто пропустил PL/SQL call stack при первом запуске.
Это единственное объяснение, которое я могу дать сделанному Джонатану заключению.
Однако, стоит учитывать, что я провожу тесты в 23.6, в то время как Джонатан указывает 23.4.

## Debug log

Что по поводу самих `WARNING: too many parse errors`, которые присутствуют в предыдущих версиях (например, в 12.2), и можно ли сказать, что теперь Oracle их не пишет вовсе?

Если отрассировать серверный процесс, выполняющий [тестовый скрипт](#alert-log), через `strace`, то можно увидеть следующее:

```
# strace -s 4096 -yy -e trace=write -p 14098
strace: Process 14098 attached
write(8</opt/oracle/diag/rdbms/free/FREE/log/debug/log.xml>, "<msg time='2025-02-17T17:43:59.577+00:00' org_id='oracle' comp_id='rdbms'\n msg_id='kksParseErrorWarning:11642:1481387665' type='UNKNOWN' group='cursor'\n level='16' host_id='myhostname.mycompany.mydomain' host_addr='10.100.101.85'\n pid='14098' con_uid='2152820782' con_id='3'\n con_name='FREEPDB1' seclabel='9'>\n <txt>WARNING: too many parse errors, count=101 SQL hash=0x19a22496\n </txt>\n</msg>\n", 393) = 393
write(8</opt/oracle/diag/rdbms/free/FREE/log/debug_FREE.log>, "2025-02-17T17:43:59.579780+00:00\nkks.c@11642:WARNING: too many parse errors, count=101 SQL hash=0x19a22496\n", 107) = 107
write(8</opt/oracle/diag/rdbms/free/FREE/log/debug/log.xml>, "<msg time='2025-02-17T17:43:59.580+00:00' org_id='oracle' comp_id='rdbms'\n msg_id='kksParseErrorWarning:11654:1504146100' type='UNKNOWN' group='cursor'\n level='16' host_id='myhostname.mycompany.mydomain' host_addr='10.100.101.85'\n pid='14098' con_uid='2152820782' con_id='3'\n con_name='FREEPDB1' seclabel='5'>\n <txt>SQL: select count(*) frm dual\n </txt>\n</msg>\n", 361) = 361
write(8</opt/oracle/diag/rdbms/free/FREE/log/debug_FREE.log>, "2025-02-17T17:43:59.580878+00:00\nkks.c@11654:SQL: select count(*) frm dual\n", 75) = 75
write(8</opt/oracle/diag/rdbms/free/FREE/log/debug/log.xml>, "<msg time='2025-02-17T17:43:59.581+00:00' org_id='oracle' comp_id='rdbms'\n msg_id='kksDumpParseErrorDiag:2117:2035696906' type='UNKNOWN' group='cursor'\n level='16' host_id='myhostname.mycompany.mydomain' host_addr='10.100.101.85'\n pid='14098' con_uid='2152820782' con_id='3'\n con_name='FREEPDB1' seclabel='9'>\n <txt>PARSE ERROR: ospid=14098, error=923: \n </txt>\n</msg>\n", 369) = 369
write(8</opt/oracle/diag/rdbms/free/FREE/log/debug_FREE.log>, "2025-02-17T17:43:59.581999+00:00\nkks.c@2117:PARSE ERROR: ospid=14098, error=923: \n", 82) = 82
write(8</opt/oracle/diag/rdbms/free/FREE/log/debug/log.xml>, "<msg time='2025-02-17T17:43:59.582+00:00' org_id='oracle' comp_id='rdbms'\n msg_id='kksDumpParseErrorDiag:2164:2094338190' type='UNKNOWN' group='cursor'\n level='16' host_id='myhostname.mycompany.mydomain' host_addr='10.100.101.85'\n pid='14098' con_uid='2152820782' con_id='3'\n con_name='FREEPDB1' seclabel='9'>\n <txt>Additional information: hd=0x69f8d610 phd=0x6bb1bec0 flg=0x28 cisid=138 sid=138 ciuid=138 uid=138 sqlid=bfqc8ascu494q\n </txt>\n</msg>\n", 449) = 449
write(8</opt/oracle/diag/rdbms/free/FREE/log/debug_FREE.log>, "2025-02-17T17:43:59.582981+00:00\nkks.c@2164:Additional information: hd=0x69f8d610 phd=0x6bb1bec0 flg=0x28 cisid=138 sid=138 ciuid=138 uid=138 sqlid=bfqc8ascu494q\n", 162) = 162
write(8</opt/oracle/diag/rdbms/free/FREE/log/debug/log.xml>, "<msg time='2025-02-17T17:43:59.583+00:00' org_id='oracle' comp_id='rdbms'\n msg_id='kksDumpParseErrorDiag:2170:1187211181' type='UNKNOWN' group='cursor'\n level='16' host_id='myhostname.mycompany.mydomain' host_addr='10.100.101.85'\n pid='14098' con_uid='2152820782' con_id='3'\n con_name='FREEPDB1' seclabel='9'>\n <txt>...Current username=TC\n </txt>\n</msg>\n", 354) = 354
write(8</opt/oracle/diag/rdbms/free/FREE/log/debug_FREE.log>, "2025-02-17T17:43:59.584025+00:00\nkks.c@2170:...Current username=TC\n", 67) = 67
write(8</opt/oracle/diag/rdbms/free/FREE/log/debug/log.xml>, "<msg time='2025-02-17T17:43:59.584+00:00' org_id='oracle' comp_id='rdbms'\n msg_id='kksDumpParseErrorDiag:2184:2480833557' type='UNKNOWN' group='cursor'\n level='16' host_id='myhostname.mycompany.mydomain' host_addr='10.100.101.85'\n pid='14098' con_uid='2152820782' con_id='3'\n con_name='FREEPDB1' seclabel='5'>\n <txt>...Application: SQL*Plus Action: \n </txt>\n</msg>\n", 365) = 365
write(8</opt/oracle/diag/rdbms/free/FREE/log/debug_FREE.log>, "2025-02-17T17:43:59.585179+00:00\nkks.c@2184:...Application: SQL*Plus Action: \n", 78) = 78
write(8</opt/oracle/diag/rdbms/free/FREE/alert/log.xml>, "<msg time='2025-02-17T17:43:59.585+00:00' org_id='oracle' comp_id='rdbms'\n type='UNKNOWN' level='16' host_id='myhostname.mycompany.mydomain'\n host_addr='10.100.101.85' module='SQL*Plus' pid='14098'\n con_uid='2152820782' con_id='3' con_name='FREEPDB1'\n seclabel='3'>\n <txt>----- PL/SQL Call Stack -----\n  object      line  object\n  handle    number  name\n0x69eaa2b8         6  anonymous block\n </txt>\n</msg>\n", 407) = 407
write(8</opt/oracle/diag/rdbms/free/FREE/trace/alert_FREE.log>, "2025-02-17T17:43:59.586037+00:00\nFREEPDB1(3):----- PL/SQL Call Stack -----\n  object      line  object\n  handle    number  name\n0x69eaa2b8
      6  anonymous block\n", 165) = 165
```

Таким образом, искомые сообщения пишутся в [debug log](https://docs.oracle.com/en/database/oracle/oracle-database/23/admin/diagnosing-and-resolving-problems.html#ADMIN-GUID-9C1E54BB-A699-418F-A486-01FA35DB03EB):

``` title="Too many parse errors warning в debug log"
2025-02-17T17:43:59.579780+00:00
kks.c@11642:WARNING: too many parse errors, count=101 SQL hash=0x19a22496
2025-02-17T17:43:59.580878+00:00
kks.c@11654:SQL: select count(*) frm dual
2025-02-17T17:43:59.581999+00:00
kks.c@2117:PARSE ERROR: ospid=14098, error=923:
2025-02-17T17:43:59.582981+00:00
kks.c@2164:Additional information: hd=0x69f8d610 phd=0x6bb1bec0 flg=0x28 cisid=138 sid=138 ciuid=138 uid=138 sqlid=bfqc8ascu494q
2025-02-17T17:43:59.584025+00:00
kks.c@2170:...Current username=TC
2025-02-17T17:43:59.585179+00:00
kks.c@2184:...Application: SQL*Plus Action:
```

Возникает вопрос: почему `WARNING: too many parse errors` с остальными деталями пишется в debug log, и только PL/SQL call stack пишется в alert log?
Для меня это выглядит странным.
Предположу, что PL/SQL call stack пишется в alert log по ошибке.
PL/SQL call stack также должен был писаться в debug log, т.к. содержит важную информацию по диагностике too many parse errors.

## \_kks\_parse\_failure\_time\_period

Стоит отметить, что при выполнении [тестового скрипта](#alert-log) пишется всего одно сообщение `WARNING: too many parse errors, count=101`, в то время как в версии 12.2 писалось предупреждение для каждых 100 ошибок вида:

```
2025-02-15T15:07:42.469631+00:00
PDB(3):WARNING: too many parse errors, count=100 SQL hash=0x19a22496
...
PDB(3):WARNING: too many parse errors, count=200 SQL hash=0x19a22496
...
2025-02-15T15:07:47.948844+00:00
PDB(3):WARNING: too many parse errors, count=300 SQL hash=0x19a22496
```

Здесь Oracle использует ограничение, задаваемое параметром `_kks_parse_failure_time_period`:

```sql title="Описание и значение по умолчанию"
SQL> select p.ksppdesc, v.ksppstvl
  2    from x$ksppi p,
  3         x$ksppsv v
  4   where p.ksppinm = '_kks_parse_failure_time_period'
  5     and v.indx = p.indx;

KSPPDESC                                 KSPPSTVL
---------------------------------------- ----------
Parse failure time period (seconds)      3600
```

Данный параметр отсутствует в версиях 19c (19.26) и 21c (21.17), присутствует в версии 23ai Free (23.6).
Параметр определяет как часто Oracle сбрасывает информацию по too many parse errors.
Значение по умолчанию для данного параметра - 3600 секунд или 1 час.

Для тестов удобно данный параметр установить в более низкое значение, чтобы вызвать появление сообщений об ошибках при каждом запуске скрипта:

```sql title="Установка _kks_parse_failure_time_period и запуск parse_fail_2.sql"
alter session set "_kks_parse_failure_time_period"=1;
@parse_fail_2.sql
```

Запустив скрипт последовательно два раза, выждав небольшую паузу между запусками, наблюдаем:

``` title="Alert log"
2025-02-17T17:46:12.295496+00:00
FREEPDB1(3):----- PL/SQL Call Stack -----
  object      line  object
  handle    number  name
0x69eaa2b8         6  anonymous block
2025-02-17T17:46:21.375571+00:00
FREEPDB1(3):----- PL/SQL Call Stack -----
  object      line  object
  handle    number  name
0x69eaa2b8         6  anonymous block
```

``` title="Debug log"
2025-02-17T17:46:12.295143+00:00
kks.c@11642:WARNING: too many parse errors, count=10001 SQL hash=0x19a22496
2025-02-17T17:46:12.295223+00:00
kks.c@2117:PARSE ERROR: ospid=14098, error=923:
2025-02-17T17:46:12.295295+00:00
kks.c@2164:Additional information: hd=0x69f8d610 phd=0x6bb1bec0 flg=0x28 cisid=138 sid=138 ciuid=138 uid=138 sqlid=bfqc8ascu494q
2025-02-17T17:46:12.295370+00:00
kks.c@2170:...Current username=TC
2025-02-17T17:46:12.295438+00:00
kks.c@2184:...Application: SQL*Plus Action:
2025-02-17T17:46:21.375214+00:00
kks.c@11642:WARNING: too many parse errors, count=20001 SQL hash=0x19a22496
2025-02-17T17:46:21.375296+00:00
kks.c@2117:PARSE ERROR: ospid=14098, error=923:
2025-02-17T17:46:21.375370+00:00
kks.c@2164:Additional information: hd=0x69f8d610 phd=0x6bb1bec0 flg=0x28 cisid=138 sid=138 ciuid=138 uid=138 sqlid=bfqc8ascu494q
2025-02-17T17:46:21.375439+00:00
kks.c@2170:...Current username=TC
2025-02-17T17:46:21.375507+00:00
kks.c@2184:...Application: SQL*Plus Action:
```

## Короче говоря

В версии 23ai Free (23.6):

- too many parse errors warning с большинством деталей (SQL текст и прочее) пишется в debug log
- в alert log пишется только PL/SQL call stack
- `_kks_parse_failure_time_period` ограничивает частоту появления данных сообщений по времени. Значение по умолчанию данного параметра один час.
