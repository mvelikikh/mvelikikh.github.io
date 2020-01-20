---
categories:
  - Oracle
date:
  created: 2020-01-20T23:00:00
description: >-
  Oracle backported SQL Macros to 19.6.
  At least SQL_MACRO(TABLE) works as this post demonstrates.
tags:
  - 19c
  - PL/SQL
---

# Bug 30324180 SQL Macro should be backported to 19.5

While reviewing the list of bugs fixed in 19.6, I found that Oracle backported SQL Macros to 19.6 judging by the bug description.

<!-- more -->

When Oracle released 19.6 release update, I went to the usual My Oracle Support (MOS) note: [Database 19 Release Updates and Revisions Bugs Fixed Lists (Doc ID 2523220.1)](https://support.oracle.com/rs?type=doc&id=2523220.1) to find out what exactly was included there that might be of interest for me.
Surprisingly, the note was not updated in several days, so that I decided to download the release update and take a look at it myself.

Oracle patches follow a well-defined structure that was described by Martin Berger: [Oracle patches - a patchfiles anatomy](http://berxblog.blogspot.com/2019/10/oracle-patches-patchfiles-anatomy.html).

One bug drew my eye:

```xml
<bug description="SQM MACRO SHOULD BE BACKPORTED TO 19.5" number="30324180"/>
```

The relevant note contains some important information, albeit without any examples: [Bug 30324180 - SQL Macro should be backported to 19.5 (Doc ID 30324180.8)](https://support.oracle.com/rs?type=doc&id=30324180.8)

Thankfully, there is a clue that the table semantics macro should be supported, so that I decided to skim through an excellent Keith Laker's presentation on that subject: [A New Approach to Simplifying Complex SQL-Using SQL Macros in Database 20c](https://static.rainfocus.com/oracle/oow19/sess/1553765929286001lSFW/PF/SQL-Macros-Overview_1569084990942001SWly.pdf).

After a bit of toing and froing, I constructed the following example that demonstrates this new functionality (as it seems).

```sql
SQL> create table t1
  2  as
  3  select n,
  4         'val_'||to_char(n, 'fm00') val
  5    from xmltable('1 to 10'
  6           columns
  7             n int path '.');

Table created.

SQL>
SQL> create table t2
  2  as
  3  select 'val_'||to_char(n, 'fm00') s
  4    from xmltable('1 to 10'
  5           columns
  6             n int path '.');

Table created.

SQL>
SQL> select * from t1;

         N VAL
---------- -------
         1 val_01
         2 val_02
         3 val_03
         4 val_04
         5 val_05
         6 val_06
         7 val_07
         8 val_08
         9 val_09
        10 val_10

SQL> select * from t2;

S
-------
val_01
val_02
val_03
val_04
val_05
val_06
val_07
val_08
val_09
val_10
```

I created two tables with a different structure.
The [MOS note](https://support.oracle.com/rs?type=doc&id=30324180.8) says about the table semantics macro, which is supposedly demonstrated on 22nd slide of [Keith's presentation](https://static.rainfocus.com/oracle/oow19/sess/1553765929286001lSFW/PF/SQL-Macros-Overview_1569084990942001SWly.pdf).

I was not able to get `SQL_MACRO(TABLE)` work, so that I ended up with the following example:

```sql
SQL> CREATE OR REPLACE FUNCTION sample(t DBMS_TF.Table_t, how_many number DEFAULT 5)
  2  RETURN VARCHAR2 SQL_MACRO
  3  AS
  4  BEGIN
  5    RETURN q'[SELECT *
  6                FROM t
  7               WHERE rownum <= how_many]';
  8  END sample;
  9  /

Function created.

SQL> select *
  2    from sample(t1, 3);

         N VAL
---------- -------
         1 val_01
         2 val_02
         3 val_03

SQL>
SQL> select *
  2    from sample(t1);

         N VAL
---------- -------
         1 val_01
         2 val_02
         3 val_03
         4 val_04
         5 val_05

SQL>
SQL> select *
  2    from sample(t2);

S
-------
val_01
val_02
val_03
val_04
val_05

```

I traced the last two statements through Intel Pin debugtrace and grepped the resulted file for the SQM string (which are presumably Oracle functions corresponding to the SQL Macro functionality):

```
<> qksptfSQM_Describe(0x7ff400bc6050, 0x6b76cbd8, ...)
| > qksptfSQM_Init(0x7ff400bc6050, 0x6b76cbd8, ...)
| | > qksptfSQM_Check_Errors(0x6b76cdf8, 0x7ff400b2c7a8, ...)
| | < qksptfSQM_Check_Errors+0x000000000090 returns: 0x7ff400b2c770
| < qksptfSQM_Init+0x0000000005d5 returns: 0x7ff400b2c7a8
| > qksptfSQM_GetTxt(0x7ff400b2c7a8, 0x1, ...)
| | | | | | | | | | | < qksptfSQM_GetTxt+0x000000001d51 returns: 0x6b76cdf8
| | | | | | | | | | | > qksptfSQM_Template(0x7ff400b2c7a8, 0, ...)
| | | | | | | | | | | < qksptfSQM_Template+0x0000000009ca returns: 0x6b76cdf8
| | | | | | | | | | | > qksptfSQM_Parse(0x7ff400b2c7a8, 0, ...)
| | | | | | | | | | | | | | | | | | > qksptfSQM_Parse_errors(0x7ff400b2c448, 0xc0, ...)
| | | | | | | | | | | | | | | | | | | | | | | | < qksptfSQM_Parse_errors+0x00000000069a returns: 0
| | | | | | | | | | | | | | | | | | | | | | | | | > qksptfSQM_Model_Check(0x7ff400bba928, 0, ...)
| | | | | | | | | | | | | | | | | | | | | | | | | < qksptfSQM_Model_Check+0x000000000040 returns: 0x1
| | | | | | | | | | | | | | | | | | | | | | | | | | > qksptfSQM_Model_Check(0x7ff405adf108, 0, ...)
| | | | | | | | | | | | | | | | | | | | | | | | | | < qksptfSQM_Model_Check+0x000000000040 returns: 0x1
| | | | | | | | | | | | | | | | | | | | | | | | | | | > qksptfSQM_Model_Check(0x7ff405adde48, 0, ...)
| | | | | | | | | | | | | | | | | | | | | | | | | | | < qksptfSQM_Model_Check+0x000000000040 returns: 0x1
| | | | | | | | | | | | | | | | | | | | | | | | | | | > qksptfSQM_Model_Check(0x7ff405ade8a8, 0, ...)
| | | | | | | | | | | | | | | | | | | | | | | | | | | < qksptfSQM_Model_Check+0x000000000040 returns: 0x1
| | | | | | | | | | | | | | | | | | | | | | | | | | > qksptfSQM_Model_Check(0x7ff400bc4260, 0, ...)
| | | | | | | | | | | | | | | | | | | | | | | | | | < qksptfSQM_Model_Check+0x000000000040 returns: 0x1
| | | | | | | | | | | | | | | | | | | | | | | | | > qksptfSQM_rm_vqb(0x7ff400bc4260, 0x7ff400bba928, ...)
| | | | | | | | | | | | | | | | | | | | | | | | | < qksptfSQM_rm_vqb+0x00000000003d returns: 0x1
| | | | | | | | | | | | | | | | | | | | | | | | | > qksptfSQM_SetSQM_(0x7ff405adf108, 0x7ff400b2c7a8, ...)
| | | | | | | | | | | | | | | | | | | | | | | | | | | > qksptfSQM_SetSQM_(0x7ff400b2c110, 0x7ff400b2c7a8, ...)
| | | | | | | | | | | | | | | | | | | | | | | | | | | < qksptfSQM_SetSQM_+0x00000000007e returns: 0x1
| | | | | | | | | | | | | | | | | | | | | | | | | < qksptfSQM_SetSQM_+0x00000000007e returns: 0x1
| | | | | | | | | | | | | | | | | | | | | | | | | | > qksptfSQM_SetSQM_(0x7ff405adde48, 0x7ff400b2c7a8, ...)
| | | | | | | | | | | | | | | | | | | | | | | | | | < qksptfSQM_SetSQM_+0x00000000007e returns: 0x1
| | | | | | | | | | | | | | | | | | | | | | | | | | > qksptfSQM_SetSQM_(0x7ff405ade8a8, 0x7ff400b2c7a8, ...)
| | | | | | | | | | | | | | | | | | | | | | | | | | < qksptfSQM_SetSQM_+0x00000000007e returns: 0x1
| | | | | | | | | | | | | | | | | | | | | | | < qksptfSQM_Parse+0x000000000851 returns: 0x1
| | | | | | | | | | | | | | | | | | | | | | | > qksptfSQM_CleanupTDOs(0x3, 0x872027e0, ...)
| | | | | | | | | | | | | | | | | | | | | | | < qksptfSQM_CleanupTDOs+0x0000000001cd returns: 0x7ff400a5d73c
| | | | | | | | | | | | > qksptfSQM_PstPrc(0x7ff400bba928, 0x98b7af08, ...)
| | | | | | | | | | | | | > qksptfSQM_PstPrc1_(0x7ff400bba928, 0x7ff400bba928, ...)
| | | | | | | | | | | | | < qksptfSQM_PstPrc1_+0x000000000032 returns: 0x1
| | | | | | | | | | | | | | > qksptfSQM_PstPrc1_(0x7ff405adf108, 0x7ff400bba928, ...)
| | | | | | | | | | | | | | | | > qksptfSQM_QbcRelExp_(0x7ff405adde48, 0x7ff405aded30, ...)
| | | | | | | | | | | | | | | | | | | > qksptfSQM_ExpRepl_(0x7ffef8fc52e0, 0x7ff405ad8818, ...)
| | | | | | | | | | | | | | | | | | | < qksptfSQM_ExpRepl_+0x00000000005a returns: 0
| | | | | | | | | | | | | | | | | | | > qksptfSQM_ExpRepl_(0x7ffef8fc52e0, 0x7ff405addf10, ...)
| | | | | | | | | | | | | | | | | | | < qksptfSQM_ExpRepl_+0x00000000005a returns: 0
| | | | | | | | | | | | | | | | | | | | > qksptfSQM_ExpRepl_(0x7ffef8fc52e0, 0x7ff405add890, ...)
| | | | | | | | | | | | | | | | | | | | < qksptfSQM_ExpRepl_+0x00000000005a returns: 0
| | | | | | | | | | | | | | | | | | | | | > qksptfSQM_ExpRepl_(0x7ffef8fc52e0, 0x7ff405add850, ...)
| | | | | | | | | | | | | | | | | | | | | < qksptfSQM_ExpRepl_+0x00000000005a returns: 0
| | | | | | | | | | | | | | | | | | | | | | > qksptfSQM_ExpRepl_(0x7ffef8fc52e0, 0x7ff405adda28, ...)
| | | | | | | | | | | | | | | | | | | | | | < qksptfSQM_ExpRepl_+0x00000000005a returns: 0
| | | | | | | | | | | | | | | | | | | | | > qksptfSQM_ExpRepl_(0x7ffef8fc52e0, 0x7ff405add858, ...)
| | | | | | | | | | | | | | | | | | | | | < qksptfSQM_ExpRepl_+0x00000000005a returns: 0
| | | | | | | | | | | | | | | | < qksptfSQM_QbcRelExp_+0x000000000079 returns: 0x1
| | | | | | | | | | | | | | | | | > qksptfSQM_QbcRelExp_(0x7ff400b2c110, 0x7ff405aded30, ...)
| | | | | | | | | | | | | | | | | | | | > qksptfSQM_ExpRepl_(0x7ffef8fc5270, 0x7ff405add1c8, ...)
| | | | | | | | | | | | | | | | | | | | < qksptfSQM_ExpRepl_+0x00000000005a returns: 0
| | | | | | | | | | | | | | | | | < qksptfSQM_QbcRelExp_+0x000000000079 returns: 0x1
| | | | | | | | | | | | | | < qksptfSQM_PstPrc1_+0x000000000181 returns: 0x1
| | | | | | | | | | | | | | | > qksptfSQM_PstPrc1_(0x7ff405adde48, 0x7ff400bba928, ...)
| | | | | | | | | | | | | | | < qksptfSQM_PstPrc1_+0x000000000032 returns: 0x1
| | | | | | | | | | | | | | | | > qksptfSQM_PstPrc1_(0x7ff400b2c110, 0x7ff400bba928, ...)
| | | | | | | | | | | | | | | | < qksptfSQM_PstPrc1_+0x000000000032 returns: 0x1
```

As Fritz Hoogland identified them, those are new functions introduced in Oracle 19.6: [What’s new with Oracle database 19.6 versus 19.5](https://fritshoogland.wordpress.com/2020/01/16/whats-new-with-oracle-database-19-6-versus-19-5/).
I will wait till Oracle officially announces SQL Macros.
For those who cannot wait, they can play around with them even in 19.6.
Judging by [the bug description](https://support.oracle.com/rs?type=doc&id=30324180.8), the relevant functionality should be available for 19.5 (introduced without much fuss), but I have not found a one-off patch.
It might have been set unpublished, though.
