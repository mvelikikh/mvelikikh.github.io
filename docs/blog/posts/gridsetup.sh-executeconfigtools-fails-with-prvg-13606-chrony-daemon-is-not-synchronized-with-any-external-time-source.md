---
categories:
  - Oracle
date:
  created: 2021-12-09T17:26:00
description: >-
  Encountered PRVG-13606 : chrony daemon is not synchronized with any external time source during gridSetup.sh -executeConfigTools.
  Found that the issue related to changes in chronyc source command output.
  Demonstrated how to resolve the issue.
tags:
  - Clusterware
  - OS
---

# gridSetup.sh executeConfigTools fails with PRVG-13606 : chrony daemon is not synchronized with any external time source

Encountered an error related to clock synchronization checks ran during Grid Infrastructure configuration.
This post demonstrates how the issue was analyzed and resolved.

<!-- more -->

## Analysis

The `gridSetup.sh -executeConfigTools` command failed with the following errors in the log:

```
/u01/app/19.3.0/grid/gridSetup.sh -executeConfigTools -responseFile /opt/rsp/gi_19.3_config.rsp -silent
...
INFO:  [Dec 8, 2021 8:20:51 AM] Verifying Clock Synchronization ...FAILED
INFO:  [Dec 8, 2021 8:20:51 AM] Skipping line: Verifying Clock Synchronization ...FAILED
INFO:  [Dec 8, 2021 8:20:51 AM]   Verifying Network Time Protocol (NTP) ...FAILED
INFO:  [Dec 8, 2021 8:20:51 AM] Skipping line:   Verifying Network Time Protocol (NTP) ...FAILED
INFO:  [Dec 8, 2021 8:20:51 AM]     Verifying chrony daemon is synchronized with at least one external time
INFO:  [Dec 8, 2021 8:20:51 AM] Skipping line:     Verifying chrony daemon is synchronized with at least one external time
INFO:  [Dec 8, 2021 8:20:51 AM]     source ...FAILED
INFO:  [Dec 8, 2021 8:20:51 AM] Skipping line:     source ...FAILED
INFO:  [Dec 8, 2021 8:20:51 AM]     rac2: PRVG-13606 : chrony daemon is not synchronized with any external time
INFO:  [Dec 8, 2021 8:20:51 AM] Skipping line:     rac2: PRVG-13606 : chrony daemon is not synchronized with any external time
INFO:  [Dec 8, 2021 8:20:51 AM]           source on node "rac2".
INFO:  [Dec 8, 2021 8:20:51 AM] Skipping line:           source on node "rac2".
INFO:  [Dec 8, 2021 8:20:51 AM] Skipping line:
INFO:  [Dec 8, 2021 8:20:51 AM]     rac1: PRVG-13606 : chrony daemon is not synchronized with any external time
INFO:  [Dec 8, 2021 8:20:51 AM] Skipping line:     rac1: PRVG-13606 : chrony daemon is not synchronized with any external time
INFO:  [Dec 8, 2021 8:20:51 AM]           source on node "rac1".
INFO:  [Dec 8, 2021 8:20:51 AM] Skipping line:           source on node "rac1".
```

It can be easily reproduced by running Cluster Verification Utility (CVU):

```
[grid@rac1 ~]$ cluvfy comp clocksync -n rac1 -verbose

Verifying Clock Synchronization ...
  Node Name                             Status
  ------------------------------------  ------------------------
  rac1                                  passed

  Node Name                             State
  ------------------------------------  ------------------------
  rac1                                  Observer

CTSS is in Observer state. Switching over to clock synchronization checks using NTP

  Verifying Network Time Protocol (NTP) ...
    Verifying '/etc/chrony.conf' ...
    Node Name                             File exists?
    ------------------------------------  ------------------------
    rac1                                  yes

    Verifying '/etc/chrony.conf' ...PASSED
    Verifying Daemon 'chronyd' ...
    Node Name                             Running?
    ------------------------------------  ------------------------
    rac1                                  yes

    Verifying Daemon 'chronyd' ...PASSED
    Verifying NTP daemon or service using UDP port 123 ...
    Node Name                             Port Open?
    ------------------------------------  ------------------------
    rac1                                  yes

    Verifying NTP daemon or service using UDP port 123 ...PASSED
    Verifying chrony daemon is synchronized with at least one external time source ...FAILED (PRVG-13606)
  Verifying Network Time Protocol (NTP) ...FAILED (PRVG-13606)
Verifying Clock Synchronization ...FAILED (PRVG-13606)

Verification of Clock Synchronization across the cluster nodes was unsuccessful on all the specified nodes.


Failures were encountered during execution of CVU verification request "Clock Synchronization across the cluster nodes".

Verifying Clock Synchronization ...FAILED
  Verifying Network Time Protocol (NTP) ...FAILED
    Verifying chrony daemon is synchronized with at least one external time
    source ...FAILED
    rac1: PRVG-13606 : chrony daemon is not synchronized with any external time
          source on node "rac1".


CVU operation performed:      Clock Synchronization across the cluster nodes
Date:                         Dec 9, 2021 10:56:45 AM
CVU home:                     /u01/app/19.3.0/grid/
User:                         grid
```

To get more details, the CVU trace could be enabled:

```
[grid@rac1 ~]$ rm -rf /tmp/cvutrace
[grid@rac1 ~]$ mkdir /tmp/cvutrace
[grid@rac1 ~]$ export CV_TRACELOC=/tmp/cvutrace
[grid@rac1 ~]$ export SRVM_TRACE=true
[grid@rac1 ~]$ export SRVM_TRACE_LEVEL=1
[grid@rac1 ~]$ cluvfy comp clocksync -n rac1 -verbose
```

This produces the following lines in the trace file `/tmp/cvutrace/cvutrace.log.0`:

```
[main] [ 2021-12-09 10:58:10.179 UTC ] [VerificationUtil.traceAndLogInternal:16755]  [TaskNTP.doChronyTimeSourceCheck:2465] status=SUCCESSFUL; vfyCode=0; output=MS Name/IP address         Stratum Poll Reach Last
Rx Last sample
===============================================================================
^* 169.254.169.123               3   7   377   128  +1141ns[+4603ns] +/-  501us

[main] [ 2021-12-09 10:58:10.179 UTC ] [TaskAnonymousProxy.<init>:119]  Defining proxy task with: 'chrony daemon is synchronized with at least one external time source'
nodeList: 'rac1'
from task: 'TaskNTP'
Called from: 'TaskNTP.performNTPChecks:889'
[main] [ 2021-12-09 10:58:10.179 UTC ] [ResultSet.overwriteResultSet:810]  Overwriting ResultSet, called from: TaskAnonymousProxy.performAnonymousTask:148
[main] [ 2021-12-09 10:58:10.179 UTC ] [CVUVariables.getCVUVariable:607]  variable name : MODE_API
[main] [ 2021-12-09 10:58:10.179 UTC ] [CVUVariables.getCVUVariable:643]  Variable found in the CVU and Command Line context
[main] [ 2021-12-09 10:58:10.179 UTC ] [CVUVariables.resolve:981]  ForcedLookUp not enabled for variable:MODE_API
[main] [ 2021-12-09 10:58:10.179 UTC ] [CVUVariables.secureVariableValueTrace:789]  getting CVUVariableConstant : VAR = MODE_API VAL = FALSE
[main] [ 2021-12-09 10:58:10.180 UTC ] [ResultSet.traceResultSet:1040]

ResultSet AFTER overwrite ===>
        Overall Status->VERIFICATION_FAILED

        Uploaded Overall Status->UNKNOWN

        HasNodeResults: true


        contents of resultTable

Dumping Result data.
  Status     : VERIFICATION_FAILED
  Name       : rac1
  Type       : Node
  Has Results: No
  Exp. value : null
  Act. value : null

  Errors  :
    PRVG-13606 : chrony daemon is not synchronized with any external time source on node "rac1".
```

The same configuration steps were completed successfully on Oracle Linux (OL) 8.4, so that I started looking for any changes.
It turns out that the `chronyc sources` output was changed.

- OL 8.4 with `chrony-3.5-2.0.1.el8.x86_64`:
  ``` hl_lines="2"
  [root@rac1 ~]# chronyc sources
  210 Number of sources = 1
  MS Name/IP address         Stratum Poll Reach LastRx Last sample
  ===============================================================================
  ^* 169.254.169.123               3   6   377    39  +4827ns[  +10us] +/-  560us
  ```

- OL 8.5 with `chrony-4.1-1.0.1.el8.x86_64`:
  ```
  [root@rac1 ~]# chronyc sources
  MS Name/IP address         Stratum Poll Reach LastRx Last sample
  ===============================================================================
  ^* 169.254.169.123               3   7   377    10   -590ns[+4002ns] +/-  494us
  ```

The number of sources line is absent in OL 8.5.
There are two workarounds that can be used.

## Workarounds

### Use ORA\_DISABLED\_CVU\_CHECKS

```
[grid@rac1 ~]$ ORA_DISABLED_CVU_CHECKS=TASKNTP cluvfy comp clocksync -n rac1 -verbose

Verifying Clock Synchronization ...
  Node Name                             Status
  ------------------------------------  ------------------------
  rac1                                  passed

  Node Name                             State
  ------------------------------------  ------------------------
  rac1                                  Observer
  Verifying Network Time Protocol (NTP) ...WARNING (PRVG-11640)
Verifying Clock Synchronization ...WARNING (PRVG-11640)

Verification of Clock Synchronization across the cluster nodes was successful.


Warnings were encountered during execution of CVU verification request "Clock Synchronization across the cluster nodes".

Verifying Clock Synchronization ...WARNING
  Verifying Network Time Protocol (NTP) ...WARNING
  rac1: PRVG-11640 : The check "Network Time Protocol (NTP)" was not performed
        as it is disabled


CVU operation performed:      Clock Synchronization across the cluster nodes
Date:                         Dec 9, 2021 11:03:41 AM
CVU home:                     /u01/app/19.3.0/grid/
User:                         grid
```

### Amend chronyc temporarily to produce the desired output

This is only to validate our hypothesis related to the cause of the validation error.

```
[root@rac1 ~]# mv /usr/bin/chronyc{,.orig}
[root@rac1 ~]# vi /usr/bin/chronyc
[root@rac1 ~]# chmod a+x /usr/bin/chronyc
[root@rac1 ~]# /usr/bin/chronyc sources
210 Number of sources = 1
MS Name/IP address         Stratum Poll Reach LastRx Last sample
===============================================================================
^* 169.254.169.123               3   8   377    21    -32us[-5361ns] +/-  578us
[root@rac1 ~]# cat /usr/bin/chronyc
#!/bin/bash
echo '210 Number of sources = 1'
/usr/bin/chronyc.orig "$@"
```

Then we can validate the change by running CVU:

```
[grid@rac1 ~]$ cluvfy comp clocksync -n rac1 -verbose

Verifying Clock Synchronization ...
  Node Name                             Status
  ------------------------------------  ------------------------
  rac1                                  passed

  Node Name                             State
  ------------------------------------  ------------------------
  rac1                                  Observer

CTSS is in Observer state. Switching over to clock synchronization checks using NTP

  Verifying Network Time Protocol (NTP) ...
    Verifying '/etc/chrony.conf' ...
    Node Name                             File exists?
    ------------------------------------  ------------------------
    rac1                                  yes

    Verifying '/etc/chrony.conf' ...PASSED
    Verifying Daemon 'chronyd' ...
    Node Name                             Running?
    ------------------------------------  ------------------------
    rac1                                  yes

    Verifying Daemon 'chronyd' ...PASSED
    Verifying NTP daemon or service using UDP port 123 ...
    Node Name                             Port Open?
    ------------------------------------  ------------------------
    rac1                                  yes

    Verifying NTP daemon or service using UDP port 123 ...PASSED
    Verifying chrony daemon is synchronized with at least one external time source ...PASSED
  Verifying Network Time Protocol (NTP) ...PASSED
Verifying Clock Synchronization ...PASSED

Verification of Clock Synchronization across the cluster nodes was successful.

CVU operation performed:      Clock Synchronization across the cluster nodes
Date:                         Dec 9, 2021 11:05:36 AM
CVU home:                     /u01/app/19.3.0/grid/
User:                         grid
```

## Conclusion

The requirement to have an external NTP server is questionable.
There can be hardware clocks which chrony can use, such as TimeSync PTP service on Azure.
This post demonstrates how to debug NTP issues during Grid Infrastructure installations and/or CVU checks.
There is one generic method provided to work around such issues by setting the `ORA_DISABLED_CVU_CHECKS` environment variable.
If the issue is caused by Oracle utilities expecting certain output, then we might as well tweak system programs temporarily to produce the desired output.