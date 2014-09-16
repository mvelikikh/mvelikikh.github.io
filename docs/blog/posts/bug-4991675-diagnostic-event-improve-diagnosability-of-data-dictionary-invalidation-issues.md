---
categories:
  - Oracle
date:
  created: 2014-09-16T10:35:00
  updated: 2016-05-14T12:30:51
description: How to use the _trace_kqlidp parameter to track dictionary invalidations
tags:
  - 11g
  - 12c
  - Initialization parameter
---

# Bug 4991675 - Diagnostic event improve diagnosability of data dictionary invalidation issues

In a recent MOS HOT Topics email I found a note about a new parameter to track dictionary invalidation issues: [Bug 4991675 - Diagnostic event improve diagnosability of data dictionary invalidation issues (Doc ID 4991675.8)](https://support.oracle.com/rs?type=doc&id=4991675.8)

<!-- more -->

Many DBAs faced with _sporadic_ invalidation issues in their work.
Finding a root cause for such issues is not always easy.
In many cases we investigate audit records, process redo logs with LogMiner and so on.
You are out of problem when there are no DDL in the database.
Unfortunately, such a goal is not always reachable.

In the patch readme you can find next notes:

> Note:Patch Post Install Steps:
> <br/>
> This fix enhances the `_trace_kqlidp` parameter therefore please set this
> <br/>
> parameter to true to enable this fix.

`_trace_kqlidp` was probably introduced in 11.1 but this patch enhances the parameter.
I wrote a simple test case that can be used to demonstrate the effect of the `_trace_kqlidp` parameter.

```sql
def tns_alias=orcl

conn /@&tns_alias.
drop user tc cascade;
grant connect to tc identified by tc;
grant alter session, create procedure, create table to tc;

conn tc/tc@&tns_alias.

create table t(x int) segment creation deferred;

create or replace procedure p
is
begin
  for t_rec in (
    select * from t)
  loop
    null;
  end loop;
end;
/

alter session set "_trace_kqlidp"=true;

select status from obj where object_name='P';
alter table t add y int;
select status from obj where object_name='P';
```

The last `ALTER TABLE` statement invalidates the procedure P.
With the parameter `_trace_kqlidp` set, I see in trace file on 11.2.0.3:

```
ksedsts()+1296<-kqlidp0()+12068<-atbdrv()+26728<-opiexe()+20544<-opiosq0()+5576<-kpooprx()+212<-kpoal8()+536<-opiodr()+1164<-ttcpip()+1104<-opitsk()+1664<-opiino()+924<-opiodr()+1164<-opidrv()+1032<-sou2o()+88<-opimai_real()+504<-ssthrdmain()+316<-main()+316
<-_start()+380Fine-grain delta dump for unit TC.T
- Change bit vector 0:
  -23, -16,
- Change bit vector 1:Empty
- Change bit vector 2:Empty
- Shift table:Empty
kqlidp0: 964375 (CURSOR TC.T) (Parent:    0) [ROOT]
kqlidp0:. 964376 (PROCEDURE TC.P) (Parent:964375) [ADDED TO QUEUE]
kqlidp0:. 964376 (PROCEDURE TC.P) (Parent:964375) [INVALIDATE]
```

On 12.1.0.2:

```sql hl_lines="1 2"
INVALIDATION: Current SQL follows
alter table t add y int
ksedsts()+392<-kqlidp0()+11984<-atbdrv()+6728<-opiexe()+22596<-opiosq0()+3928<-kpooprx()+196<-kpoal8()+656<-opiodr()+1100<-ttcpip()+972<-opitsk()+1820<-opiino()+920<-opiodr()+1100<-opidrv()+932<-sou2o()+112<-opimai_real()+756<-ssthrdmain()+456<-main()+320<-_start()+300
Fine-grain delta dump for unit TC.T
- Change bit vector 0:
  -23, -16,
- Change bit vector 1:Empty
- Change bit vector 2:Empty
- Shift table:Empty
kqlidp0: 91877 (CURSOR TC.T) (Parent:    0) [ROOT]
kqlidp0:. 91878 (PROCEDURE TC.P) (Parent:91877) [ADDED TO QUEUE]
kqlidp0:. 91878 (PROCEDURE TC.P) (Parent:91877) [INVALIDATE]
```

We can see that patch 4991675 probably adds highlighted lines.
"INVALIDATION" line helps in trace file identification.
"Current SQL" line simplify root cause analysis.

!!! tip "alert.log is also populated with "INVALIDATION" lines."

    ```
    Tue Sep 16 10:16:50 2014
    INVALIDATION performed by ospid=21919. Please see tracefile.
    ```
