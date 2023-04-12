---
categories:
  - Oracle
date:
  created: 2023-04-13T00:05:00
description: >-
  Demonstrate ora_hash Python program that shows how to compute ORA_HASH for a given value in Python.
  Test it on non-string data types, such as NUMBER and DATE.
  Also show that the function supports max_bucket and seed_value parameters similar to the ORA_HASH Oracle SQL function.
tags:
  - SQL
---

# Computing ORA_HASH

This post is written to demonstrate a Python function computing `ORA_HASH`.

<!-- more -->

## Introduction

I wrote a short Python [function](/tools.md#ora_hash) to compute a hash value for a given expression.
The return value of the function matches the return value of [ORA\_HASH](https://docs.oracle.com/en/database/oracle/oracle-database/23/sqlrf/ORA_HASH.html#GUID-0349AFF5-0268-43CE-8118-4F96D752FDE6) on inputs I tested it with in Oracle 23c on Linux x86-64.

In its simplest form, the invocation can be as follows:

```python title="Python"
>>> ora_hash(b'test')
2662839991
```

```sql title="SQL"
SQL> select ora_hash('test');

ORA_HASH('TEST')
----------------
      2662839991
```

## Handling non-string data types

In case of non-string data types, some conversion should be performed.
`ORA_HASH` accepts a variety of data types.
I use `NUMBER` and `DATE` in the examples below.
The procedure is essentially the same with both data types: need to take the internal representation of a value in Oracle and pass it to Python.
It should be possible to handle any other supported data types following the same procedure.

### NUMBER

```sql title="SQL"
SQL> select ora_hash(2023);

ORA_HASH(2023)
--------------
    2671887358

SQL> select dump(2023, 16);

DUMP(2023,16)
---------------------
Typ=2 Len=3: c2,15,18
```

```python title="Python"
>>> ora_hash(b'\xc2\x15\x18')
2671887358
```

### DATE

```sql title="SQL"
SQL> select ora_hash(to_date('2023-03-01 12:34:56', 'yyyy-mm-dd hh24:mi:ss'));

ORA_HASH(TO_DATE('2023-03-0112:34:56','YYYY-MM-DDHH24:MI:SS'))
--------------------------------------------------------------
                                                     112410422

SQL> select dump(to_date('2023-03-01 12:34:56', 'yyyy-mm-dd hh24:mi:ss'), 16);

DUMP(TO_DATE('2023-03-0112:34:56
--------------------------------
Typ=13 Len=8: e7,7,3,1,c,22,38,0
```

```python title="Python"
>>> ora_hash(b'\xe7\x07\x03\x01\x0c\x22\x38\x00')
112410422
```

## Specifying max\_bucket and seed\_value

These parameters are also supported.

### MAX\_BUCKET

```sql title="SQL"
SQL> select ora_hash('abracadabra', 255);

ORA_HASH('ABRACADABRA',255)
---------------------------
                         82
```

```python title="Python"
>>> ora_hash(b'abracadabra', 255)
82
```

### SEED\_VALUE

```sql title="SQL"
SQL> select ora_hash('abracadabra', power(2,32)-1, 123);

ORA_HASH('ABRACADABRA',POWER(2,32)-1,123)
-----------------------------------------
                               4012392341
```

```python title="Python"
>>> ora_hash(b'abracadabra', seed=123)
4012392341
```

### MAX\_BUCKET and SEED\_VALUE

```sql title="SQL"
SQL> select ora_hash('abracadabra', 255, 123);

ORA_HASH('ABRACADABRA',255,123)
-------------------------------
                            149
```

```python title="Python"
>>> ora_hash(b'abracadabra', 255, 123)
149
```
