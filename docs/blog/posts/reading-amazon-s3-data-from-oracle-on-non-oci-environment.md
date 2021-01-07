---
categories:
  - Oracle
date:
  created: 2021-01-07T01:14:00
description: >-
  Demonstrate how to read Amazon S3 data from Oracle Database on a non-OCI environment utilizing Oracle provided packages.
tags:
  - 19c
  - OERR
  - PL/SQL
  - SQL
---

# Reading Amazon S3 Data from Oracle on non-OCI Environment

In this post, let us demonstrate how to read Amazon S3 data from Oracle Database running on a non-OCI environment.

<!-- more -->

It is known that [DBMS\_CLOUD](https://docs.oracle.com/en/cloud/paas/autonomous-database/adbsa/dbms-cloud.html#GUID-2AFBEFA4-992E-4F53-96DB-F560084C7DA9) can be used to read Amazon S3 data.
However, it is one of the packages supplied by Oracle for its Autonomous Database offering.
Likewise, Amazon RDS provides some [S3 integration](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/oracle-s3-integration.html) as well.

What about customers who do not use either of these?
I used to work for a company where we were using [alexandria-plsql-utils](https://github.com/mortenbra/alexandria-plsql-utils) to load data from S3.
Coincidentally, I have been looking for something recently on MOS and came across the following bug: [Bug 28867698 - Inclusion of DBMS\_CLOUD into "STANDARD" Oracle (Doc ID 28867698.8)](https://support.oracle.com/CSP/main/article?cmd=show&type=NOT&id=28867698.8).
It sounded promising, so that I decided to investigate as to how this package can be adapted for reading S3 data.

## Prerequisites

The fix for the bug is included in 19.9 DB October 2020 Release Update.
I assume this package and its dependencies can be installed in earlier releases/release updates.
However, I have no idea whether it will work there.
I can imagine that there might be some issues, to name a few:

- `DBMS_CLOUD` and its dependencies use JSON.
  Its support has been gradually improving over the last releases. It might be the case that some of the functionality will not work properly in older releases.
- Not only is this about the package and other supplied database objects, but also it is about the `ORACLE_LOADER` access driver.
  If it does not provide the required capabilities in older releases, then again it is not something that can be fixed easily.

## Environment

My environment is 19.9 CDB Single Instance on Azure:

```
[oracle@myhostname ~]$ $ORACLE_HOME/OPatch/opatch lspatches
31772784;OCW RELEASE UPDATE 19.9.0.0.0 (31772784)
31771877;Database Release Update : 19.9.0.0.201020 (31771877)

OPatch succeeded.
```

I created a new PDB for this exercise:

```sql
SQL> create pluggable database tc admin user pdb_admin identified by oracle;

Pluggable database created.

SQL> alter pluggable database tc open;

Pluggable database altered.
```

Since I am going to read data from S3, I created a new bucket `mikhail-bucket-20210104`.
It is non-public, so that I created a new IAM user, and assigned the following policy to it:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "Stmt1508867055000",
            "Effect": "Allow",
            "Action": [
                "s3:GetObject"
            ],
            "Resource": [
                "arn:aws:s3:::mikhail-bucket-20210104/*"
            ]
        }
    ]
}
```

Then, I saved user's access and secret keys which will be used to establish an S3 connection from the Oracle database.

## Installation Steps

I used the following script to install `DBMS_CLOUD` as `SYS`:

```sql
spo /tmp/dbms_cloud

@?/rdbms/admin/dbms_cloud_types.sql
@?/rdbms/admin/dbms_cloud.sql
@?/rdbms/admin/dbms_cloud_task_catalog.sql
@?/rdbms/admin/dbms_cloud_catalog.sql
@?/rdbms/admin/dbms_cloud_task_views.sql
@?/rdbms/admin/dbms_cloud_capability.sql
@?/rdbms/admin/prvt_cloud_core.plb
@?/rdbms/admin/prvt_cloud_core_body.plb
@?/rdbms/admin/prvt_cloud_internal.plb
@?/rdbms/admin/prvt_cloud_request.plb
@?/rdbms/admin/prvt_cloud_task.plb
@?/rdbms/admin/prvt_cloud_task_body.plb
@?/rdbms/admin/prvt_cloud_body.plb
@?/rdbms/admin/prvt_cloud_capability_body.plb
@?/rdbms/admin/prvt_cloud_internal_body.plb
@?/rdbms/admin/prvt_cloud_request_body.plb
@?/rdbms/admin/dbms_cloud_metadata.sql

spo off
```

These are the files that Oracle added in 19.9.
Presumably they were provided by the fix for [Bug 28867698 - Inclusion of DBMS\_CLOUD into "STANDARD" Oracle (Doc ID 28867698.8)](https://support.oracle.com/CSP/main/article?cmd=show&type=NOT&id=28867698.8).

I am going to access S3 via HTTPS.
Therefore, I created a new empty wallet `/u01/app/oracle/wallet`:

```
[oracle@myhostname ~]$ mkdir -p /u01/app/oracle/wallet
[oracle@myhostname ~]$ orapki wallet create -wallet /u01/app/oracle/wallet -pwd Oracle123 -auto_login
Oracle PKI Tool Release 21.0.0.0.0 - Production
Version 21.0.0.0.0
Copyright (c) 2004, 2020, Oracle and/or its affiliates. All rights reserved.

Operation is successfully completed.
```


I also need to load SSL certificates into the wallet. I use openssl to get the certificates.

``` hl_lines="13 18 21 26"
[oracle@myhostname ~]$ openssl s_client -showcerts -connect s3.amazonaws.com:443 </dev/null
CONNECTED(00000003)
depth=2 C = IE, O = Baltimore, OU = CyberTrust, CN = Baltimore CyberTrust Root
verify return:1
depth=1 C = US, O = DigiCert Inc, OU = www.digicert.com, CN = DigiCert Baltimore CA-2 G2
verify return:1
depth=0 C = US, ST = Washington, L = Seattle, O = "Amazon.com, Inc.", CN = s3.amazonaws.com
verify return:1
---
Certificate chain
 0 s:/C=US/ST=Washington/L=Seattle/O=Amazon.com, Inc./CN=s3.amazonaws.com
   i:/C=US/O=DigiCert Inc/OU=www.digicert.com/CN=DigiCert Baltimore CA-2 G2
-----BEGIN CERTIFICATE-----
MIIIGTCCBwGgAwIBAgIQDWRQa0XzDONabC3fLBi0NzANBgkqhkiG9w0BAQsFADBk
<skip>
x+JAorfCzDKa+P1lgCh3+V5Lnqvla2hwCyCnYAy1RR0y1UEUB8FUYj1/PIDs9RJX
cVq+ZBjAtIrm6j5b+Q==
-----END CERTIFICATE-----
 1 s:/C=US/O=DigiCert Inc/OU=www.digicert.com/CN=DigiCert Baltimore CA-2 G2
   i:/C=IE/O=Baltimore/OU=CyberTrust/CN=Baltimore CyberTrust Root
-----BEGIN CERTIFICATE-----
MIIEYzCCA0ugAwIBAgIQAYL4CY6i5ia5GjsnhB+5rzANBgkqhkiG9w0BAQsFADBa
<skip>
0WyzT7QrhExHkOyL4kGJE7YHRndC/bseF/r/JUuOUFfrjsxOFT+xJd1BDKCcYm1v
upcHi9nzBhDFKdT3uhaQqNBU4UtJx5g=
-----END CERTIFICATE-----
---
Server certificate
subject=/C=US/ST=Washington/L=Seattle/O=Amazon.com, Inc./CN=s3.amazonaws.com
issuer=/C=US/O=DigiCert Inc/OU=www.digicert.com/CN=DigiCert Baltimore CA-2 G2
---
No client certificate CA names sent
Peer signing digest: SHA256
Server Temp Key: ECDH, P-256, 256 bits
---
SSL handshake has read 3712 bytes and written 415 bytes
---
New, TLSv1/SSLv3, Cipher is ECDHE-RSA-AES128-GCM-SHA256
Server public key is 2048 bit
Secure Renegotiation IS supported
Compression: NONE
Expansion: NONE
No ALPN negotiated
SSL-Session:
    Protocol  : TLSv1.2
    Cipher    : ECDHE-RSA-AES128-GCM-SHA256
    Session-ID: 5BE1D3D1A79399E9728D7E0B2CD4E1F041DCEC03087D4EFAEF6131AF5A8ABF80
    Session-ID-ctx:
    Master-Key: 7E05806771AF48B9A9EA7DC6B5DBC4E064F315825F4BE411C7D5FB97B189B0643BE7200463EB29D44A4CF12951AF2C2A
    Key-Arg   : None
    Krb5 Principal: None
    PSK identity: None
    PSK identity hint: None
    Start Time: 1609936308
    Timeout   : 300 (sec)
    Verify return code: 0 (ok)
---
DONE
```

Essentially, I have to load two certificates bounded by `BEGIN`/`END CERTIFICATE` lines.
I wrote a one-liner for that - it extracts certificates using `sed`, and pipes it through `csplit` to write each certificate to a separate file:

```
[oracle@myhostname ~]$ openssl s_client -showcerts -connect s3.amazonaws.com:443 </dev/null 2>/dev/null | sed '/BEGIN/,/END/!d' | csplit -f aws -b '%d.pem' - /END/+1
2870
1582
[oracle@myhostname ~]$ ll aws?.pem
-rw-r--r-- 1 oracle oinstall 2870 Jan  6 12:33 aws0.pem
-rw-r--r-- 1 oracle oinstall 1582 Jan  6 12:33 aws1.pem
```

Now I can load both certificates into the wallet:

```
[oracle@myhostname ~]$ orapki wallet add -wallet /u01/app/oracle/wallet -cert aws0.pem -trusted_cert -pwd Oracle123
Oracle PKI Tool Release 21.0.0.0.0 - Production
Version 21.0.0.0.0
Copyright (c) 2004, 2020, Oracle and/or its affiliates. All rights reserved.

Operation is successfully completed.
[oracle@myhostname ~]$ orapki wallet add -wallet /u01/app/oracle/wallet -cert aws1.pem -trusted_cert -pwd Oracle123
Oracle PKI Tool Release 21.0.0.0.0 - Production
Version 21.0.0.0.0
Copyright (c) 2004, 2020, Oracle and/or its affiliates. All rights reserved.

Operation is successfully completed.
[oracle@myhostname ~]$ orapki wallet display -wallet /u01/app/oracle/wallet
Oracle PKI Tool Release 21.0.0.0.0 - Production
Version 21.0.0.0.0
Copyright (c) 2004, 2020, Oracle and/or its affiliates. All rights reserved.

Requested Certificates:
User Certificates:
Trusted Certificates:
Subject:        CN=DigiCert Baltimore CA-2 G2,OU=www.digicert.com,O=DigiCert Inc,C=US
Subject:        CN=s3.amazonaws.com,O=Amazon.com\, Inc.,L=Seattle,ST=Washington,C=US
```

At this stage, I can fire an HTTP request:

```sql
SQL> select utl_http.request('https://mikhail-bucket-20210104.s3.amazonaws.com/sales_2020.csv',
  2                          null,
  3                          'file:/u01/app/oracle/wallet')
  4           get_request
  5    from dual;

GET_REQUEST
--------------------------------------------------------------------------------
<?xml version="1.0" encoding="UTF-8"?>
<Error><Code>AccessDenied</Code><Message>Access Denied</Message><RequestId>9A9C3
73E50A59095</RequestId><HostId>cGMOSk5WlNt0MNa++5c/N1JdIMSYH7fsSmj9ETSUHT7d1ztYO
40CSmQDSJF2sht8W/HoX23utI8=</HostId></Error>
```

The `AccessDenied` error is expected - I have to supply the AWS credentials.
However, if it was a bucket with public access, it should work fine.

## DB User and S3 Credentials

Let us now create a new database user whose schema owns S3 credentials and any other application objects:

```sql
SQL> grant dba to tc identified by tc;

Grant succeeded.
```

Create new credentials using access and secret keys:

```sql
SQL> conn tc/tc@localhost/tc
Connected.
SQL>
SQL> exec dbms_credential.create_credential( -
>   credential_name => 'S3_CREDENTIAL', -
>   username => 'A******************3', -
>   password => '1**************************************E')

PL/SQL procedure successfully completed.
```

## SSL Wallet

It is about time to add something to the S3 bucket. For that, I uploaded the `sales_2020.csv` file to my S3 bucket:

```
2020-01-01,1,10,100
2020-02-01,2,5,200
2020-03-01,2,10,400
```

Yet I am still not able to select anything using my S3 location:

```sql
SQL> select *
  2    from external (
  3           ( sold_date date,
  4             product_id number,
  5             quantity_sold number(10,2),
  6             amount_sold number(10,2)
  7           )
  8           type oracle_loader
  9           default directory data_pump_dir
 10           access parameters (
 11             records delimited by newline
 12             nologfile
 13             nobadfile
 14             nodiscardfile
 15             readsize=10000000
 16             credential 'S3_CREDENTIAL'
 17             fields terminated by ','
 18             date_format date mask 'yyyy-mm-dd')
 19           location ('https://mikhail-bucket-20210104.s3.amazonaws.com/sales_2020.csv')
 20           reject limit unlimited);
select *
*
ERROR at line 1:
ORA-29913: error in executing ODCIEXTTABLEOPEN callout
ORA-20000: Database property SSL_WALLET not found
ORA-06512: at "SYS.DBMS_CLOUD", line 917
ORA-06512: at "SYS.DBMS_CLOUD_INTERNAL", line 3823
ORA-06512: at line 1
```

The package tries to find that property `SSL_WALLET` in `DATABASE_PROPERTIES`.
At present I use a quick and dirty workaround by adding a new row into `SYS.PROPS$` in `CDB$ROOT`:

```sql
SQL> insert into props$(name, value$, comment$) values ('SSL_WALLET', '/u01/app/oracle/wallet', 'SSL Wallet');

1 row created.

SQL> commit;
```

There is also an undocumented system parameter `ssl_wallet` which I assume was intended to have something to do with this.
The `DBMS_CLOUD` code, though, queries `DATABASE_PROPERTIES` directly.
Although I assume the code can be rewritten somehow to make use of the `ssl_wallet` parameter, my intention is to use that package as is.

Having added new `SSL_WALLET` property, I am now finally able to access the S3 bucket:

```sql
SQL> select *
  2    from external (
  3           ( sold_date date,
  4             product_id number,
  5             quantity_sold number(10,2),
  6             amount_sold number(10,2)
  7           )
  8           type oracle_loader
  9           default directory data_pump_dir
 10           access parameters (
 11             records delimited by newline
 12             nologfile
 13             nobadfile
 14             nodiscardfile
 15             readsize=10000000
 16             credential 'S3_CREDENTIAL'
 17             fields terminated by ','
 18             date_format date mask 'yyyy-mm-dd')
 19           location ('https://mikhail-bucket-20210104.s3.amazonaws.com/sales_2020.csv')
 20           reject limit unlimited);

SOLD_DATE PRODUCT_ID QUANTITY_SOLD AMOUNT_SOLD
--------- ---------- ------------- -----------
01-JAN-20          1            10         100
01-FEB-20          2             5         200
01-MAR-20          2            10         400
```

## Hybrid Partitioned Table

As an extra exercise, I created a hybrid partitioned table - it has both external and traditional partitions:

```sql
SQL> create table sales_hybrid
  2    ( sold_date date,
  3      product_id number,
  4      quantity_sold number(10,2),
  5      amount_sold number(10,2)
  6    )
  7    external partition attributes (
  8      type oracle_loader
  9      default directory data_pump_dir
 10      access parameters (
 11        records delimited by newline
 12        nologfile
 13        nobadfile
 14        nodiscardfile
 15        credential 'S3_CREDENTIAL'
 16        fields terminated by ','
 17        date_format date mask 'yyyy-mm-dd'
 18      )
 19    )
 20    partition by range(sold_date) (
 21      partition sales_2020 values less than (date'2021-01-01')
 22        external location ('https://mikhail-bucket-20210104.s3.amazonaws.com/sales_2020.csv'),
 23      partition sales_2021 values less than (date'2022-01-01')
 24    )
 25  ;

Table created.

SQL>
SQL> insert into sales_hybrid values(date'2021-01-01',1,10,150);

1 row created.

SQL> select * from sales_hybrid;

SOLD_DATE PRODUCT_ID QUANTITY_SOLD AMOUNT_SOLD
--------- ---------- ------------- -----------
01-JAN-20          1            10         100
01-FEB-20          2             5         200
01-MAR-20          2            10         400
01-JAN-21          1            10         150
```

Moreover, we can even access compressed files:

```sql hl_lines="16 27"
SQL> drop table sales_hybrid;

Table dropped.

SQL> create table sales_hybrid
  2    ( sold_date date,
  3      product_id number,
  4      quantity_sold number(10,2),
  5      amount_sold number(10,2)
  6    )
  7    external partition attributes (
  8      type oracle_loader
  9      default directory data_pump_dir
 10      access parameters (
 11        records delimited by newline
 12        compression gzip
 13        nologfile
 14        nobadfile
 15        nodiscardfile
 16        credential 'S3_CREDENTIAL'
 17        fields terminated by ','
 18        date_format date mask 'yyyy-mm-dd'
 19      )
 20    )
 21    partition by range(sold_date) (
 22      partition sales_2020 values less than (date'2021-01-01')
 23        external location ('https://mikhail-bucket-20210104.s3.amazonaws.com/sales_2020.csv.gz'),
 24      partition sales_2021 values less than (date'2022-01-01')
 25    )
 26  ;

Table created.

SQL>
SQL> insert into sales_hybrid values(date'2021-01-01',1,10,150);

1 row created.

SQL>
SQL> select * from sales_hybrid;

SOLD_DATE PRODUCT_ID QUANTITY_SOLD AMOUNT_SOLD
--------- ---------- ------------- -----------
01-JAN-20          1            10         100
01-FEB-20          2             5         200
01-MAR-20          2            10         400
01-JAN-21          1            10         150
```


gzip, zlib, bzip2 compression schemes are supported per [the documentation](https://docs.oracle.com/en/cloud/paas/autonomous-database/adbsa/format-options.html#GUID-08C44CDA-7C81-481A-BA0A-F7346473B703).
We might as well utilize [the new ORA\_PARTITION\_VALIDATION SQL function](https://docs.oracle.com/en/database/oracle/oracle-database/19/vldbg/partition-concepts.html#GUID-EA7EF5CB-DD49-43AF-889A-F83AAC0D7D51) to see if the rows conform to the partition definition:

```sql
SQL> select ora_partition_validation(rowid), sh.* from sales_hybrid sh;

ORA_PARTITION_VALIDATION(ROWID) SOLD_DATE PRODUCT_ID QUANTITY_SOLD AMOUNT_SOLD
------------------------------- --------- ---------- ------------- -----------
                              1 01-JAN-20          1            10         100
                              1 01-FEB-20          2             5         200
                              1 01-MAR-20          2            10         400
                              1 01-JAN-21          1            10         150
```
