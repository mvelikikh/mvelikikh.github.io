---
categories:
  - Oracle
date:
  created: 2021-12-17T23:54:00
description: >-
  It is possible to use credential objects in database links since 21c.
  The functionality was backported to 19c too.
  This post shows this new capability.
tags:
  - 19c
  - 21c
  - OERR
---

# Using credentials with database links in 21c

Since 21c it is now possible to use credential objects in database links.
This post demonstrates the new capability.

<!-- more -->

## Demonstration

Here is a short demonstration of this functionality:

```sql
SQL> exec dbms_credential.create_credential('TC_CRED', 'TC', 'tc')

PL/SQL procedure successfully completed.

SQL>
SQL> create database link link1 connect with tc_cred using 'localhost/pdb';

Database link created.

SQL> create database link link2 connect with tc_cred using 'localhost/pdb';

Database link created.

SQL>
SQL> select * from dual@link1;

D
-
X

SQL> select * from dual@link2;

D
-
X
```

SQL Language Reference has not been updated with the new syntax yet.
If we alter the user's password, the existing database links will not work anymore (I do not consider gradual password rollover here):

```sql
SQL> alter user tc identified by tc2;

User altered.

SQL>
SQL> alter session close database link link1;

Session altered.

SQL> alter session close database link link2;

Session altered.

SQL>
SQL> select * from dual@link1;
select * from dual@link1
                   *
ERROR at line 1:
ORA-01017: invalid username/password; logon denied
ORA-02063: preceding line from LINK1
```

It is enough to alter the credential objects to make the database links work again:

```sql
SQL> exec dbms_credential.update_credential('TC_CRED', 'PASSWORD', 'tc2')

PL/SQL procedure successfully completed.

SQL>
SQL> select * from dual@link1;

D
-
X

SQL> select * from dual@link2;

D
-
X
```

## Conclusion

This functionality really comes into its own when you re-use one username and password pair in multiple database links.
If we want to change the username or password, there is no need to change each link anymore.
We can alter one credential object instead.
The functionality has been backported to 19c as well: [Bug 29541929 - support credential objects in database links (Doc ID 29541929.8)](https://support.oracle.com/rs?type=doc&id=29541929.8).
