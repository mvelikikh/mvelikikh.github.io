---
categories:
  - Oracle
date:
  created: 2019-12-12T20:00:00
description: >-
  A practical demonstration of performing unattended Grid Infrastructure Out of Place patching using opatchauto and property files.
tags:
  - 19c
  - OPatch
---

# Patching Oracle Grid Infrastructure Standalone Environment Using opatchauto Out of Place (OOP) Patching

A practical demonstration of performing unattended Grid Infrastructure Out of Place patching using opatchauto and property files.

<!-- more -->

The MOS article [Grid Infrastructure Out of Place ( OOP ) Patching using opatchauto (Doc ID 2419319.1)](https://support.oracle.com/rs?type=doc&id=2419319.1) describes how to perform opatchauto Out of Place Patching of a Grid Infrastructure environment.
The article assumes that commands are to be entered interactively.
Although it is possible to automate the patching process using the Linux [expect](https://linux.die.net/man/1/expect) command, an alternative approach utilizing property files can be adapted to perform unattended patching.

## Initial setup

I have a Grid Infrastructure Oracle Home `/u01/app/oracle/product/19.4.0/grid` on a Linux server.
That is Grid Infrastructure Release Update 19.4.0.0.190716.
I would like to install [Grid Infrastructure Release Update 19.5.0.0.191015](https://support.oracle.com/epmos/faces/ui/patch/PatchDetail.jspx?parent=DOCUMENT&sourceId=756671.1&patchId=30116789) to a new location `/u01/app/oracle/product/19.5.0/grid`.
There are also a few 12.2 databases running on the same server.

I will not be using the 2 Step Method from the aforementioned MOS article, so that I will not be running the `prepare-clone` and `switch-clone` commands.
The patching will be performed by running a single command that can be easily scripted and used from any IT automation tool, such as [Ansible](https://www.ansible.com/).

## Configuring Oracle Home mapping file

Here is an excerpt from [the OPatch User's Guide](https://docs.oracle.com/cd/E91266_01/OPTCH/GUID-10EF5AF2-BB81-488B-8F5A-362C04E4E6BE.htm#OPTCH-GUID-73389F3A-BFDF-48EC-9642-322C16730EDC) describing how to provide original and cloned home details:

> To create a property file, add all the required original and cloned home details and save the file with the *.properties* extension.
> For example: clone.properties.
>
> Following is an example of the property file:
>
> ```
> /scratch/product/12.2/<original_home>=/scratch/product/12.2/<cloned_home>
> /scratch/product/db/12.2/<original_home>=/scratch/product/db/12.2/<cloned_home>
> ```
>
> Where,
>
> *&lt;original\_home&gt;* is the folder name of the original home.
>
> *&lt;cloned\_home&gt;* is the folder name of the clone home to which the original home would be cloned to.

Hence, I create a property file with the following contents:

``` title="clone.properties"
/u01/app/oracle/product/19.4.0/grid=/u01/app/oracle/product/19.5.0/grid
```

## Analyzing the patch applicability

``` hl_lines="18 40"
[root@emrep 30116789]# opatchauto apply -outofplace -phBaseDir /u01/app/oracle/stage/p30116789_190000_Linux-x86-64_gi_ru_19.5.0.0.191015 \
> -oh /u01/app/oracle/product/19.4.0/grid \
> -silent /u01/app/oracle/stage/p30116789_190000_Linux-x86-64_gi_ru_19.5.0.0.191015/30116789/clone.properties \
> -analyze

OPatchauto session is initiated at Thu Dec 12 12:09:32 2019

System initialization log file is /u01/app/oracle/product/19.4.0/grid/cfgtoollogs/opatchautodb/systemconfig2019-12-12_12-09-36PM.log.

Session log file is /u01/app/oracle/product/19.4.0/grid/cfgtoollogs/opatchauto/opatchauto2019-12-12_12-09-41PM.log
The id for this session is ATZ9

Executing OPatch prereq operations to verify patch applicability on home /u01/app/oracle/product/19.4.0/grid
Patch applicability verified successfully on home /u01/app/oracle/product/19.4.0/grid

OPatchAuto successful.

--------------------------------Summary--------------------------------
Out of place patching clone home(s) summary
____________________________________________
Host : emrep
Actual Home : /u01/app/oracle/product/19.4.0/grid
Version:19.0.0.0.0
Clone Home Path : /u01/app/oracle/product/19.5.0/grid


Analysis for applying patches has completed successfully:

Host:emrep
SIHA Home:/u01/app/oracle/product/19.4.0/grid
Version:19.0.0.0.0


==Following patches were SKIPPED:

Patch: /u01/app/oracle/stage/p30116789_190000_Linux-x86-64_gi_ru_19.5.0.0.191015/30116789/29401763
Reason: This patch is already been applied, so not going to apply again.


==Following patches were SUCCESSFULLY analyzed to be applied:

Patch: /u01/app/oracle/stage/p30116789_190000_Linux-x86-64_gi_ru_19.5.0.0.191015/30116789/30122149
Log: /u01/app/oracle/product/19.4.0/grid/cfgtoollogs/opatchauto/core/opatch/opatch2019-12-12_12-10-00PM_1.log

Patch: /u01/app/oracle/stage/p30116789_190000_Linux-x86-64_gi_ru_19.5.0.0.191015/30116789/30122167
Log: /u01/app/oracle/product/19.4.0/grid/cfgtoollogs/opatchauto/core/opatch/opatch2019-12-12_12-10-00PM_1.log

Patch: /u01/app/oracle/stage/p30116789_190000_Linux-x86-64_gi_ru_19.5.0.0.191015/30116789/30125133
Log: /u01/app/oracle/product/19.4.0/grid/cfgtoollogs/opatchauto/core/opatch/opatch2019-12-12_12-10-00PM_1.log



OPatchauto session completed at Thu Dec 12 12:10:14 2019
Time taken to complete the session 0 minute, 42 seconds
```

## Stopping Oracle Databases that use Oracle ASM

Since I would like to patch only the Grid Infrastructure Oracle Home, which implies its unavailability in my setup, I can stop all Oracle databases beforehand.
Otherwise, they will be shutting down with the abort option.
The following lines from the alert log confirm that the database was brought down using the abort option on one server where I was testing the Out of Place patching:

``` hl_lines="2"
Thu Dec 12 12:26:00 2019
Shutting down instance (abort) (OS id: 13679)
License high water mark = 97
Thu Dec 12 12:26:00 2019
USER (ospid: 13679): terminating the instance
Thu Dec 12 12:26:01 2019
Instance terminated by USER, pid = 13679
```

## Applying the Release Update

``` hl_lines="54 69 97"
[root@emrep 30116789]# opatchauto apply -outofplace -phBaseDir /u01/app/oracle/stage/p30116789_190000_Linux-x86-64_gi_ru_19.5.0.0.191015 \
> -oh /u01/app/oracle/product/19.4.0/grid \
> -silent /u01/app/oracle/stage/p30116789_190000_Linux-x86-64_gi_ru_19.5.0.0.191015/30116789/clone.properties

OPatchauto session is initiated at Thu Dec 12 12:12:57 2019

System initialization log file is /u01/app/oracle/product/19.4.0/grid/cfgtoollogs/opatchautodb/systemconfig2019-12-12_12-13-01PM.log.

Session log file is /u01/app/oracle/product/19.4.0/grid/cfgtoollogs/opatchauto/opatchauto2019-12-12_12-13-06PM.log
The id for this session is IMWY

Executing OPatch prereq operations to verify patch applicability on home /u01/app/oracle/product/19.4.0/grid
Patch applicability verified successfully on home /u01/app/oracle/product/19.4.0/grid


Copying the files from the existing oracle home /u01/app/oracle/product/19.4.0/grid to a new location. Please wait...
Clone of oracle home /u01/app/oracle/product/19.4.0/grid is /u01/app/oracle/product/19.5.0/grid on host emrep
Copying the files from the existing oracle home /u01/app/oracle/product/19.4.0/grid to a new location is successful.


Unlocking CRS clone home for home /u01/app/oracle/product/19.4.0/grid.
Prepatch operation log file location: /u01/app/oracle/crsdata/emrep/crsconfig/hapatch_2019-12-12_12-16-50AM.log
Unlocked CRS clone home successfully for home /u01/app/oracle/product/19.4.0/grid.


Creating clone for oracle home /u01/app/oracle/product/19.4.0/grid.
Clone operation successful for oracle home /u01/app/oracle/product/19.4.0/grid.


Performing post clone operation for oracle home /u01/app/oracle/product/19.4.0/grid.
Performing post clone operation was successful for oracle home /u01/app/oracle/product/19.5.0/grid.


Start applying binary patch on home /u01/app/oracle/product/19.5.0/grid
Binary patch applied successfully on home /u01/app/oracle/product/19.5.0/grid


Update nodelist in the inventory for oracle home /u01/app/oracle/product/19.5.0/grid.
Update nodelist in the inventory is completed for oracle home /u01/app/oracle/product/19.5.0/grid.


Starting CRS service on home /u01/app/oracle/product/19.5.0/grid
Postpatch operation log file location: /u01/app/oracle/crsdata/emrep/crsconfig/hapatch_2019-12-12_12-25-58AM.log
CRS service started successfully on home /u01/app/oracle/product/19.5.0/grid


Confirm that all resources have been started from home /u01/app/oracle/product/19.5.0/grid.
All resources have been started successfully from home /u01/app/oracle/product/19.5.0/grid.



OPatchAuto successful.

--------------------------------Summary--------------------------------

Patching is completed successfully. Please find the summary as follows:

Host:emrep
SIHA Home:/u01/app/oracle/product/19.4.0/grid
Version:19.0.0.0.0
Summary:

==Following patches were SKIPPED:

Patch: /u01/app/oracle/stage/p30116789_190000_Linux-x86-64_gi_ru_19.5.0.0.191015/30116789/29401763
Reason: This patch is already been applied, so not going to apply again.


==Following patches were SUCCESSFULLY applied:

Patch: /u01/app/oracle/stage/p30116789_190000_Linux-x86-64_gi_ru_19.5.0.0.191015/30116789/30122149
Log: /u01/app/oracle/product/19.5.0/grid/cfgtoollogs/opatchauto/core/opatch/opatch2019-12-12_12-18-01PM_1.log

Patch: /u01/app/oracle/stage/p30116789_190000_Linux-x86-64_gi_ru_19.5.0.0.191015/30116789/30122167
Log: /u01/app/oracle/product/19.5.0/grid/cfgtoollogs/opatchauto/core/opatch/opatch2019-12-12_12-18-01PM_1.log

Patch: /u01/app/oracle/stage/p30116789_190000_Linux-x86-64_gi_ru_19.5.0.0.191015/30116789/30125133
Log: /u01/app/oracle/product/19.5.0/grid/cfgtoollogs/opatchauto/core/opatch/opatch2019-12-12_12-18-01PM_1.log


Patching session reported following warning(s):
_________________________________________________

[Note]: Please verify the database is running from the desired Oracle home, if not then manually execute
 $ORACLE_HOME/bin/srvctl modify database command to fix the problem


Out of place patching clone home(s) summary
____________________________________________
Host : emrep
Actual Home : /u01/app/oracle/product/19.4.0/grid
Version:19.0.0.0.0
Clone Home Path : /u01/app/oracle/product/19.5.0/grid


OPatchauto session completed at Thu Dec 12 12:37:27 2019
Time taken to complete the session 24 minutes, 30 seconds
[root@emrep 30116789]#
```

Thus, it took just 24 minutes to perform the patching on that server; it is an AWS `t3.large` instance.
The time can be even shortened more by preparing the cloned Oracle Home in advance.
A rough estimate on the log above can be made that the patching time may be shortened twice using [the 2 Step Method](https://support.oracle.com/rs?type=doc&id=2419319.1).
