---
categories:
  - Oracle
date:
  created: 2019-06-13T02:19:00
description: >-
  Found that OSDBA and OSOPER groups were coming blank in the srvctl config database output.
  Investigated the issue decompiling several Java classes along the way, and found that it was due to missing permissions on the CRS resource.
  Once the permissions were added, the groups were returned properly.
tags:
  - 19c
  - OS
---

# srvctl config database OSDBA and OSOPER groups not defined

I have recently investigated why there are some databases in my environment which are shown with empty `OSDBA` or `OSOPER` groups.

<!-- more -->

``` hl_lines="15 16"
$ srvctl config database -d orcl
Database unique name: orcl
Database name: orcl
Oracle home: /u01/app/oracle/product/db_19
Oracle user: oracle
Spfile: +DATA/ORCL/PARAMETERFILE/spfile.270.1010270597
Password file:
Domain:
Start options: open
Stop options: immediate
Database role: PRIMARY
Management policy: AUTOMATIC
Disk Groups: DATA,FRA
Services:
OSDBA group:
OSOPER group:
Database instance: orcl
```

`srvctl` is a usual shell script that calls the following:

```
# JRE Executable and Class File Variables
JRE=${JREDIR}/bin/java
..skip..
# Run srvctl
${JRE} ${JRE_OPTIONS} -DORACLE_HOME=${ORACLE_HOME} -classpath ${CLASSPATH} ${SRVM_PROPERTY_DEFS} oracle.ops.opsctl.OPSCTLDriver "$@"
```

That is just a Java class call.
We call `oracle.ops.opsctl.OPSCTLDriver` passing command-line arguments.
`CLASSPATH` is defined as follows:

```
CLASSPATH=${NETCFGJAR}:${LDAPJAR}:${JREJAR}:${SRVMJAR}:${SRVMHASJAR}:${SRVMASMJAR}:\
${EONSJAR}:${SRVCTLJAR}:${GNSJAR}:${ANTLRJAR}:${CLSCEJAR}:${CHACONFIGJAR}:${JDBCJAR}:\
${MAILJAR}:${ACTIVATIONJAR}:${JWCCREDJAR}
```

Those jar-variables are set in the script so it is trivial to find out all classes that are used there.
I used to use JAD to decompile them but it appears to be not in vogue and not developed anymore.
Thankfully, there are a bunch of free sites that can be used as a replacement.
I personally have used [this one](http://www.javadecompilers.com/).

It is usually advised to identify the entry jar first by looking into the jar files so as to figure out where exactly `OPSCTLDriver` is coming from.
Not surprisingly, it is coming from `${SRVCTLJAR}` which is set to `${ORACLE_HOME}/srvm/jlib/srvctl.jara`.
`OPSCTLDriver` calls `oracle.ops.opsctl.ConfigAction` that does the following:

```java
for (Database db : dblist) {
..skip..
  if ((isUnixSystem) && (!isMgmtDB)) {
    groups = db.getGroups();
    dbaGrp = groups.get("OSDBA") == null ? "" : (String)groups.get("OSDBA");
    operGrp = groups.get("OSOPER") == null ? "" : (String)groups.get("OSOPER");
  }
```

Hence, the groups I am interested in are from the `Database` class which is set in the import section: `import oracle.cluster.database.Database;`.
That is just an interface from `srvm.jar`:

```java
public abstract interface Database
  extends SoftwareModule
{
```

The actual implementation is this: `oracle.cluster.impl.database.DatabaseImpl`.

Here are how those groups are determined:

```java hl_lines="16 17"
String oracleBin = getOracleHome() + File.separator + "bin";
      Trace.out("Creating OSDBAGRPUtil with path: " + oracleBin);
      OSDBAGRPUtil grpUtil = new OSDBAGRPUtil(oracleBin);
      Map<String, String> groups = grpUtil.getAdminGroups(version());


      ResourcePermissionsImpl perm = (ResourcePermissionsImpl)m_crsResource.getPermissions();
      String acl = perm.getAclString();
      Map<String, List<string>> aclMap = splitACL(acl);

      List<String> acl_groups = (List)aclMap.get(ResourceType.ACL.GROUP.toString());


      String dba = (String)groups.get("SYSDBA");
      String oper = (String)groups.get("SYSOPER");
      if ((!dba.isEmpty()) && (acl_groups.contains(dba.toLowerCase()))) {
        groupMap.put("OSDBA", dba);
      }
      if ((!oper.isEmpty()) && (acl_groups.contains(oper.toLowerCase()))) {
        groupMap.put("OSOPER", oper);
      }
      return groupMap;
```

Having applied the same technique, it is easy to find out that `OSDBAGRPUtil` calls `${ORACLE_HOME}/bin/osdbagrp` passing either `-d` or `-o` flags depending on what group we are interested in.

In my case, those commands returned `dba` and `oper` for `OSDBA` and `OSOPER` respectively:

```bash
$ osdbagrp -d
dba
$ osdbagrp -o
oper
```

Thus, this part of the if statement is true: `(!dba.isEmpty())` and the `dba` group is not set because of: `(acl_groups.contains(dba.toLowerCase()))`.
So that is something related to ACLs which is coming from `ResourcePermissionsImpl perm = (ResourcePermissionsImpl)m_crsResource.getPermissions();`.
Let us use [the crsctl getperm command](https://docs.oracle.com/database/121/CWADD/GUID-F7DBDD74-6D13-4471-9A92-C2577B04798B.htm#CWADD91543) passing the database resource to it:

```bash
$ crsctl getperm resource ora.orcl.db
Name: ora.orcl.db
owner:oracle:rwx,pgrp:asmdba:r-x,other::r--,group:oinstall:r-x,user:oracle:rwx
```

That looks promising - neither `dba` nor `oper` groups are set.
I ran the command below to set the `dba` group:

```bash
$ crsctl setperm resource ora.orcl.db -u group:dba:r-x
CRS-4995:  The command 'Setperm  resource' is invalid in crsctl. Use srvctl for this command.
$ crsctl setperm resource ora.orcl.db -u group:dba:r-x -unsupported
```

Well, that is an Oracle Restart environment, so that I added the `unsupported` flag.

Once it was done, the `OSDBA` group was properly coming back:

```bash hl_lines="15"
$ srvctl config database -d orcl
Database unique name: orcl
Database name: orcl
Oracle home: /u01/app/oracle/product/db_19
Oracle user: oracle
Spfile: +DATA/ORCL/PARAMETERFILE/spfile.270.1010270597
Password file:
Domain:
Start options: open
Stop options: immediate
Database role: PRIMARY
Management policy: AUTOMATIC
Disk Groups: DATA,FRA
Services:
OSDBA group: dba
OSOPER group:
Database instance: orcl
```
