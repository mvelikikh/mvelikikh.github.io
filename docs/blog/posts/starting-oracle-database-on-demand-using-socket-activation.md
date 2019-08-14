---
categories:
  - Oracle
date:
  created: 2019-08-15T00:40:00
description: >-
  A proof of concept implementation starting Oracle Database on demand using systemd socket activation.
tags:
  - 19c
  - OERR
  - OS
---

# Starting Oracle Database on Demand Using Socket Activation

I remember watching a video about [Amazon Aurora Serverless](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/aurora-serverless.how-it-works.html#aurora-serverless.how-it-works.pause-resume) where it was demonstrated that your database can be started on demand when the first connection comes.
Although it is not something that you might want for your 24x7 OLTP database, it can come in handy for Development environments that have the intermittent usage pattern.
I decided to write a blog post about how that can be done for an Oracle Database server working on a systemd-based Linux Operating System.

<!-- more -->

My setup uses systemd Socket Activation which you can read more about on [Lennart Poettering's website](http://0pointer.de/blog/projects/socket-activation.html).
The following link has been used as a basis for that setup: [systemd: on-demand start of services like postgresql and mysql that do not yet support socket-based activation](https://unix.stackexchange.com/questions/352495/systemd-on-demand-start-of-services-like-postgresql-and-mysql-that-do-not-yet-s).
I took Amazon Linux distribution for this demo with the following kernel: `4.14.123-111.109.amzn2.x86_64`, however, the setup steps should be the same for any other Red Hat based distributions.
The Oracle Database version is 19.3.

In a nutshell, we need to create several systemd units:

1. The socket unit:
   ```systemd title="/etc/systemd/system/proxy-to-oracle.socket"
   [Unit]
   Description="Socket for Oracle Socket Proxy"
   Documentation=https://www.freedesktop.org/software/systemd/man/systemd-socket-proxyd.html

   [Socket]
   ListenStream=0.0.0.0:1522

   [Install]
   WantedBy=sockets.target
   ```
   The socket listens on port 1522 which accepts client connections to the database. When a connection comes, it starts the following service if it's not already running:

1. The socket forwarder proxy:
   ```systemd title="/etc/systemd/system/proxy-to-oracle.service"
   [Unit]
   Description="Oracle Socket Proxy"
   Documentation=https://www.freedesktop.org/software/systemd/man/systemd-socket-proxyd.html
   Requires=dbora.service
   After=dbora.service

   [Service]
   User=nobody
   Group=nobody
   ExecStart=/lib/systemd/systemd-socket-proxyd ip-172-17-31-208.ec2.internal:1521
   Restart=on-failure
   PrivateTmp=true
   ```
   I am using [systemd-socket-proxyd](https://www.freedesktop.org/software/systemd/man/systemd-socket-proxyd.html) that proxies the connection to the host `ip-172-17-31-208.ec2.internal` on port 1521 - it's just the hostname/port of the server where the listener is running (I'm using the same machine to host all services).
   There are `After` and `Requires` dependencies on `dbora.service`, which manages the database and the listener.

1. systemd Oracle service:
   ```systemd title="/etc/systemd/system/dbora.service"
   [Unit]
   Description="The Oracle Database Service"
   After=syslog.target network.target

   [Service]
   LimitMEMLOCK=infinity
   LimitNOFILE=65535
   RemainAfterExit=yes
   User=oracle
   Group=dba
   ExecStart=/home/oracle/scripts/start_oracle.sh
   ExecStop=/u01/app/oracle/product/19/dbhome_1/bin/dbshut /u01/app/oracle/product/19/dbhome_1

   [Install]
   WantedBy=multi-user.target
   ```
   In the service above, I used the standard stop command and a slightly changed startup script:

1. Oracle startup script:
   ```bash title="start_oracle.sh"
   #!/bin/sh

   export ORACLE_SID=orcl
   ORAENV_ASK=NO . /usr/local/bin/oraenv -s
   sqlplus / as sysdba <<_EOF
   startup
   _EOF

   lsnrctl start

   sqlplus / as sysdba <<_EOF
   alter system register;
   _EOF
   ```
   I did not use the `dbstart` command as it starts the listener first before bringing up databases.
   I was getting `ORA-01109: database not open` errors with the standard `dbstart` script, so I resorted to my own version of the startup script.

The TNS-descriptor is below:

``` hl_lines="6"
pdb =
    (DESCRIPTION=
      (RETRY_COUNT=10)
      (RETRY_DELAY=10)
      (ADDRESS=
        (PROTOCOL=TCP)(HOST=ip-172-17-31-208.ec2.internal)(PORT=1522)
      )
      (CONNECT_DATA=
        (SERVICE_NAME=pdb)
      )
    )
```

It's worth mentioning that the port is set to 1522 - that is where the systemd proxy is listening on.
I use a non-standard client `sqlnet.ora` file that disables Out of Band Break (see more information about it: [What is DISABLE_OOB (Out Of Band Break)? (Doc ID 373475.1)](https://support.oracle.com/rs?type=doc&id=373475.1)):

``` title="sqlnet.ora"
DISABLE_OOB=ON
```

Without that, I kept getting the `ORA-12637: Packet receive failed` error.
I searched through SQL\*Net traces and finally found a clue that pointed out to that parameter disabling Out of Band Breaks.
Actually, I do not recall that I got that error when I configured a similar setup on Oracle Database 12.1 and Oracle Linux 6 last year.

I'm going to connect to the socket on port 1522; the `proxy-to-oracle.service` should start the `dbora.service` if it is not running, and proxy the connection to the listener.
There is a little helper script to test the database connection that writes some output to estimate how long it takes to establish the connection:

```bash title="test_db_conn.sh"
#!/bin/sh
export TNS_ADMIN="${HOME}/tns_admin"
echo "Started at: "$(date +"%F %T")

sqlplus -L tc/tc@pdb <<_EOF
select to_char(sysdate, 'yyyy-mm-dd hh24:mi:ss') current_date
  from dual;
_EOF

echo ""
echo "Finished at: "$(date +"%F %T")
```

The initial state of services is below - only the `proxy-to-oracle.socket` is running:

```
# systemctl status proxy-to-oracle.socket proxy-to-oracle.service dbora.service
● proxy-to-oracle.socket - "Socket for Oracle Socket Proxy"
   Loaded: loaded (/etc/systemd/system/proxy-to-oracle.socket; enabled; vendor preset: disabled)
   Active: active (listening) since Thu 2019-08-08 13:31:19 UTC; 20h ago
     Docs: https://www.freedesktop.org/software/systemd/man/systemd-socket-proxyd.html
   Listen: 0.0.0.0:1522 (Stream)

● proxy-to-oracle.service - "Oracle Socket Proxy"
   Loaded: loaded (/etc/systemd/system/proxy-to-oracle.service; static; vendor preset: disabled)
   Active: inactive (dead) since Fri 2019-08-09 10:25:21 UTC; 3min 15s ago
     Docs: https://www.freedesktop.org/software/systemd/man/systemd-socket-proxyd.html
  Process: 16042 ExecStart=/lib/systemd/systemd-socket-proxyd ip-172-17-31-208.ec2.internal:1521 (code=killed, signal=TERM)
 Main PID: 16042 (code=killed, signal=TERM)

● dbora.service - "The Oracle Database Service"
   Loaded: loaded (/etc/systemd/system/dbora.service; enabled; vendor preset: disabled)
   Active: inactive (dead) since Fri 2019-08-09 10:25:46 UTC; 2min 50s ago
  Process: 22234 ExecStop=/u01/app/oracle/product/19/dbhome_1/bin/dbshut /u01/app/oracle/product/19/dbhome_1 (code=exited, status=0/SUCCESS)
  Process: 16032 ExecStart=/home/oracle/scripts/start_oracle.sh (code=exited, status=0/SUCCESS)
 Main PID: 16032 (code=exited, status=0/SUCCESS)
```

Neither the instance nor the listener are running:

```
[oracle@ip-172-17-31-208 ~]$ pgrep -af 'pmon|tnslsnr'
[oracle@ip-172-17-31-208 ~]$
```

Now I am starting the script that tests the database connection:

``` hl_lines="2 19"
[oracle@ip-172-17-31-208 scripts]$ ./test_db_conn.sh
Started at: 2019-08-09 10:32:53

SQL*Plus: Release 19.0.0.0.0 - Production on Fri Aug 9 10:32:53 2019
Version 19.3.0.0.0

Copyright (c) 1982, 2019, Oracle.  All rights reserved.


Last Successful login time: Fri Aug 09 2019 09:27:45 +00:00

Connected to:
Oracle Database 19c Enterprise Edition Release 19.0.0.0.0 - Production
Version 19.3.0.0.0

SQL>   2
CURRENT_DATE
-------------------
2019-08-09 10:33:13

SQL> Disconnected from Oracle Database 19c Enterprise Edition Release 19.0.0.0.0 - Production
Version 19.3.0.0.0

Finished at: 2019-08-09 10:33:14
```

It takes less than 20 seconds to start the instance (the TNS descriptor used `RETRY_DELAY=10`, so that the client tries to establish a connection every 10 seconds).
