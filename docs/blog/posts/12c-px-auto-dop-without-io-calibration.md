---
categories:
  - Oracle
date:
  created: 2015-10-29T11:59:00
  updated: 2016-05-14T12:30:15
description: >-
  Oracle Database 11g allows to use parallel statement queuing without automatic degree of parallelism if parallel_degree_policy=auto but there is no I/O calibration statistics.
  Oracle Database 12c changed this behavior, so that it uses the default I/O calibration statistics, so that the 11g approach does not work anymore.
tags:
  - 12c
  - Initialization parameter
  - PX
---

# 12c: PX Auto DOP without IO Calibration

I have upgraded one of data warehouse databases from 11g to 12c this week and noticed changes in behaviour of the [PX Auto DOP](https://docs.oracle.com/database/121/VLDBG/GUID-29D801DE-54DB-40F3-BAAD-C1C5125C1B35.htm) feature.

<!-- more -->

According to the documentation of the `parallel_degree_policy` parameter [Oracle Database Reference 11g](https://docs.oracle.com/database/121/VLDBG/GUID-29D801DE-54DB-40F3-BAAD-C1C5125C1B35.htm), it can be set to the following values:

- `MANUAL` - Disables automatic degree of parallelism, statement queuing, and in-memory parallel execution. This reverts the behavior of parallel execution to what it was prior to Oracle Database 11g Release 2 (11.2). This is the default.
- `LIMITED` - Enables automatic degree of parallelism for some statements but statement queuing and in-memory Parallel Execution are disabled. Automatic degree of parallelism is only applied to those statements that access tables or indexes decorated explicitly with the DEFAULT degree of parallelism using the PARALLEL clause. Statements that do not access any tables or indexes decorated with the DEFAULT degree of parallelism will retain the MANUAL behavior.
- `AUTO` - Enables automatic degree of parallelism, statement queuing, and in-memory parallel execution.

In short:

- `MANUAL` - disables Auto DOP, parallel statement queuing, and in-memory parallel execution.
- `AUTO` - enables all of the above.

What if you need parallel statement queuing but do not want to use PX Auto DOP?
There is a MOS note suggesting to add a hint `STATEMENT_QUEUING` to your statements manually: [How to Achieve Parallel Statement Queuing for an SQL When PARALLEL\_DEGREE\_POLICY=MANUAL (Doc ID 1902069.1)](https://support.oracle.com/rs?type=doc&id=1902069.1)

There is a clever automatic way to achieve the same in Oracle Database 11g: [VLDB and Partitioning Guide 11g](https://docs.oracle.com/cd/E11882_01/server.112/e25523/parallel002.htm#sthref897)

> When `PARALLEL_DEGREE_POLICY` is set to `AUTO`, Oracle Database determines whether the statement should run in parallel based on the cost of the operations in the execution plan and the hardware characteristics.
> <br/>
> **The hardware characteristics include I/O calibration statistics so these statistics must be gathered** **otherwise Oracle Database does not use the automatic degree policy feature.**

So I simply set `PARALLEL_DEGREE_POLICY=AUTO` and did not gather I/O calibration statistics.
This prevents PX Auto DOP but parallel statement queuing and in-memory parallel execution still stays enabled.

Oracle Database 12c changes the things:
[VLDB and Partitioning Guide 12c](http://docs.oracle.com/database/121/VLDBG/GUID-29D801DE-54DB-40F3-BAAD-C1C5125C1B35.htm#d48132e147)

> When `PARALLEL_DEGREE_POLICY` is set to `AUTO`, Oracle Database determines whether the statement should run in parallel based on the cost of the operations in the execution plan and the hardware characteristics.
> <br/>
> **The hardware characteristics include I/O calibration statistics so these statistics should be gathered.**
> <br/>
> **If I/O calibration is not run to gather the required statistics, a default calibration value is used to calculate the cost of operations and the degree of parallelism.**

The difference is that now PX Auto DOP works even without I/O calibration statistics.
I am unaware of any announcements of this change in the New Features or VLDB and Partitioning guides.
Although I could agree that the configuration with `PARALLEL_DEGREE_POLICY=AUTO` without I/O calibration statistics looks a bit unusual, I would prefer that Oracle mentions such a behavior change at least in the "Changes in this release" section in the relevant book, i.e. [here](https://docs.oracle.com/database/121/VLDBG/GUID-C7A9BAD4-E4C9-4765-88C5-51AC7E97BAF1.htm#VLDBG14022).
