---
categories:
  - Oracle
date:
  created: 2015-07-22T16:37:00
  updated: 2016-05-14T12:30:38
description: >-
  Adjunct schemas are created for each editions-enabled schema in Edition-based redefinition.
  There is one adjunct schema per editions-enabled schema per edition
tags:
  - 12c
  - Diagnostic event
  - EBR
---

# Edition-based redefinition: adjunct schemas

In this blog post I would like to describe one of the basic component of Edition-based redefinition (EBR): adjunct schemas.

<!-- more -->

EBR is one of the killer feature of Oracle Database 11g R2, as [Tom Kyte said in 2010](http://www.oracle.com/au/products/database/o30asktom-082672.html).
But I don't think that this feature is widely used by Oracle community.
Why? Probably because applications must be "edition aware", as described by Tom Kyte in his excellent articles.

I have been using EBR since 2012.
All of this information are pure speculations based on various blog posts and Oracle whitepapers, and of course my experience with the EBR feature.
All of the tests are run in Oracle Database version 12.1.0.2 on Solaris SPARC.

Here is a code that I use for this demo:

```sql
def tns_alias=orcl

doc
  connect as DBA user
#
conn /@&tns_alias.

set echo on timi off ti off sqlp "SQL> "

drop edition e1 cascade;
drop edition e2 cascade;
drop user tc cascade;

doc
  Create editions-enabled schema
#
grant create procedure, create session to tc identified by tc;

alter user tc enable editions;

doc
  Enable SQL tracing
#

alter session set events 'sql_trace bind=true';

doc
  Create 2 editions
#

create edition e1;
create edition e2;

alter session set events 'sql_trace off';

select value from v$diag_info where name='Default Trace File';
```

The code creates an editions-enabled schema `TC` and two editions: `E1` and `E2`.

I would like to point your attention to the recursive SQL below executed during the `CREATE EDITION` command:

```sql
PARSING IN CURSOR #18446744071422692152 len=288 dep=1 uid=0 oct=2 lid=0 tim=9324454212634 hv=556673006 ad='430c59cc0' sqlid='fws71mhhkw9zf'
insert into user$(user#, name, password, ctime, ptime,                      datats#, tempts#, type#, defrole, resource$, ltime,                      astatus, lcount, spare1, spare2, ext_user
name)    values(:1, :2, NULL, sysdate, null, :3, :4, 2, :5, :6, null, :7, 0, 16,           :8, :9)
END OF STMT
PARSE #18446744071422692152:c=1199,e=1198,p=0,cr=0,cu=0,mis=1,r=0,dep=1,og=4,plh=0,tim=9324454212629
BINDS #18446744071422692152:
 Bind#0
  oacdty=02 mxl=22(22) mxlc=00 mal=00 scl=00 pre=00
  oacflg=00 fl2=1000001 frm=00 csi=00 siz=24 off=0
  kxsbbbfp=ffffffff77e77150  bln=22  avl=03  flg=05
  value=859
 Bind#1
  oacdty=01 mxl=32(30) mxlc=00 mal=00 scl=00 pre=00
  oacflg=10 fl2=0001 frm=01 csi=171 siz=32 off=0
  kxsbbbfp=ffffffff7fff8688  bln=32  avl=30  flg=09
  value="SYS_DZAYDZXFEF1OQRKZUBTDF4UHRF"
 Bind#2
  oacdty=02 mxl=22(22) mxlc=00 mal=00 scl=00 pre=00
  oacflg=00 fl2=1000001 frm=00 csi=00 siz=144 off=0
  kxsbbbfp=ffffffff77e770a8  bln=22  avl=02  flg=05
  value=3
 Bind#3
  oacdty=02 mxl=22(22) mxlc=00 mal=00 scl=00 pre=00
  oacflg=00 fl2=1000001 frm=00 csi=00 siz=0 off=24
  kxsbbbfp=ffffffff77e770c0  bln=22  avl=02  flg=01
  value=2
 Bind#4
  oacdty=02 mxl=22(22) mxlc=00 mal=00 scl=00 pre=00
  oacflg=00 fl2=1000001 frm=00 csi=00 siz=0 off=48
  kxsbbbfp=ffffffff77e770d8  bln=22  avl=01  flg=01
  value=0
 Bind#5
  oacdty=02 mxl=22(22) mxlc=00 mal=00 scl=00 pre=00
  oacflg=00 fl2=1000001 frm=00 csi=00 siz=0 off=72
  kxsbbbfp=ffffffff77e770f0  bln=22  avl=02  flg=01
  value=1
 Bind#6
  oacdty=02 mxl=22(22) mxlc=00 mal=00 scl=00 pre=00
  oacflg=00 fl2=1000001 frm=00 csi=00 siz=0 off=96
  kxsbbbfp=ffffffff77e77108  bln=22  avl=01  flg=01
  value=0
 Bind#7
  oacdty=02 mxl=22(22) mxlc=00 mal=00 scl=00 pre=00
  oacflg=00 fl2=1000001 frm=00 csi=00 siz=0 off=120
  kxsbbbfp=ffffffff77e77120  bln=22  avl=04  flg=01
  value=512690
 Bind#8
  oacdty=01 mxl=32(02) mxlc=00 mal=00 scl=00 pre=00
  oacflg=10 fl2=0001 frm=01 csi=171 siz=32 off=0
  kxsbbbfp=ffffffff7fff86c4  bln=32  avl=02  flg=09
  value="TC"
```

Using Tom Kyte's `print_table` procedure, I retrieve the `USER$` row in a more readable format:

```sql hl_lines="3 4 20 22"
SQL> exec print_table(q'#select * from sys.user$ where name='SYS_DZAYDZXFEF1OQRKZUBTDF4UHRF'#')
USER#                         : 859
NAME                          : SYS_DZAYDZXFEF1OQRKZUBTDF4UHRF
TYPE#                         : 2
PASSWORD                      :
DATATS#                       : 3
TEMPTS#                       : 2
CTIME                         : 22.07.2015 15:44:08
PTIME                         :
EXPTIME                       :
LTIME                         :
RESOURCE$                     : 1
AUDIT$                        :
DEFROLE                       : 0
DEFGRP#                       :
DEFGRP_SEQ#                   :
ASTATUS                       : 0
LCOUNT                        : 0
DEFSCHCLASS                   :
EXT_USERNAME                  : TC
SPARE1                        : 16
SPARE2                        : 512690
SPARE3                        :
SPARE4                        :
SPARE5                        :
SPARE6                        :
SPARE7                        :
SPARE8                        :
SPARE9                        :
SPARE10                       :
SPARE11                       :
-----------------
```

It can be seen that `USER$` was populated with a new row that has a rather obscure `NAME` `SYS_%`. The new row has `TYPE#=2`.

According to the definition of the `SYS.USER$` table from `@?/rdbms/admin/dcore.bsq`, it is an "adjunct" schema:

```sql
create table user$                                             /* user table */
( user#         number not null,                   /* user identifier number */
  name          varchar2("M_IDEN") not null,                 /* name of user */
               /* 0 = role, 1 = user, 2 = adjunct schema, 3 = schema synonym */
```

The row has `EXT_USERNAME` the same as the original schema:

```
EXT_USERNAME                  : TC
```

`SPARE2` - references to the edition object:

```sql hl_lines="1 7 9"
SPARE2                        : 512690

SQL> exec print_table('select * from dba_objects where object_id=512690')
OWNER                         : SYS
OBJECT_NAME                   : E1
SUBOBJECT_NAME                :
OBJECT_ID                     : 512690
DATA_OBJECT_ID                :
OBJECT_TYPE                   : EDITION
CREATED                       : 22.07.2015 15:44:08
LAST_DDL_TIME                 : 22.07.2015 15:44:08
TIMESTAMP                     : 2015-07-22:15:44:08
STATUS                        : VALID
TEMPORARY                     : N
GENERATED                     : N
SECONDARY                     : N
NAMESPACE                     : 64
EDITION_NAME                  :
SHARING                       : NONE
EDITIONABLE                   :
ORACLE_MAINTAINED             : N
-----------------
```

The second adjunct schema points to the `E2` edition (some rows are skipped for readability):

```sql hl_lines="3 4 6 8 15 17"
SQL> exec print_table(q'#select * from sys.user$ where name='SYS_D$8SPB$NEB3PDFCNYRJHBAV7MK'#')
USER#                         : 861
NAME                          : SYS_D$8SPB$NEB3PDFCNYRJHBAV7MK
TYPE#                         : 2
...
EXT_USERNAME                  : TC
SPARE1                        : 16
SPARE2                        : 512691
...

SQL> exec print_table('select * from dba_objects where object_id=512691')
OWNER                         : SYS
OBJECT_NAME                   : E2
SUBOBJECT_NAME                :
OBJECT_ID                     : 512691
DATA_OBJECT_ID                :
OBJECT_TYPE                   : EDITION
CREATED                       : 22.07.2015 15:44:08
LAST_DDL_TIME                 : 22.07.2015 15:44:08
TIMESTAMP                     : 2015-07-22:15:44:08
STATUS                        : VALID
TEMPORARY                     : N
GENERATED                     : N
SECONDARY                     : N
NAMESPACE                     : 64
EDITION_NAME                  :
SHARING                       : NONE
EDITIONABLE                   :
ORACLE_MAINTAINED             : N
-----------------
```

Here is a list of adjunct schemas in one of production databases with just one edition (we purge old editions on a regular basis):

```sql
SQL> select name from sys.user$ where type#=2;

NAME
------------------------------
SYS_CTO$G3UFDV01YXT$0I2IIAM1FW
SYS_#65J#JRLAO7834YSNCQ09MJB0#
SYS_CFV3AQP2WPEDH4WG#BC_OY_529
SYS_MAEDFDRVL4UF6O0_K#2IKFG332
SYS_ZTM78VJZ1NRBT0OZ7CX3QQYWO#
SYS_PBOZ#4GB#AZAEGM2DQ62ODWO1Q
SYS_4OYT_40J6MSQ9HK4L$R5K8ZD8G
SYS_7DT8CD#ARM8HF8LE5K6T7#G91K
SYS_DAL9_OKM$3EL#MH_IA4IYDJ6V8
SYS_7W7SDDSF#H6QO#D8F_CFH6HL5A
SYS_WW9CZFBWQZH45YCIQW9Z8QXDPG
SYS_R0CCNSCA$$67F4F3JASWEJXZMS
SYS___IC1EVBW5MA9VL6BUY958MFEQ
SYS_JY31UD09PBTXAUV#YLDG8ND1X$
SYS_CMD9YMUP#4W3IRHEA99$OA_2$H
SYS_375#5FX937$H68GJ_ZSX5ROSP3
SYS_U5$O#5LBHUX78D5M6C421CM_F#
SYS_FFQSGVBBM97GZCOVA7ZZCXOE6N
SYS_DX#I9P0FLCROTW5_FUQ0TG4L$M
SYS_7CFP28DK1RX$CV#ES#WEKAJ1WR
```

Sometimes we have from 5 to 6 editions in place. That results in 100-120 additional schemas used by EBR!

Now you know, if you find a row in `USER$` with `TYPE#=2` that has an obscure name like `SYS_%` - it's normal.
At least if you are using editions.
