---
categories:
  - Oracle
date:
  created: 2017-01-30T09:15:00
description: >-
  DBMS_METADATA.GET_SXML_DDL may return wrong DDL for a trigger on an editioning view, as opposed to DBMS_METADATA.GET_DDL that returns the correct one.
tags:
  - 11g
  - 12c
  - Bug
  - EBR
---

# `DBMS_METADATA.GET_SXML_DDL` may produce incorrect DDL for trigger in EBR environment

I have recently discovered a case when `DBMS_METADATA.GET_SXML_DDL` returns incorrect DDL for a trigger in an EBR environment.

<!-- more -->

Here is a test case to reproduce the issue that is present in 12.1.0.2.170117 and 11.2.0.4.161018:

```sql
SQL> grant connect, create table, create view, create trigger to tc identified by tc;

Grant succeeded.

SQL>
SQL> alter user tc enable editions for view,trigger;

User altered.

SQL>
SQL> conn tc/tc
Connected.
SQL>
SQL> create table t (
  2    x int)
  3  /

Table created.

SQL>
SQL> create or replace editioning view ev
  2  as
  3  select *
  4    from t
  5  /

View created.

SQL>
SQL> create or replace trigger trg
  2  before update of x on ev
  3  declare
  4  begin
  5    null;
  6  end;
  7  /

Trigger created.
```

Let us look at the DDL of the trigger returned by the `DBMS_METADATA.GET_DDL` and `DBMS_METADATA.GET_SXML_DDL` functions.

```sql
SQL> select dbms_metadata.get_ddl( 'TRIGGER', 'TRG') from dual;

DBMS_METADATA.GET_DDL('TRIGGER','TRG')
--------------------------------------------------------------------------------

  CREATE OR REPLACE EDITIONABLE TRIGGER "TC"."TRG"
before update of x on ev
declare
begin
  null;
end;
ALTER TRIGGER "TC"."TRG" ENABLE


SQL> select dbms_metadata.get_sxml_ddl( 'TRIGGER', 'TRG') from dual;

DBMS_METADATA.GET_SXML_DDL('TRIGGER','TRG')
--------------------------------------------------------------------------------
  CREATE OR REPLACE TRIGGER "TC"."TRG"
  BEFORE UPDATE OF X ON "TC"."EV"
  declare
begin
  null;
end;
```

They are about the same with the exception of the `EDITIONABLE` property.
Now I change the status of my trigger.
Please note the highlighted lines showing the differences:

```sql hl_lines="12 25"
SQL> alter trigger trg enable;

Trigger altered.

SQL>
SQL> select dbms_metadata.get_ddl( 'TRIGGER', 'TRG') from dual;

DBMS_METADATA.GET_DDL('TRIGGER','TRG')
--------------------------------------------------------------------------------

  CREATE OR REPLACE EDITIONABLE TRIGGER "TC"."TRG"
before update of x on ev
declare
begin
  null;
end;
ALTER TRIGGER "TC"."TRG" ENABLE


SQL> select dbms_metadata.get_sxml_ddl( 'TRIGGER', 'TRG') from dual;

DBMS_METADATA.GET_SXML_DDL('TRIGGER','TRG')
--------------------------------------------------------------------------------
  CREATE OR REPLACE TRIGGER "TC"."TRG"
  BEFORE UPDATE OF X, X ON "TC"."EV"
  declare
begin
  null;
end;
```

I have ended up with two `X` columns in the output of `DBMS_METADATA.GET_SXML_DDL`, which is, in fact, a non-working DDL statement.
I played more with this issue, and I have eventually obtained four X columns, which is not the limit:

??? Show

    ```sql hl_lines="12 25 45 58"
    SQL> alter trigger trg disable;

    Trigger altered.

    SQL>
    SQL> select dbms_metadata.get_ddl( 'TRIGGER', 'TRG') from dual;

    DBMS_METADATA.GET_DDL('TRIGGER','TRG')
    --------------------------------------------------------------------------------

      CREATE OR REPLACE EDITIONABLE TRIGGER "TC"."TRG"
    before update of x on ev
    declare
    begin
      null;
    end;
    ALTER TRIGGER "TC"."TRG" DISABLE


    SQL> select dbms_metadata.get_sxml_ddl( 'TRIGGER', 'TRG') from dual;

    DBMS_METADATA.GET_SXML_DDL('TRIGGER','TRG')
    --------------------------------------------------------------------------------
      CREATE OR REPLACE TRIGGER "TC"."TRG"
      BEFORE UPDATE OF X, X, X ON "TC"."EV"
      declare
    begin
      null;
    end;
      ALTER TRIGGER "TC"."TRG" DISABLE


    SQL>
    SQL> alter trigger trg enable;

    Trigger altered.

    SQL>
    SQL> select dbms_metadata.get_ddl( 'TRIGGER', 'TRG') from dual;

    DBMS_METADATA.GET_DDL('TRIGGER','TRG')
    --------------------------------------------------------------------------------

      CREATE OR REPLACE EDITIONABLE TRIGGER "TC"."TRG"
    before update of x on ev
    declare
    begin
      null;
    end;
    ALTER TRIGGER "TC"."TRG" ENABLE


    SQL> select dbms_metadata.get_sxml_ddl( 'TRIGGER', 'TRG') from dual;

    DBMS_METADATA.GET_SXML_DDL('TRIGGER','TRG')
    --------------------------------------------------------------------------------
      CREATE OR REPLACE TRIGGER "TC"."TRG"
      BEFORE UPDATE OF X, X, X, X ON "TC"."EV"
      declare
    begin
      null;
    end;
    ```

The `DBMS_METADATA.GET_SXML_DDL` procedure uses a `SELECT` statement similar to the above to obtain the DDL:

```sql
SELECT /*+all_rows*/
       SYS_XMLGEN(
         VALUE(KU$),
         XMLFORMAT.createFormat2('TRIGGER_T', '7')),
       KU$.OBJ_NUM
  FROM SYS.KU$_TRIGGER_VIEW KU$
 WHERE NOT (KU$.BASE_OBJ IS NOT NULL AND BITAND(KU$.BASE_OBJ.FLAGS,128)!=0)
   AND KU$.SCHEMA_OBJ.NAME = 'TRG'
   AND KU$.SCHEMA_OBJ.OWNER_NAME = 'TC';
```

The column list for the trigger comes from the following part of the `SYS.KU$_TRIGGER_VIEW` view:

```sql
          cast(multiset(select * from ku$_triggercol_view tv
                        where tv.obj_num=t.obj#
                      ) as ku$_triggercol_list_t
             ),
```

The code of the `KU$_TRIGGERCOL_VIEW` view is as follows:

```sql
CREATE OR REPLACE FORCE NONEDITIONABLE VIEW "SYS"."KU$_TRIGGERCOL_VIEW" OF "SYS"."KU$_TRIGGERCOL_T"
  WITH OBJECT IDENTIFIER (obj_num,intcol_num,type_num) AS
  select '1','0',
         tc.obj#, tc.col#, tc.type#, tc.position#, tc.intcol#, c.name,
         (select a.name from attrcol$ a where
                        a.obj#=tc.obj# and a.intcol#=tc.intcol#)
  from col$ c, triggercol$ tc, trigger$ t
  where tc.obj#=t.obj#
    and c.obj#=t.baseobject
    and c.intcol#=tc.intcol#
```

And the final part of the puzzle is the `TRIGGERCOL$` table:

```sql hl_lines="9"
SQL> select * from sys.triggercol$ where obj#=(select object_id from dba_objects where owner='TC' and object_name='TRG');

      OBJ#       COL#      TYPE#  POSITION#    INTCOL#
---------- ---------- ---------- ---------- ----------
    214352          1          0          0          1
    214352          1          0          0          1
    214352          1          0          0          1
    214352          1          0          0          1
    214352          1       1024          0          1
```

It gets one row each time I execute the `ALTER TRIGGER ENABLE/DISABLE` statement.
I think Oracle Developers should filter the rows because there is only one row with `TYPE#=1024`.
`DBMS_METADATA.GET_DDL` returns correct DDL and it seems to be coming from the DDL passed by a user.
Conversely, `DBMS_METADATA.GET_SXML_DDL` tries to reconstruct the user's DDL, and it messes things up.
