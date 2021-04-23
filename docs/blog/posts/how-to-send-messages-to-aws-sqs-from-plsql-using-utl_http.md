---
categories:
  - Oracle
date:
  created: 2021-04-23T23:00:00
description: >-
  Explain how to call AWS SQS from PL/SQL using UTL_HTTP.
  Provide a complete example, including wallet creation, and PL/SQL code.
  The same method could be applicable to other AWS services.
tags:
  - 19c
  - PL/SQL
---

# How to Send Messages to AWS SQS from PL/SQL Using UTL\_HTTP

This blog post provides a complete example showing how to send messages to an AWS SQS queue.

<!-- more -->

## AWS Prerequisites

I created a queue called TestQueue.
I also created an SQS VPC endpoint for the purpose of this example.

There is an IAM policy that I assigned to a dedicated IAM user created for this example:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "VisualEditor0",
            "Effect": "Allow",
            "Action": "sqs:SendMessage",
            "Resource": "arn:aws:sqs:us-east-1:12<redacted>:TestQueue"
        }
    ]
}
```

## Environment

I used Oracle Database 19.11 in my tests.
The database user that is going to call the AWS SQS API is `TC`.

## Wallet

First of all, let us load the AWS certificates into a wallet.
Creating a new wallet:

```
[oracle@rac1 ~]$ orapki wallet create -wallet /u01/app/oracle/wallet_sqs -pwd Oracle123 -auto_login
Oracle PKI Tool Release 19.0.0.0.0 - Production
Version 19.4.0.0.0
Copyright (c) 2004, 2021, Oracle and/or its affiliates. All rights reserved.

Operation is successfully completed.
```

Getting AWS certificates and loading them:

```
[oracle@rac1 ~]$ openssl s_client -showcerts -connect vpce-010f631ef8f1e24e7-8br55nv1.sqs.us-east-1.vpce.amazonaws.com:443 </dev/null 2>/dev/null | sed '/BEGIN/,/END/!d' | csplit -f aws -b '%d.pem' - /END/+1
2033
4798
[oracle@rac1 ~]$ orapki wallet add -wallet /u01/app/oracle/wallet_sqs -cert aws1.pem -trusted_cert -pwd Oracle123
Oracle PKI Tool Release 19.0.0.0.0 - Production
Version 19.4.0.0.0
Copyright (c) 2004, 2021, Oracle and/or its affiliates. All rights reserved.

Operation is successfully completed.
```

In order to call AWS SQS, I need to provide both `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`.
I certainly do not want to store them somewhere in the database.
Instead, I am going to add the credentials to the wallet:

```
[oracle@rac1 ~]$ mkstore -wrl /u01/app/oracle/wallet_sqs -createCredential aws_sqs AKI<AWS_ACCESS_KEY_ID redacted>
Oracle Secret Store Tool Release 19.0.0.0.0 - Production
Version 19.4.0.0.0
Copyright (c) 2004, 2021, Oracle and/or its affiliates. All rights reserved.

Your secret/Password is missing in the command line
Enter your secret/Password:
Re-enter your secret/Password:
Enter wallet password:
```

In the end, that is what my wallet looks like:

```
[oracle@rac1 ~]$ orapki wallet display -wallet /u01/app/oracle/wallet_sqs
Oracle PKI Tool Release 19.0.0.0.0 - Production
Version 19.4.0.0.0
Copyright (c) 2004, 2021, Oracle and/or its affiliates. All rights reserved.

Requested Certificates:
User Certificates:
Oracle Secret Store entries:
oracle.security.client.connect_string1
oracle.security.client.password1
oracle.security.client.username1
Trusted Certificates:
Subject:        CN=Amazon,OU=Server CA 1B,O=Amazon,C=US
[oracle@rac1 ~]$ mkstore -wrl /u01/app/oracle/wallet_sqs -listCredential
Oracle Secret Store Tool Release 19.0.0.0.0 - Production
Version 19.4.0.0.0
Copyright (c) 2004, 2021, Oracle and/or its affiliates. All rights reserved.

Enter wallet password:
List credential (index: connect_string username)
1: aws_sqs AKI<AWS_ACCESS_KEY_ID redacted>
```

## Configuring Network Access Control Lists (ACLs)

There are two privileges required for the calling user, which is called `TC`:

- The user must be able to access the VPC endpoint over network
- The user must be able to access the wallet file

The privileges assigned as follows:

```sql
SQL> exec dbms_network_acl_admin.append_host_ace( -
  host => '*.amazonaws.com', -
  ace  => xs$ace_type(privilege_list => xs$name_list('connect'), -
                      principal_name => 'tc', -
                      principal_type => xs_acl.ptype_db))

PL/SQL procedure successfully completed.

SQL> exec dbms_network_acl_admin.append_wallet_ace( -
  wallet_path => 'file:/u01/app/oracle/wallet_sqs', -
  ace         =>  xs$ace_type(privilege_list => xs$name_list('use_client_certificates', 'use_passwords'), -
                              principal_name => 'tc', -
                              principal_type => xs_acl.ptype_db))

PL/SQL procedure successfully completed.
```

## Making UTL\_HTTP Call

Finally, I am ready to make an AWS SQS API call:

```sql { .annotate }
SQL> declare
  2    req utl_http.req;
  3    resp utl_http.resp;
  4    value varchar2(32767);
  5    endpoint varchar2(32767) := 'https://vpce-010f631ef8f1e24e7-8br55nv1.sqs.us-east-1.vpce.amazonaws.com/12<redacted>/TestQueue/';
  6    parameters varchar2(32767) := 'Action=SendMessage&MessageBody=example';
  7    request_url varchar2(32767) := endpoint || '?' || parameters;
  8  begin
  9    utl_http.set_wallet('file:/u01/app/oracle/wallet_sqs');
 10    req := utl_http.begin_request(request_url);
 11    utl_http.set_header(req, 'x-amz-date', to_char(sysdate,'yyyymmdd"T"hh24miss"Z"'));-- (1)!
 12    utl_http.set_property(req, 'aws-region', 'us-east-1');-- (2)!
 13    utl_http.set_property(req, 'aws-service', 'sqs');-- (3)!
 14    utl_http.set_authentication_from_wallet(req, 'aws_sqs', 'AWS4-HMAC-SHA256');-- (4)!
 15    resp := utl_http.get_response(req);
 16    loop
 17      utl_http.read_line(resp, value, true);
 18      dbms_output.put_line(value);
 19    end loop;
 20  exception
 21    when utl_http.end_of_body
 22    then
 23      utl_http.end_request(req);
 24      utl_http.end_response(resp);
 25    when others
 26    then
 27      utl_http.end_request(req);
 28      raise;
 29  end;
 30  /
<?xml version="1.0"?><SendMessageResponse
xmlns="http://queue.amazonaws.com/doc/2012-11-05/"><SendMessageResult><MessageId
>d59b7cfb-4d9d-4675-bf1c-d64a9cb27929</MessageId><MD5OfMessageBody>1a79a4d60de67
18e8e5b326e338ae533</MD5OfMessageBody></SendMessageResult><ResponseMetadata><Req
uestId>675ba300-5f89-59d8-bf23-fbfcb7bd1fc9</RequestId></ResponseMetadata></Send
MessageResponse>

PL/SQL procedure successfully completed.
```

1. `x-amz-date` is one of the mandatory headers in [Signature Version 4](https://docs.aws.amazon.com/general/latest/gr/sigv4-date-handling.html)
2. The line is provided in accordance with the comments in `?/rdbms/admin/utlhttp.sql`
3. The line is provided in accordance with the comments in `?/rdbms/admin/utlhttp.sql`
4. There is one `UTL_HTTP` call but there are a lot of things are performed inside the procedure, such as: loading `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` from the wallet, constructing a Signature Version 4 request.
   The scheme `AWS4-HMAC-SHA256` is not documented yet in Oracle documentation, but it is mentioned in `?/rdbms/admin/utlhttp.sql`

Lines 11 to 14 have inline comments with additional information about them.

It can be seen that the invocation was successful and the message ID was returned as a result.

## Conclusion

As this blog post demonstrates, it is quite simple to call the AWS SQS API from PL/SQL using `UTL_HTTP`.
Regretfully, some of the parameters I used are not widely known, and there is little documentation for them.
It is my hope that Oracle improves its documentation one day.

It should be possible to call other AWS services using the same technique.
SQS was used since there was an original question about it on [SQL.RU](https://www.sql.ru/forum/1335452/aws-sqs-iz-pl-sql).
For instance, I remember I was calling S3 the other day using a similar script and a Signature Version 2 request, which corresponds to `schema=AWS` in the [UTL\_HTTP.SET\_AUTHENTICATION\_FROM\_WALLET](https://docs.oracle.com/en/database/oracle/oracle-database/19/arpls/UTL_HTTP.html#GUID-4A74C20F-9544-4123-AF8D-B5588503B6C4) call.
When it comes to S3, there is yet another way to utilize it that I blogged about in January: [Reading Amazon S3 Data from Oracle on non-OCI Environment](reading-amazon-s3-data-from-oracle-on-non-oci-environment.md).
