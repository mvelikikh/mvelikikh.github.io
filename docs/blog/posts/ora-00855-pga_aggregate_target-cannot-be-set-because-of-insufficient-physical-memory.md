---
categories:
  - Oracle
date:
  created: 2023-03-18T19:05:00
description: >-
  Researching the cause for ORA-00855, and explaining how the maximum PGA_AGGREGATE_TARGET is calculated for a given host.
tags:
  - 19c
  - Code symbol
  - Initialization parameter
  - OERR
---

# ORA-00855 PGA\_AGGREGATE\_TARGET cannot be set because of insufficient physical memory

I have been investigated a case with `ORA-00855` recently, and decided to share my findings about this error in this post.

<!-- more -->

Let us start by asking a practical question.
Given the following amount of host memory and `%target` parameters, what `PGA_AGGREGATE_TARGET` (PAT) can be set for this system?

```sql
SQL> sho parameter ga%target

NAME                                 TYPE        VALUE
------------------------------------ ----------- ------------------------------
pga_aggregate_target                 big integer 200M
sga_target                           big integer 16640M
SQL> !grep Mem /proc/meminfo
MemTotal:       32053636 kB
MemFree:         2063524 kB
MemAvailable:    5843840 kB
```

Oracle allows to set the value to more than `MemAvailable`:

```sql
SQL> alter system set pga_aggregate_target=5843841K;

System altered.
```

At the same time, an attempt to set the PAT value to 6GB fails with `ORA-855`:

```sql
SQL> alter system set pga_aggregate_target=6G;
alter system set pga_aggregate_target=6G
*
ERROR at line 1:
ORA-02097: parameter cannot be modified because specified value is invalid
ORA-00855: PGA_AGGREGATE_TARGET cannot be set because of insufficient physical memory.
```

with the following message written to the alert log:

```
pga_aggregate_target cannot be set to 6442450944 due to SGA memory requirement and the physical memory size.
```

The description of the error is self-explanatory:

```sql
SQL> !oerr ora 855
00855, 00000, "PGA_AGGREGATE_TARGET cannot be set because of insufficient physical memory."
// *Cause:  PGA_AGGREGATE_TARGET value was too high for the current system global area (SGA) size and amount of physical memory available.
// *Action: Reduce the SGA size or increase the physical memory size.
```

Which, however, doesn't explain what the maximum PAT value allowed for this system.
During my experiments, I found out that Oracle calls the `ksmc_physmem_pga_target` function internally that returns the maximum PAT value.
The function takes the total host memory as input, which in my case would be **32053636KB** (or **0x7a4661000** in hex).
We can use gdb to show the value:

```
(gdb) printf "0x%lx\n", (long) ksmc_physmem_pga_target(0x7a4661000)
0x1686120cc
```

Which is 6,046,163,148 bytes.
oradebug outputs just 4 last bytes and it is not reliable here (the same value is shown in the trace file):

```sql
SQL> oradebug call ksmc_physmem_pga_target 0x7a4661000
Function returned 686120CC
```

The trace file:

```
Oradebug command 'call ksmc_physmem_pga_target 0x7a4661000' console output:
Function returned 686120CC
```

Oracle developers must have used the `%x` format in oradebug:

```
(gdb) printf "0x%x\n", (long) ksmc_physmem_pga_target(0x7a4661000)
0x686120cc
```

The PAT value can be validated in SQL\*Plus:

```sql
SQL> alter system set pga_aggregate_target=6046163148;

System altered.
```

While setting the value to more than that is not allowed:

```sql
SQL> alter system set pga_aggregate_target=6046163149;
alter system set pga_aggregate_target=6046163149
*
ERROR at line 1:
ORA-02097: parameter cannot be modified because specified value is invalid
ORA-00855: PGA_AGGREGATE_TARGET cannot be set because of insufficient physical
memory.
```

The internal algorithm used by Oracle may change, but at the time of my experiments in 19.18 the maximum PGA value seems to be calculated as follows:

```
max PAT = (TotalMemory * _pga_limit_physmem_perc / 100 - SGA_TARGET) * 100 / _pga_limit_target_perc
```

Description:

- `max PAT`: `PGA_AGGREGATE_TARGET` max value

- `TotalMemory`: total host memory (`MemTotal` in `/proc/meminfo`)

- `_pga_limit_physmem_perc`: the parameter limiting total PGA and SGA (90% by default, in other words Oracle reserves 10% for OS and everything else):
  ```sql
  SQL> select indx, ksppdesc from x$ksppi where ksppinm='_pga_limit_physmem_perc';

        INDX KSPPDESC
  ---------- --------------------------------------------------------------------------------
         246 default percent of physical memory for pga_aggregate_limit and SGA

  SQL> select ksppstvl from x$ksppsv where indx=246;

  KSPPSTVL
  --------------------------------------------------------------------------------
  90
  ```

- `_pga_limit_target_perc`: the default percent of PAT for `pga_aggregate_limit` (200% by default):
  ```sql
  SQL> select indx, ksppdesc from x$ksppi where ksppinm='_pga_limit_target_perc';

        INDX KSPPDESC
  ---------- --------------------------------------------------------------------------------
         234 default percent of pga_aggregate_target for pga_aggregate_limit

  SQL> select ksppstvl from x$ksppsv where indx=234;

  KSPPSTVL
  --------------------------------------------------------------------------------
  200
  ```

Substituting the values from the sample system to the formula, we get the expected value we experimentally found previously:

```
max PAT = (32053636 * 1024 * 90 / 100 - 16640 * 1024 * 1024) * 100 / 200 = 6046163148.8
```

Please note that this formula applies when the value is set while the instance is up and running.
It is still possible to set a higher value in the spfile and bounce the instance.
It will work producing the following output in the alert log:

```
2023-03-18T13:20:50.763260+00:00
**********************************************************************
PGA_AGGREGATE_TARGET specified is high
Errors in file /u01/app/oracle/diag/rdbms/racdb/racdb1/trace/racdb1_ora_275709.trc  (incident=14402):
ORA-00700: soft internal error, arguments: [pga physmem limit], [6046163149], [6046163148], [], [], [], [], [], [], [], [], []
Incident details in: /u01/app/oracle/diag/rdbms/racdb/racdb1/incident/incdir_14402/racdb1_ora_275709_i14402.trc
```

Where the second argument of the `ORA-00700` error (**6046163149**) is the actual PAT value, the third argument (**6046163148**) is the max PAT value calculated by the formula above.
In such a scenario, it is not possible to set the PAT value to itself:

```sql
SQL> sho parameter pga

NAME                                 TYPE        VALUE
------------------------------------ ----------- ------------------------------
pga_aggregate_limit                  big integer 12092326298
pga_aggregate_target                 big integer 6046163149
SQL> alter system set pga_aggregate_target=6046163149;
alter system set pga_aggregate_target=6046163149
*
ERROR at line 1:
ORA-02097: parameter cannot be modified because specified value is invalid
ORA-00855: PGA_AGGREGATE_TARGET cannot be set because of insufficient physical
memory.
```
