---
categories:
  - Oracle
date:
  created: 2021-01-28T03:45:00
description: >-
  Encountered an uncommon OPATCHAUTO-72043 on Java Cryptographic Extension (JCE).
  The error happened because the newer OPatch version was copied over the old version without removing the old version first.
tags:
  - 18c
  - OPatch
---

# OPATCHAUTO-72043 and JCE

I was applying Grid Infrastructure Jan 2021 Release Update (GI RU) 18.13.0.0.210119 to an 18c cluster the other day.
`opatchauto` failed with the error `OPATCHAUTO-72043`.

<!-- more -->

```
[root@rac1 ~]# /u01/app/18.3.0/grid/OPatch/opatchauto apply -analyze /u01/swtmp/32226219/ -oh /u01/app/18.3.0/grid/

OPatchauto session is initiated at Wed Jan 27 20:40:45 2021

System initialization log file is /u01/app/18.3.0/grid/cfgtoollogs/opatchautodb/systemconfig2021-01-27_08-40-48PM.log.

Session log file is /u01/app/18.3.0/grid/cfgtoollogs/opatchauto/opatchauto2021-01-27_08-40-51PM.log
The id for this session is 56VW
OPATCHAUTO-72043: Patch collection failed.
OPATCHAUTO-72043: Failed to create bundle patch object.
OPATCHAUTO-72043: Please verify the patch supplied.
OPatchAuto failed.

OPatchauto session completed at Wed Jan 27 20:40:53 2021
Time taken to complete the session 0 minute, 8 seconds

 opatchauto failed with error code 42
```

The session's log file did not point out to any specific problem:

??? "Session's log file log"
    ```
    2021-01-27 20:40:51,664 INFO  [1] com.oracle.glcm.patch.auto.OPatchAuto - OPatchAuto version: 13.9.4.5.0
    2021-01-27 20:40:51,666 INFO  [1] com.oracle.cie.common.util.reporting.CommonReporter - Reporting console output : Message{id='null', message='Session log file is /u01/app/18.3.0/grid/cfgtoollogs/opatchauto/opatchauto2021-01-27_08-40-51PM.log'}
    2021-01-27 20:40:51,733 INFO  [1] oracle.dbsysmodel.driver.sdk.productdriver.ClusterInformationLoader - crsType: SOFTWARE_INSTALLATION_ONLY
    2021-01-27 20:40:51,733 INFO  [1] oracle.dbsysmodel.driver.sdk.productdriver.ClusterInformationLoader - running: false
    2021-01-27 20:40:52,354 INFO  [1] com.oracle.glcm.patch.auto.OPatchAutoOptions - OPatchAutoOptions configured options:
    2021-01-27 20:40:52,354 INFO  [1] com.oracle.glcm.patch.auto.OPatchAutoOptions - Option: patch.location:patch-location Value:/u01/swtmp/32226219/
    2021-01-27 20:40:52,354 INFO  [1] com.oracle.glcm.patch.auto.OPatchAutoOptions - Option: home:-oh Value:/u01/app/18.3.0/grid/
    2021-01-27 20:40:52,354 INFO  [1] com.oracle.glcm.patch.auto.OPatchAutoOptions - Option: log:-log Value:/u01/app/18.3.0/grid/cfgtoollogs/opatchauto/opatchauto2021-01-27_08-40-51PM.log
    2021-01-27 20:40:52,355 INFO  [1] com.oracle.glcm.patch.auto.OPatchAutoOptions - Option: log_priority:-logLevel Value:INFO
    2021-01-27 20:40:52,355 INFO  [1] com.oracle.glcm.patch.auto.OPatchAutoOptions - Option: customLogDir:-customLogDir Value:/u01/app/18.3.0/grid/cfgtoollogs
    2021-01-27 20:40:52,355 INFO  [1] com.oracle.glcm.patch.auto.OPatchAutoOptions - Option: analyze:-analyze Value:true
    2021-01-27 20:40:52,355 INFO  [1] com.oracle.glcm.patch.auto.OPatchAutoOptions - Option: inventory.pointer.location:-invPtrLoc Value:/u01/app/18.3.0/grid//oraInst.loc
    2021-01-27 20:40:52,355 INFO  [1] com.oracle.glcm.patch.auto.OPatchAutoOptions - Option: host:-host Value:rac1.example.com
    2021-01-27 20:40:52,355 INFO  [1] com.oracle.glcm.patch.auto.OPatchAutoOptions - Option: patch.plan:-plan Value:crs-rolling
    2021-01-27 20:40:52,355 INFO  [1] com.oracle.glcm.patch.auto.OPatchAutoOptions - Option: format:-format Value:xml
    2021-01-27 20:40:52,355 INFO  [1] com.oracle.glcm.patch.auto.OPatchAutoOptions - Option: output:-output Value:console
    2021-01-27 20:40:52,355 INFO  [1] com.oracle.glcm.patch.auto.OPatchAutoOptions - Option: customconfigdir:-customConfigDir Value:/u01/app/18.3.0/grid/opatchautocfg/db
    2021-01-27 20:40:52,355 INFO  [1] com.oracle.glcm.patch.auto.OPatchAutoOptions - Option: nonrolling:-nonrolling Value:false
    2021-01-27 20:40:52,355 INFO  [1] com.oracle.glcm.patch.auto.OPatchAutoOptions - Option: session:-session Value:56VW
    2021-01-27 20:40:52,545 INFO  [1] com.oracle.glcm.patch.auto.OPatchAuto - The id for this session is 56VW
    2021-01-27 20:40:52,545 INFO  [1] com.oracle.cie.common.util.reporting.CommonReporter - Reporting console output : Message{id='null', message='The id for this session is 56VW'}
    2021-01-27 20:40:52,549 WARNING [1] com.oracle.glcm.patch.auto.credential.CredentialManager - Unable to locate credential for host rac1
    2021-01-27 20:40:52,584 INFO  [1] com.oracle.glcm.patch.auto.OPatchAutoHelper - Executing command [bash, -c, ORACLE_HOME=/u01/app/18.3.0/grid /u01/app/18.3.0/grid/bin/orabasehome]
    2021-01-27 20:40:52,602 INFO  [1] com.oracle.helper.util.HelperUtility - Orabasehome Output :
    /u01/app/18.3.0/grid

    2021-01-27 20:40:52,602 INFO  [1] com.oracle.helper.util.HelperUtility - Oracle Base Home for /u01/app/18.3.0/grid is /u01/app/18.3.0/grid
    2021-01-27 20:40:52,603 WARNING [1] com.oracle.glcm.patch.auto.credential.CredentialManager - Unable to locate credential for host rac1
    2021-01-27 20:40:52,616 INFO  [1] com.oracle.glcm.patch.auto.db.framework.core.patch.impl.PatchPackageFactoryImpl - Entering getPatchPackageFromDir, getting patch object for the given patch location /u01/swtmp/32226219
    2021-01-27 20:40:53,135 INFO  [1] com.oracle.glcm.patch.auto.db.framework.core.patch.OPatchBundlePatchValidatorAndGenerator - Bundle.xml does not exist
    2021-01-27 20:40:53,135 INFO  [1] com.oracle.glcm.patch.auto.db.framework.core.patch.OPatchSingletonPatchValidatorAndGenerator - inventory.xml found at /u01/swtmp/32226219/32216973/etc/config/inventory.xml which implies it is an OPatch Singleton patch
    2021-01-27 20:40:53,137 INFO  [1] com.oracle.glcm.patch.auto.db.framework.core.patch.PatchMetadaReader - Command for patch metadata::/u01/app/18.3.0/grid/perl/bin/perl  /u01/app/18.3.0/grid/OPatch/auto/database/bin/OPatchAutoBinary.pl query patchinfo -patch_location /u01/swtmp/32226219/32216973 -result /u01/app/18.3.0/grid/OPatch/auto/dbtmp/result.ser
    2021-01-27 20:40:53,741 INFO  [1] com.oracle.glcm.patch.auto.db.product.executor.GISystemCall - Is retry required=false
    2021-01-27 20:40:53,742 WARNING [1] com.oracle.glcm.patch.auto.db.integration.model.plan.PatchingProcessInitializer - Patch Collection failed:
    2021-01-27 20:40:53,743 INFO  [1] com.oracle.glcm.patch.auto.db.integration.model.productsupport.DBBaseProductSupport - Space available after session: 32874 MB
    2021-01-27 20:40:53,766 SEVERE [1] com.oracle.glcm.patch.auto.OPatchAuto - OPatchAuto failed.
    com.oracle.glcm.patch.auto.OPatchAutoException: OPATCHAUTO-72043: Patch collection failed.
    OPATCHAUTO-72043: Failed to create bundle patch object.
    OPATCHAUTO-72043: Please verify the patch supplied.
    	at com.oracle.glcm.patch.auto.db.integration.model.plan.PatchingProcessInitializer.initializePatchPackageBag(PatchingProcessInitializer.java:97)
    	at com.oracle.glcm.patch.auto.db.integration.model.plan.PatchingProcessInitializer.processInit(PatchingProcessInitializer.java:66)
    	at com.oracle.glcm.patch.auto.db.integration.model.productsupport.DBCommonSupport.initializePatchData(DBCommonSupport.java:126)
    	at com.oracle.glcm.patch.auto.db.integration.model.productsupport.DBBaseProductSupport.initializePatchData(DBBaseProductSupport.java:408)
    	at com.oracle.glcm.patch.auto.db.integration.model.productsupport.DBCommonSupport.loadTopology(DBCommonSupport.java:163)
    	at com.oracle.glcm.patch.auto.db.integration.model.productsupport.DBBaseProductSupport.loadTopology(DBBaseProductSupport.java:195)
    	at com.oracle.glcm.patch.auto.db.integration.model.productsupport.DBProductSupport.loadTopology(DBProductSupport.java:69)
    	at com.oracle.glcm.patch.auto.OPatchAuto.loadTopology(OPatchAuto.java:1732)
    	at com.oracle.glcm.patch.auto.OPatchAuto.prepareOrchestration(OPatchAuto.java:730)
    	at com.oracle.glcm.patch.auto.OPatchAuto.orchestrate(OPatchAuto.java:397)
    	at com.oracle.glcm.patch.auto.OPatchAuto.orchestrate(OPatchAuto.java:344)
    	at com.oracle.glcm.patch.auto.OPatchAuto.main(OPatchAuto.java:212)
    Caused by: com.oracle.glcm.patch.auto.db.integration.model.productsupport.patch.PatchCollectionException:
    	at com.oracle.glcm.patch.auto.db.framework.core.patch.OPatchSingletonPatchValidatorAndGenerator.generate(OPatchSingletonPatchValidatorAndGenerator.java:151)
    	at oracle.dbsysmodel.patchsdk.PatchFactory.getInstance(PatchFactory.java:246)
    	at com.oracle.glcm.patch.auto.db.framework.core.patch.impl.PatchPackageFactoryImpl.getPatchPackageFromDir(PatchPackageFactoryImpl.java:75)
    	at com.oracle.glcm.patch.auto.db.product.patch.BundlePatchObject.prcoessPatch(BundlePatchObject.java:131)
    	at com.oracle.glcm.patch.auto.db.product.patch.BundlePatchObject.createPatchBagForPatchLocation(BundlePatchObject.java:124)
    	at com.oracle.glcm.patch.auto.db.product.patch.BundlePatchObject.<init>(BundlePatchObject.java:77)
    	at com.oracle.glcm.patch.auto.db.integration.model.productsupport.patch.PatchInformationInitializer.createPatch(PatchInformationInitializer.java:43)
    	at com.oracle.glcm.patch.auto.db.integration.model.plan.PatchingProcessInitializer.initializePatchPackageBag(PatchingProcessInitializer.java:80)
    	... 11 more
    2021-01-27 20:40:53,767 INFO  [1] com.oracle.cie.common.util.reporting.CommonReporter - Reporting console output : Message{id='null', message='OPATCHAUTO-72043: Patch collection failed.
    OPATCHAUTO-72043: Failed to create bundle patch object.
    OPATCHAUTO-72043: Please verify the patch supplied.'}
    2021-01-27 20:40:53,767 INFO  [1] com.oracle.cie.common.util.reporting.CommonReporter - Reporting console output : Message{id='null', message='OPatchAuto failed.'}
    ```

There are several common scenarios when I see such errors:

- Wrong permissions on patch files
- A wrong folder passed to `opatchauto`
- Wrong `opatch` version

None of these was the case:

```
[grid@rac1 ~]$ /u01/app/18.3.0/grid/OPatch/opatch version
OPatch Version: 12.2.0.1.23

OPatch succeeded.
```

After checking the usual suspects, I had to enable logging:

```
[root@rac1 ~]# /u01/app/18.3.0/grid/OPatch/opatchauto apply -analyze /u01/swtmp/32226219/ -logLevel FINEST -oh /u01/app/18.3.0/grid/

OPatchauto session is initiated at Wed Jan 27 20:52:04 2021

System initialization log file is /u01/app/18.3.0/grid/cfgtoollogs/opatchautodb/systemconfig2021-01-27_08-52-07PM.log.

Session log file is /u01/app/18.3.0/grid/cfgtoollogs/opatchauto/opatchauto2021-01-27_08-52-10PM.log
The id for this session is 7NBB
OPATCHAUTO-72043: Patch collection failed.
OPATCHAUTO-72043: Failed to create bundle patch object.
OPATCHAUTO-72043: Please verify the patch supplied.
OPatchAuto failed.

OPatchauto session completed at Wed Jan 27 20:52:12 2021
Time taken to complete the session 0 minute, 8 seconds

 opatchauto failed with error code 42
```

This time around I got something new:

``` hl_lines="130 152 172 175"
2021-01-27 20:52:10,508 FINEST [1] com.oracle.cie.common.util.reporting.Reporting - Adding reporter com.oracle.cie.common.util.reporting.console.ConsoleReporter@4445629
2021-01-27 20:52:10,510 INFO  [1] com.oracle.glcm.patch.auto.OPatchAuto - OPatchAuto version: 13.9.4.5.0
2021-01-27 20:52:10,511 INFO  [1] com.oracle.cie.common.util.reporting.CommonReporter - Reporting console output : Message{id='null', message='Session log file is /u01/app/18.3.0/grid/cfgtoollogs/opatchauto/opatchauto2021-01-27_08-52-10PM.log'}
2021-01-27 20:52:10,517 FINER [1] com.oracle.glcm.patch.auto.db.integration.model.productsupport.DBProductSupport -  ShardedDatabase set as false
2021-01-27 20:52:10,517 FINER [1] com.oracle.glcm.patch.auto.db.integration.model.productsupport.DBProductSupport -  DataGuard primary set as : null
2021-01-27 20:52:10,517 FINER [1] com.oracle.glcm.patch.auto.db.integration.model.productsupport.DBProductSupport -  ShardGroup set as : null
2021-01-27 20:52:10,517 FINER [1] com.oracle.glcm.patch.auto.db.integration.model.productsupport.DBProductSupport -  ShardSpace set as : null
2021-01-27 20:52:10,517 FINER [1] com.oracle.glcm.patch.auto.db.integration.model.productsupport.DBProductSupport -  productSupport initialize: com.oracle.glcm.patch.auto.db.integration.model.productsupport.DBBaseProductSupport@48fa0f47
2021-01-27 20:52:10,517 FINE  [1] com.oracle.glcm.patch.auto.db.integration.model.productsupport.topology.DBPatchingHelper - switchSession: false
2021-01-27 20:52:10,577 INFO  [1] oracle.dbsysmodel.driver.sdk.productdriver.ClusterInformationLoader - crsType: SOFTWARE_INSTALLATION_ONLY
2021-01-27 20:52:10,577 INFO  [1] oracle.dbsysmodel.driver.sdk.productdriver.ClusterInformationLoader - running: false
2021-01-27 20:52:10,577 FINER [1] oracle.dbsysmodel.driver.sdk.productdriver.ClusterInformationLoader - ENTRY
2021-01-27 20:52:10,577 FINE  [1] oracle.dbsysmodel.driver.sdk.productdriver.ClusterInformationLoader - CRS stack is down. Now getting crs version by OUI.
2021-01-27 20:52:10,660 FINEST [1] oracle.dbsysmodel.driver.sdk.productdriver.OUIDriver - Added Component:oracle.crs
2021-01-27 20:52:10,660 FINEST [1] oracle.dbsysmodel.driver.sdk.productdriver.OUIDriver - Added OUI Info to:OraGI18Home1
2021-01-27 20:52:10,660 FINER [1] oracle.dbsysmodel.driver.sdk.productdriver.OUIDriver - ENTRY
2021-01-27 20:52:10,660 FINEST [1] oracle.dbsysmodel.driver.sdk.productdriver.OUIDriver - Executing OPatch/opatch version for OracleHome at /u01/app/18.3.0/grid
2021-01-27 20:52:10,968 FINE  [1] oracle.dbsysmodel.driver.sdk.productdriver.OUIDriver - /u01/app/18.3.0/grid has OPatch Version 12.2.0.1.23
2021-01-27 20:52:10,968 FINER [1] oracle.dbsysmodel.driver.sdk.productdriver.OUIDriver - RETURN
2021-01-27 20:52:10,969 FINER [1] oracle.dbsysmodel.driver.sdk.productdriver.OUIDriver - ENTRY
2021-01-27 20:52:10,969 FINE  [1] oracle.dbsysmodel.driver.sdk.productdriver.OUIDriver - ORACLE_BASE for /u01/app/18.3.0/grid is /u01/app/grid
2021-01-27 20:52:10,969 FINER [1] oracle.dbsysmodel.driver.sdk.productdriver.OUIDriver - RETURN
2021-01-27 20:52:10,969 FINEST [1] oracle.dbsysmodel.driver.sdk.productdriver.OUIDriver - Found Local Home:/u01/app/18.3.0/grid
2021-01-27 20:52:10,969 CONFIG [1] oracle.dbsysmodel.driver.sdk.productdriver.ClusterInformationLoader - Found local home at /u01/app/18.3.0/grid
2021-01-27 20:52:11,108 FINE  [1] com.oracle.glcm.patch.auto.db.integration.model.productsupport.topology.DBPatchingHelper - switchSession: false
2021-01-27 20:52:11,108 FINE  [1] com.oracle.glcm.patch.auto.db.integration.model.productsupport.topology.DBPatchingHelper - isSingleSession: false
2021-01-27 20:52:11,108 FINE  [1] com.oracle.glcm.patch.auto.db.integration.model.productsupport.topology.DBPatchingHelper - prepareSession: false
2021-01-27 20:52:11,108 FINE  [1] com.oracle.glcm.patch.auto.db.integration.model.productsupport.topology.DBPatchingHelper - switchSession: false
2021-01-27 20:52:11,108 FINE  [1] com.oracle.glcm.patch.auto.db.integration.model.productsupport.topology.DBPatchingHelper - oopEnabled: false
2021-01-27 20:52:11,112 FINE  [1] com.oracle.glcm.patch.auto.db.integration.model.productsupport.topology.CRSTopologyBuilder - SIDBonly is set to false
2021-01-27 20:52:11,113 FINE  [1] com.oracle.glcm.patch.auto.db.integration.model.productsupport.topology.DBPatchingHelper - switchSession: false
2021-01-27 20:52:11,142 FINEST [1] com.oracle.glcm.patch.auto.db.framework.sdk.patchplanner.PatchPlanEnv - Found property LocalHost
2021-01-27 20:52:11,142 FINEST [1] com.oracle.glcm.patch.auto.db.framework.sdk.patchplanner.PatchPlanEnv - Found property logDir
2021-01-27 20:52:11,142 FINEST [1] com.oracle.glcm.patch.auto.db.framework.sdk.patchplanner.PatchPlanEnv - Found property SessionID
2021-01-27 20:52:11,142 FINEST [1] com.oracle.glcm.patch.auto.db.framework.sdk.patchplanner.PatchPlanEnv - Found property OracleHome
2021-01-27 20:52:11,142 FINEST [1] com.oracle.glcm.patch.auto.db.framework.sdk.patchplanner.PatchPlanEnv - Found property LogFileLevel
2021-01-27 20:52:11,143 FINEST [1] com.oracle.glcm.patch.auto.db.framework.sdk.patchplanner.PatchPlanEnv - Found property ConsoleLogLevel
2021-01-27 20:52:11,143 FINEST [1] com.oracle.glcm.patch.auto.db.framework.sdk.patchplanner.PatchPlanEnv - Found property OPlanLocation
2021-01-27 20:52:11,143 FINEST [1] com.oracle.glcm.patch.auto.db.framework.sdk.patchplanner.PatchPlanEnv - Found property ConfigXML
2021-01-27 20:52:11,143 FINEST [1] com.oracle.glcm.patch.auto.db.framework.sdk.patchplanner.PatchPlanEnv - Found property invPtrLoc
2021-01-27 20:52:11,143 FINEST [1] com.oracle.glcm.patch.auto.db.framework.sdk.patchplanner.PatchPlanEnv - Found property UserInvokingOplan
2021-01-27 20:52:11,143 FINEST [1] com.oracle.glcm.patch.auto.db.framework.sdk.patchplanner.PatchPlanEnv - Found property RootUser
2021-01-27 20:52:11,143 FINEST [1] com.oracle.glcm.patch.auto.db.framework.sdk.patchplanner.PatchPlanEnv - Found property TmpFilesDir
2021-01-27 20:52:11,143 FINEST [1] com.oracle.glcm.patch.auto.db.framework.sdk.patchplanner.PatchPlanEnv - Found property ExecutionMode
2021-01-27 20:52:11,144 FINEST [1] com.oracle.glcm.patch.auto.db.framework.sdk.patchplanner.PatchPlanEnv - Found property AdminServerURL
2021-01-27 20:52:11,144 FINEST [1] com.oracle.glcm.patch.auto.db.framework.sdk.patchplanner.PatchPlanEnv - Found property AdminServerUser
2021-01-27 20:52:11,144 FINEST [1] com.oracle.glcm.patch.auto.db.framework.sdk.patchplanner.PatchPlanEnv - Found property AdminServerPassword
2021-01-27 20:52:11,144 FINEST [1] com.oracle.glcm.patch.auto.db.framework.sdk.patchplanner.PatchPlanEnv - Found property BundlePatchLocation
2021-01-27 20:52:11,145 FINEST [1] com.oracle.glcm.patch.auto.db.framework.sdk.patchplanner.PatchPlanEnv - Found property RACPatchLocations
2021-01-27 20:52:11,145 FINEST [1] com.oracle.glcm.patch.auto.db.framework.sdk.patchplanner.PatchPlanEnv - Found property GIPatchLocations
2021-01-27 20:52:11,145 FINEST [1] com.oracle.glcm.patch.auto.db.framework.sdk.patchplanner.PatchPlanEnv - Found property AllPatchLocations
2021-01-27 20:52:11,145 FINEST [1] com.oracle.glcm.patch.auto.db.framework.sdk.patchplanner.PatchPlanEnv - Found property PatchIDs
2021-01-27 20:52:11,145 FINEST [1] com.oracle.glcm.patch.auto.db.framework.sdk.patchplanner.PatchPlanEnv - Found property Operation
2021-01-27 20:52:11,145 FINEST [1] com.oracle.glcm.patch.auto.db.framework.sdk.patchplanner.PatchPlanEnv - Found property SkipConfigValidation
2021-01-27 20:52:11,145 FINEST [1] com.oracle.glcm.patch.auto.db.framework.sdk.patchplanner.PatchPlanEnv - Found property ProductFamily
2021-01-27 20:52:11,145 FINEST [1] com.oracle.glcm.patch.auto.db.framework.sdk.patchplanner.PatchPlanEnv - Found property NodeNumberPerReadme
2021-01-27 20:52:11,146 FINEST [1] com.oracle.glcm.patch.auto.db.framework.sdk.patchplanner.PatchPlanEnv - Found property MoveConfigToOH
2021-01-27 20:52:11,146 FINEST [1] com.oracle.glcm.patch.auto.db.framework.sdk.patchplanner.PatchPlanEnv - Found property SelectivePatchingEnabled
2021-01-27 20:52:11,146 FINEST [1] com.oracle.glcm.patch.auto.db.framework.sdk.patchplanner.PatchPlanEnv - Found property ConfigurationSnapshot
2021-01-27 20:52:11,146 FINEST [1] com.oracle.glcm.patch.auto.db.framework.sdk.patchplanner.PatchPlanEnv - Found property MinimumOPatchVersion
2021-01-27 20:52:11,146 FINEST [1] com.oracle.glcm.patch.auto.db.framework.sdk.patchplanner.PatchPlanEnv - Found property IntgFactoryClass
2021-01-27 20:52:11,146 FINEST [1] com.oracle.glcm.patch.auto.db.framework.sdk.patchplanner.PatchPlanEnv - Found property customLogPath
2021-01-27 20:52:11,154 FINE  [1] com.oracle.glcm.patch.auto.db.integration.model.productsupport.topology.CRSTopologyBuilder - Creating config graph from instance
2021-01-27 20:52:11,179 FINE  [1] com.oracle.glcm.patch.auto.db.integration.model.productsupport.DBBaseProductSupport - Actions loaded...
2021-01-27 20:52:11,182 FINE  [1] com.oracle.glcm.patch.auto.db.integration.model.productsupport.SDBProductSupport - Actions loaded...
2021-01-27 20:52:11,208 FINE  [1] com.oracle.glcm.patch.auto.db.integration.model.productsupport.topology.DBPatchingHelper - isSingleSession: false
2021-01-27 20:52:11,208 FINE  [1] com.oracle.glcm.patch.auto.db.integration.model.productsupport.topology.DBPatchingHelper - prepareSession: false
2021-01-27 20:52:11,208 FINE  [1] com.oracle.glcm.patch.auto.db.integration.model.productsupport.topology.DBPatchingHelper - switchSession: false
2021-01-27 20:52:11,208 FINE  [1] com.oracle.glcm.patch.auto.db.integration.model.productsupport.topology.DBPatchingHelper - oopEnabled: false
2021-01-27 20:52:11,211 INFO  [1] com.oracle.glcm.patch.auto.OPatchAutoOptions - OPatchAutoOptions configured options:
2021-01-27 20:52:11,212 INFO  [1] com.oracle.glcm.patch.auto.OPatchAutoOptions - Option: patch.location:patch-location Value:/u01/swtmp/32226219/
2021-01-27 20:52:11,212 INFO  [1] com.oracle.glcm.patch.auto.OPatchAutoOptions - Option: home:-oh Value:/u01/app/18.3.0/grid/
2021-01-27 20:52:11,212 INFO  [1] com.oracle.glcm.patch.auto.OPatchAutoOptions - Option: log:-log Value:/u01/app/18.3.0/grid/cfgtoollogs/opatchauto/opatchauto2021-01-27_08-52-10PM.log
2021-01-27 20:52:11,212 INFO  [1] com.oracle.glcm.patch.auto.OPatchAutoOptions - Option: log_priority:-logLevel Value:FINEST
2021-01-27 20:52:11,212 INFO  [1] com.oracle.glcm.patch.auto.OPatchAutoOptions - Option: customLogDir:-customLogDir Value:/u01/app/18.3.0/grid/cfgtoollogs
2021-01-27 20:52:11,212 INFO  [1] com.oracle.glcm.patch.auto.OPatchAutoOptions - Option: analyze:-analyze Value:true
2021-01-27 20:52:11,212 INFO  [1] com.oracle.glcm.patch.auto.OPatchAutoOptions - Option: inventory.pointer.location:-invPtrLoc Value:/u01/app/18.3.0/grid//oraInst.loc
2021-01-27 20:52:11,212 INFO  [1] com.oracle.glcm.patch.auto.OPatchAutoOptions - Option: host:-host Value:rac1.example.com
2021-01-27 20:52:11,212 INFO  [1] com.oracle.glcm.patch.auto.OPatchAutoOptions - Option: patch.plan:-plan Value:crs-rolling
2021-01-27 20:52:11,213 INFO  [1] com.oracle.glcm.patch.auto.OPatchAutoOptions - Option: format:-format Value:xml
2021-01-27 20:52:11,213 INFO  [1] com.oracle.glcm.patch.auto.OPatchAutoOptions - Option: output:-output Value:console
2021-01-27 20:52:11,213 INFO  [1] com.oracle.glcm.patch.auto.OPatchAutoOptions - Option: customconfigdir:-customConfigDir Value:/u01/app/18.3.0/grid/opatchautocfg/db
2021-01-27 20:52:11,213 INFO  [1] com.oracle.glcm.patch.auto.OPatchAutoOptions - Option: nonrolling:-nonrolling Value:false
2021-01-27 20:52:11,213 INFO  [1] com.oracle.glcm.patch.auto.OPatchAutoOptions - Option: session:-session Value:7NBB
2021-01-27 20:52:11,215 FINE  [1] com.oracle.glcm.patch.auto.tracking.PatchTracking - Adding new execution with id 1 to patch tracking session 7NBB
2021-01-27 20:52:11,222 FINE  [1] com.oracle.glcm.patch.auto.tracking.PatchTracking - Saving patch tracking session to /u01/app/18.3.0/grid/opatchautocfg/db/sessioninfo/7NBB.json
2021-01-27 20:52:11,421 INFO  [1] com.oracle.glcm.patch.auto.OPatchAuto - The id for this session is 7NBB
2021-01-27 20:52:11,422 INFO  [1] com.oracle.cie.common.util.reporting.CommonReporter - Reporting console output : Message{id='null', message='The id for this session is 7NBB'}
2021-01-27 20:52:11,424 FINEST [1] com.oracle.glcm.patch.auto.db.integration.model.productsupport.topology.DBPatchingHelper - requestedHostName: rac1.example.com
2021-01-27 20:52:11,425 FINEST [1] com.oracle.glcm.patch.auto.db.integration.model.productsupport.topology.DBPatchingHelper - formattedHostName: rac1
2021-01-27 20:52:11,425 WARNING [1] com.oracle.glcm.patch.auto.credential.CredentialManager - Unable to locate credential for host rac1
2021-01-27 20:52:11,425 FINE  [1] com.oracle.glcm.patch.auto.db.integration.model.productsupport.topology.DBPatchingHelper - Permissions: 700
2021-01-27 20:52:11,428 FINE  [1] com.oracle.glcm.patch.auto.db.product.executor.GISystemCall - System Call command is: [/bin/su, root, -m, -c, chmod 700 /u01/app/18.3.0/grid/.patch_storage]
2021-01-27 20:52:11,448 FINEST [1] com.oracle.glcm.patch.auto.db.product.executor.GISystemCall - Output message:
2021-01-27 20:52:11,448 FINEST [1] com.oracle.glcm.patch.auto.db.product.executor.GISystemCall - Return code: 0
2021-01-27 20:52:11,448 FINEST [1] com.oracle.glcm.patch.auto.db.integration.model.plan.PatchingProcessInitializer - Operation type:apply
2021-01-27 20:52:11,453 FINER [1] com.oracle.glcm.patch.auto.db.framework.sdk.patchplanner.PatchPlanEnv - Unrecognized property "autoDeploymentSubType"
2021-01-27 20:52:11,460 INFO  [1] com.oracle.glcm.patch.auto.OPatchAutoHelper - Executing command [bash, -c, ORACLE_HOME=/u01/app/18.3.0/grid /u01/app/18.3.0/grid/bin/orabasehome]
2021-01-27 20:52:11,461 FINE  [1] com.oracle.glcm.patch.auto.OPatchAutoHelper - Executing command [bash, -c, ORACLE_HOME=/u01/app/18.3.0/grid /u01/app/18.3.0/grid/bin/orabasehome] in dir null with env null
2021-01-27 20:52:11,477 INFO  [1] com.oracle.helper.util.HelperUtility - Orabasehome Output :
/u01/app/18.3.0/grid

2021-01-27 20:52:11,477 INFO  [1] com.oracle.helper.util.HelperUtility - Oracle Base Home for /u01/app/18.3.0/grid is /u01/app/18.3.0/grid
2021-01-27 20:52:11,478 WARNING [1] com.oracle.glcm.patch.auto.credential.CredentialManager - Unable to locate credential for host rac1
2021-01-27 20:52:11,478 FINE  [1] com.oracle.glcm.patch.auto.db.framework.core.oplan.IOUtils - Change the permission of the file /u01/app/18.3.0/grid/cfgtoollogs/opatchautodbto 775
2021-01-27 20:52:11,478 FINE  [1] com.oracle.glcm.patch.auto.db.product.executor.GISystemCall - System Call command is: [/bin/su, grid, -m, -c, chmod 775 /u01/app/18.3.0/grid/cfgtoollogs/opatchautodb]
2021-01-27 20:52:11,492 FINEST [1] com.oracle.glcm.patch.auto.db.product.executor.GISystemCall - Output message:
2021-01-27 20:52:11,492 FINEST [1] com.oracle.glcm.patch.auto.db.product.executor.GISystemCall - Return code: 0
2021-01-27 20:52:11,494 INFO  [1] com.oracle.glcm.patch.auto.db.framework.core.patch.impl.PatchPackageFactoryImpl - Entering getPatchPackageFromDir, getting patch object for the given patch location /u01/swtmp/32226219
2021-01-27 20:52:11,495 FINE  [1] com.oracle.glcm.patch.auto.db.framework.core.patch.impl.PatchPackageFactoryImpl - Adding to the patch factory all supported PatchValidatorsAndGenerators.
2021-01-27 20:52:11,499 FINE  [1] com.oracle.glcm.patch.auto.db.framework.core.patch.impl.PatchPackageFactoryImpl - Adding PatchValidatorAndGenerator class com.oracle.glcm.patch.auto.db.framework.core.patch.OPatchBundlePatchValidatorAndGenerator
2021-01-27 20:52:11,499 FINEST [1] oracle.dbsysmodel.patchsdk.PatchFactory - ENTRY
2021-01-27 20:52:11,499 FINE  [1] com.oracle.glcm.patch.auto.db.framework.core.patch.impl.PatchPackageFactoryImpl - Adding PatchValidatorAndGenerator class com.oracle.glcm.patch.auto.db.framework.core.patch.OPatchSingletonPatchValidatorAndGenerator
2021-01-27 20:52:11,499 FINEST [1] oracle.dbsysmodel.patchsdk.PatchFactory - ENTRY
2021-01-27 20:52:11,499 FINE  [1] com.oracle.glcm.patch.auto.db.framework.core.patch.impl.PatchPackageFactoryImpl - Adding PatchValidatorAndGenerator class com.oracle.glcm.patch.auto.db.framework.core.patch.CompositePatchValidatorAndGenerator
2021-01-27 20:52:11,500 FINEST [1] oracle.dbsysmodel.patchsdk.PatchFactory - ENTRY
2021-01-27 20:52:11,500 FINE  [1] com.oracle.glcm.patch.auto.db.framework.core.patch.impl.PatchPackageFactoryImpl - Adding PatchValidatorAndGenerator class com.oracle.glcm.patch.auto.db.framework.core.patch.ExapatchPatchValidatorAndGenerator
2021-01-27 20:52:11,500 FINEST [1] oracle.dbsysmodel.patchsdk.PatchFactory - ENTRY
2021-01-27 20:52:11,500 FINE  [1] com.oracle.glcm.patch.auto.db.framework.core.patch.impl.PatchPackageFactoryImpl - Adding PatchValidatorAndGenerator class com.oracle.glcm.patch.auto.db.framework.core.patch.DefaultPatchValidatorAndGenerator
2021-01-27 20:52:11,500 FINEST [1] oracle.dbsysmodel.patchsdk.PatchFactory - ENTRY
2021-01-27 20:52:11,500 FINEST [1] oracle.dbsysmodel.patchsdk.PatchFactory - ENTRY
2021-01-27 20:52:11,500 FINEST [1] oracle.dbsysmodel.patchsdk.PatchFactory - patchLocation /u01/swtmp/32226219
2021-01-27 20:52:12,036 FINE  [1] oracle.dbsysmodel.patchsdk.PatchFactory - Patch represented by the given patch location /u01/swtmp/32226219 is an Engineered System Patch.
2021-01-27 20:52:12,078 FINE  [1] oracle.dbsysmodel.patchsdk.PatchFactory - Trying to create sub patch with the PatchValidatorAndGenerator com.oracle.glcm.patch.auto.db.framework.core.patch.OPatchBundlePatchValidatorAndGenerator
2021-01-27 20:52:12,078 INFO  [1] com.oracle.glcm.patch.auto.db.framework.core.patch.OPatchBundlePatchValidatorAndGenerator - Bundle.xml does not exist
2021-01-27 20:52:12,079 FINE  [1] oracle.dbsysmodel.patchsdk.PatchFactory - Trying to create sub patch with the PatchValidatorAndGenerator com.oracle.glcm.patch.auto.db.framework.core.patch.OPatchSingletonPatchValidatorAndGenerator
2021-01-27 20:52:12,079 INFO  [1] com.oracle.glcm.patch.auto.db.framework.core.patch.OPatchSingletonPatchValidatorAndGenerator - inventory.xml found at /u01/swtmp/32226219/32216973/etc/config/inventory.xml which implies it is an OPatch Singleton patch
2021-01-27 20:52:12,081 INFO  [1] com.oracle.glcm.patch.auto.db.framework.core.patch.PatchMetadaReader - Command for patch metadata::/u01/app/18.3.0/grid/perl/bin/perl  /u01/app/18.3.0/grid/OPatch/auto/database/bin/OPatchAutoBinary.pl query patchinfo -patch_location /u01/swtmp/32226219/32216973 -result /u01/app/18.3.0/grid/OPatch/auto/dbtmp/result.ser
2021-01-27 20:52:12,081 FINE  [1] com.oracle.glcm.patch.auto.db.product.executor.GISystemCall - System Call command is: [/bin/su, grid, -m, -c, /u01/app/18.3.0/grid/perl/bin/perl  /u01/app/18.3.0/grid/OPatch/auto/database/bin/OPatchAutoBinary.pl query patchinfo -patch_location /u01/swtmp/32226219/32216973 -result /u01/app/18.3.0/grid/OPatch/auto/dbtmp/result.ser]
2021-01-27 20:52:12,657 FINEST [1] com.oracle.glcm.patch.auto.db.product.executor.GISystemCall - Error message:Exception in thread "main" java.util.ServiceConfigurationError: java.nio.file.spi.FileSystemProvider: Provider org.apache.sshd.client.subsystem.sftp.fs.SftpFileSystemProvider could not be instantiated
	at java.util.ServiceLoader.fail(ServiceLoader.java:232)
	at java.util.ServiceLoader.access$100(ServiceLoader.java:185)
	at java.util.ServiceLoader$LazyIterator.nextService(ServiceLoader.java:384)
	at java.util.ServiceLoader$LazyIterator.next(ServiceLoader.java:404)
	at java.util.ServiceLoader$1.next(ServiceLoader.java:480)
	at java.nio.file.spi.FileSystemProvider.loadInstalledProviders(FileSystemProvider.java:119)
	at java.nio.file.spi.FileSystemProvider.access$000(FileSystemProvider.java:77)
	at java.nio.file.spi.FileSystemProvider$1.run(FileSystemProvider.java:169)
	at java.nio.file.spi.FileSystemProvider$1.run(FileSystemProvider.java:166)
	at java.security.AccessController.doPrivileged(Native Method)
	at java.nio.file.spi.FileSystemProvider.installedProviders(FileSystemProvider.java:166)
	at java.nio.file.FileSystems.newFileSystem(FileSystems.java:388)
	at oracle.opatch.wrappers.WrapperFactory.loadWrapperProvider(WrapperFactory.java:144)
	at oracle.opatch.wrappers.WrapperFactory.loadWrapperProvider(WrapperFactory.java:103)
	at oracle.opatch.wrappers.WrapperFactory.getNioServiceWrapper(WrapperFactory.java:71)
	at oracle.opatch.opatchutil.OUSession.phbasedir(OUSession.java:2594)
	at oracle.opatch.opatchsdk.OPatchPatch.getPatches(OPatchPatch.java:486)
	at oracle.opatch.opatchsdk.OPatchPatch.getPatchesNoSymbolResolve(OPatchPatch.java:456)
	at oracle.opatchauto.core.utility.operation.PatchMetadataQueryOperation.getPatchInfo(PatchMetadataQueryOperation.java:45)
	at oracle.opatchauto.core.utility.operation.PatchMetadataQueryOperation.execute(PatchMetadataQueryOperation.java:26)
	at oracle.opatchauto.core.OpatchAutoCoreUtility.main(OpatchAutoCoreUtility.java:41)
Caused by: java.lang.ExceptionInInitializerError
	at javax.crypto.JceSecurityManager.<clinit>(JceSecurityManager.java:65)
	at javax.crypto.Cipher.getConfiguredPermission(Cipher.java:2590)
	at javax.crypto.Cipher.getMaxAllowedKeyLength(Cipher.java:2614)
	at org.apache.sshd.common.cipher.Cipher.checkSupported(Cipher.java:80)
	at org.apache.sshd.common.cipher.BuiltinCiphers.<init>(BuiltinCiphers.java:104)
	at org.apache.sshd.common.cipher.BuiltinCiphers.<clinit>(BuiltinCiphers.java:55)
	at org.apache.sshd.common.BaseBuilder.<clinit>(BaseBuilder.java:70)
	at org.apache.sshd.client.SshClient.setUpDefaultClient(SshClient.java:778)
	at org.apache.sshd.client.subsystem.sftp.fs.SftpFileSystemProvider.<init>(SftpFileSystemProvider.java:170)
	at org.apache.sshd.client.subsystem.sftp.fs.SftpFileSystemProvider.<init>(SftpFileSystemProvider.java:161)
	at org.apache.sshd.client.subsystem.sftp.fs.SftpFileSystemProvider.<init>(SftpFileSystemProvider.java:157)
	at org.apache.sshd.client.subsystem.sftp.fs.SftpFileSystemProvider.<init>(SftpFileSystemProvider.java:144)
	at sun.reflect.NativeConstructorAccessorImpl.newInstance0(Native Method)
	at sun.reflect.NativeConstructorAccessorImpl.newInstance(NativeConstructorAccessorImpl.java:62)
	at sun.reflect.DelegatingConstructorAccessorImpl.newInstance(DelegatingConstructorAccessorImpl.java:45)
	at java.lang.reflect.Constructor.newInstance(Constructor.java:423)
	at java.lang.Class.newInstance(Class.java:442)
	at java.util.ServiceLoader$LazyIterator.nextService(ServiceLoader.java:380)
	... 18 more
Caused by: java.lang.SecurityException: Can not initialize cryptographic mechanism
	at javax.crypto.JceSecurity.<clinit>(JceSecurity.java:93)
	... 36 more
Caused by: java.lang.SecurityException: The jurisdiction policy files are not signed by the expected signer! (Policy files are specific per major JDK release.Ensure the correct version is installed.)
	at javax.crypto.JarVerifier.verifyPolicySigned(JarVerifier.java:336)
	at javax.crypto.JceSecurity.loadPolicies(JceSecurity.java:378)
	at javax.crypto.JceSecurity.setupJurisdictionPolicies(JceSecurity.java:323)
	at javax.crypto.JceSecurity.access$000(JceSecurity.java:50)
	at javax.crypto.JceSecurity$1.run(JceSecurity.java:85)
	at java.security.AccessController.doPrivileged(Native Method)
	at javax.crypto.JceSecurity.<clinit>(JceSecurity.java:82)
	... 36 more

2021-01-27 20:52:12,657 FINEST [1] com.oracle.glcm.patch.auto.db.product.executor.GISystemCall - Output message:
2021-01-27 20:52:12,657 FINEST [1] com.oracle.glcm.patch.auto.db.product.executor.GISystemCall - Return code: 1
2021-01-27 20:52:12,657 INFO  [1] com.oracle.glcm.patch.auto.db.product.executor.GISystemCall - Is retry required=false
2021-01-27 20:52:12,657 FINE  [1] com.oracle.glcm.patch.auto.db.framework.core.patch.PatchMetadaReader - Query output::
2021-01-27 20:52:12,657 FINE  [1] com.oracle.glcm.patch.auto.db.framework.core.patch.PatchMetadaReader - Query err::Exception in thread "main" java.util.ServiceConfigurationError: java.nio.file.spi.FileSystemProvider: Provider org.apache.sshd.client.subsystem.sftp.fs.SftpFileSystemProvider could not be instantiated
	at java.util.ServiceLoader.fail(ServiceLoader.java:232)
	at java.util.ServiceLoader.access$100(ServiceLoader.java:185)
	at java.util.ServiceLoader$LazyIterator.nextService(ServiceLoader.java:384)
	at java.util.ServiceLoader$LazyIterator.next(ServiceLoader.java:404)
	at java.util.ServiceLoader$1.next(ServiceLoader.java:480)
	at java.nio.file.spi.FileSystemProvider.loadInstalledProviders(FileSystemProvider.java:119)
	at java.nio.file.spi.FileSystemProvider.access$000(FileSystemProvider.java:77)
	at java.nio.file.spi.FileSystemProvider$1.run(FileSystemProvider.java:169)
	at java.nio.file.spi.FileSystemProvider$1.run(FileSystemProvider.java:166)
	at java.security.AccessController.doPrivileged(Native Method)
	at java.nio.file.spi.FileSystemProvider.installedProviders(FileSystemProvider.java:166)
	at java.nio.file.FileSystems.newFileSystem(FileSystems.java:388)
	at oracle.opatch.wrappers.WrapperFactory.loadWrapperProvider(WrapperFactory.java:144)
	at oracle.opatch.wrappers.WrapperFactory.loadWrapperProvider(WrapperFactory.java:103)
	at oracle.opatch.wrappers.WrapperFactory.getNioServiceWrapper(WrapperFactory.java:71)
	at oracle.opatch.opatchutil.OUSession.phbasedir(OUSession.java:2594)
	at oracle.opatch.opatchsdk.OPatchPatch.getPatches(OPatchPatch.java:486)
	at oracle.opatch.opatchsdk.OPatchPatch.getPatchesNoSymbolResolve(OPatchPatch.java:456)
	at oracle.opatchauto.core.utility.operation.PatchMetadataQueryOperation.getPatchInfo(PatchMetadataQueryOperation.java:45)
	at oracle.opatchauto.core.utility.operation.PatchMetadataQueryOperation.execute(PatchMetadataQueryOperation.java:26)
	at oracle.opatchauto.core.OpatchAutoCoreUtility.main(OpatchAutoCoreUtility.java:41)
Caused by: java.lang.ExceptionInInitializerError
	at javax.crypto.JceSecurityManager.<clinit>(JceSecurityManager.java:65)
	at javax.crypto.Cipher.getConfiguredPermission(Cipher.java:2590)
	at javax.crypto.Cipher.getMaxAllowedKeyLength(Cipher.java:2614)
	at org.apache.sshd.common.cipher.Cipher.checkSupported(Cipher.java:80)
	at org.apache.sshd.common.cipher.BuiltinCiphers.<init>(BuiltinCiphers.java:104)
	at org.apache.sshd.common.cipher.BuiltinCiphers.<clinit>(BuiltinCiphers.java:55)
	at org.apache.sshd.common.BaseBuilder.<clinit>(BaseBuilder.java:70)
	at org.apache.sshd.client.SshClient.setUpDefaultClient(SshClient.java:778)
	at org.apache.sshd.client.subsystem.sftp.fs.SftpFileSystemProvider.<init>(SftpFileSystemProvider.java:170)
	at org.apache.sshd.client.subsystem.sftp.fs.SftpFileSystemProvider.<init>(SftpFileSystemProvider.java:161)
	at org.apache.sshd.client.subsystem.sftp.fs.SftpFileSystemProvider.<init>(SftpFileSystemProvider.java:157)
	at org.apache.sshd.client.subsystem.sftp.fs.SftpFileSystemProvider.<init>(SftpFileSystemProvider.java:144)
	at sun.reflect.NativeConstructorAccessorImpl.newInstance0(Native Method)
	at sun.reflect.NativeConstructorAccessorImpl.newInstance(NativeConstructorAccessorImpl.java:62)
	at sun.reflect.DelegatingConstructorAccessorImpl.newInstance(DelegatingConstructorAccessorImpl.java:45)
	at java.lang.reflect.Constructor.newInstance(Constructor.java:423)
	at java.lang.Class.newInstance(Class.java:442)
	at java.util.ServiceLoader$LazyIterator.nextService(ServiceLoader.java:380)
	... 18 more
Caused by: java.lang.SecurityException: Can not initialize cryptographic mechanism
	at javax.crypto.JceSecurity.<clinit>(JceSecurity.java:93)
	... 36 more
Caused by: java.lang.SecurityException: The jurisdiction policy files are not signed by the expected signer! (Policy files are specific per major JDK release.Ensure the correct version is installed.)
	at javax.crypto.JarVerifier.verifyPolicySigned(JarVerifier.java:336)
	at javax.crypto.JceSecurity.loadPolicies(JceSecurity.java:378)
	at javax.crypto.JceSecurity.setupJurisdictionPolicies(JceSecurity.java:323)
	at javax.crypto.JceSecurity.access$000(JceSecurity.java:50)
	at javax.crypto.JceSecurity$1.run(JceSecurity.java:85)
	at java.security.AccessController.doPrivileged(Native Method)
	at javax.crypto.JceSecurity.<clinit>(JceSecurity.java:82)
	... 36 more

2021-01-27 20:52:12,658 FINE  [1] com.oracle.cie.common.util.ResourceBundleManager - The code () is null or not an integer.
2021-01-27 20:52:12,658 WARNING [1] com.oracle.glcm.patch.auto.db.integration.model.plan.PatchingProcessInitializer - Patch Collection failed:
2021-01-27 20:52:12,659 FINE  [1] com.oracle.glcm.patch.auto.db.product.GILogger - com.oracle.glcm.patch.auto.db.framework.core.patch.OPatchSingletonPatchValidatorAndGenerator.generate(OPatchSingletonPatchValidatorAndGenerator.java:151)
2021-01-27 20:52:12,659 FINE  [1] com.oracle.glcm.patch.auto.db.product.GILogger - oracle.dbsysmodel.patchsdk.PatchFactory.getInstance(PatchFactory.java:246)
2021-01-27 20:52:12,659 FINE  [1] com.oracle.glcm.patch.auto.db.product.GILogger - com.oracle.glcm.patch.auto.db.framework.core.patch.impl.PatchPackageFactoryImpl.getPatchPackageFromDir(PatchPackageFactoryImpl.java:75)
2021-01-27 20:52:12,659 FINE  [1] com.oracle.glcm.patch.auto.db.product.GILogger - com.oracle.glcm.patch.auto.db.product.patch.BundlePatchObject.prcoessPatch(BundlePatchObject.java:131)
2021-01-27 20:52:12,659 FINE  [1] com.oracle.glcm.patch.auto.db.product.GILogger - com.oracle.glcm.patch.auto.db.product.patch.BundlePatchObject.createPatchBagForPatchLocation(BundlePatchObject.java:124)
2021-01-27 20:52:12,659 FINE  [1] com.oracle.glcm.patch.auto.db.product.GILogger - com.oracle.glcm.patch.auto.db.product.patch.BundlePatchObject.<init>(BundlePatchObject.java:77)
2021-01-27 20:52:12,659 FINE  [1] com.oracle.glcm.patch.auto.db.product.GILogger - com.oracle.glcm.patch.auto.db.integration.model.productsupport.patch.PatchInformationInitializer.createPatch(PatchInformationInitializer.java:43)
2021-01-27 20:52:12,659 FINE  [1] com.oracle.glcm.patch.auto.db.product.GILogger - com.oracle.glcm.patch.auto.db.integration.model.plan.PatchingProcessInitializer.initializePatchPackageBag(PatchingProcessInitializer.java:80)
2021-01-27 20:52:12,659 FINE  [1] com.oracle.glcm.patch.auto.db.product.GILogger - com.oracle.glcm.patch.auto.db.integration.model.plan.PatchingProcessInitializer.processInit(PatchingProcessInitializer.java:66)
2021-01-27 20:52:12,659 FINE  [1] com.oracle.glcm.patch.auto.db.product.GILogger - com.oracle.glcm.patch.auto.db.integration.model.productsupport.DBCommonSupport.initializePatchData(DBCommonSupport.java:126)
2021-01-27 20:52:12,659 FINE  [1] com.oracle.glcm.patch.auto.db.product.GILogger - com.oracle.glcm.patch.auto.db.integration.model.productsupport.DBBaseProductSupport.initializePatchData(DBBaseProductSupport.java:408)
2021-01-27 20:52:12,660 FINE  [1] com.oracle.glcm.patch.auto.db.product.GILogger - com.oracle.glcm.patch.auto.db.integration.model.productsupport.DBCommonSupport.loadTopology(DBCommonSupport.java:163)
2021-01-27 20:52:12,660 FINE  [1] com.oracle.glcm.patch.auto.db.product.GILogger - com.oracle.glcm.patch.auto.db.integration.model.productsupport.DBBaseProductSupport.loadTopology(DBBaseProductSupport.java:195)
2021-01-27 20:52:12,660 FINE  [1] com.oracle.glcm.patch.auto.db.product.GILogger - com.oracle.glcm.patch.auto.db.integration.model.productsupport.DBProductSupport.loadTopology(DBProductSupport.java:69)
2021-01-27 20:52:12,660 FINE  [1] com.oracle.glcm.patch.auto.db.product.GILogger - com.oracle.glcm.patch.auto.OPatchAuto.loadTopology(OPatchAuto.java:1732)
2021-01-27 20:52:12,660 FINE  [1] com.oracle.glcm.patch.auto.db.product.GILogger - com.oracle.glcm.patch.auto.OPatchAuto.prepareOrchestration(OPatchAuto.java:730)
2021-01-27 20:52:12,660 FINE  [1] com.oracle.glcm.patch.auto.db.product.GILogger - com.oracle.glcm.patch.auto.OPatchAuto.orchestrate(OPatchAuto.java:397)
2021-01-27 20:52:12,660 FINE  [1] com.oracle.glcm.patch.auto.db.product.GILogger - com.oracle.glcm.patch.auto.OPatchAuto.orchestrate(OPatchAuto.java:344)
2021-01-27 20:52:12,660 FINE  [1] com.oracle.glcm.patch.auto.db.product.GILogger - com.oracle.glcm.patch.auto.OPatchAuto.main(OPatchAuto.java:212)
2021-01-27 20:52:12,660 FINE  [1] com.oracle.cie.common.util.ResourceBundleManager - The code (OPATCHAUTO-72043: Patch collection failed.
OPATCHAUTO-72043: Failed to create bundle patch object.
OPATCHAUTO-72043: Please verify the patch supplied.) is null or not an integer.
2021-01-27 20:52:12,660 INFO  [1] com.oracle.glcm.patch.auto.db.integration.model.productsupport.DBBaseProductSupport - Space available after session: 32877 MB
2021-01-27 20:52:12,662 FINE  [1] com.oracle.glcm.patch.auto.db.product.executor.GISystemCall - System Call command is: [/bin/su, root, -m, -c, cp /tmp/patchingsummary.xml /u01/app/18.3.0/grid/opatchautocfg/db/sessioninfo/]
2021-01-27 20:52:12,673 FINEST [1] com.oracle.glcm.patch.auto.db.product.executor.GISystemCall - Output message:
2021-01-27 20:52:12,673 FINEST [1] com.oracle.glcm.patch.auto.db.product.executor.GISystemCall - Return code: 0
2021-01-27 20:52:12,674 FINE  [1] com.oracle.glcm.patch.auto.db.framework.core.oplan.IOUtils - Change the permission of the file /u01/app/18.3.0/grid/opatchautocfg/db/sessioninfo/patchingsummary.xmlto 775
2021-01-27 20:52:12,674 FINE  [1] com.oracle.glcm.patch.auto.db.product.executor.GISystemCall - System Call command is: [/bin/su, root, -m, -c, chmod 775 /u01/app/18.3.0/grid/opatchautocfg/db/sessioninfo/patchingsummary.xml]
2021-01-27 20:52:12,683 FINEST [1] com.oracle.glcm.patch.auto.db.product.executor.GISystemCall - Output message:
2021-01-27 20:52:12,684 FINEST [1] com.oracle.glcm.patch.auto.db.product.executor.GISystemCall - Return code: 0
2021-01-27 20:52:12,684 SEVERE [1] com.oracle.glcm.patch.auto.OPatchAuto - OPatchAuto failed.
com.oracle.glcm.patch.auto.OPatchAutoException: OPATCHAUTO-72043: Patch collection failed.
OPATCHAUTO-72043: Failed to create bundle patch object.
OPATCHAUTO-72043: Please verify the patch supplied.
	at com.oracle.glcm.patch.auto.db.integration.model.plan.PatchingProcessInitializer.initializePatchPackageBag(PatchingProcessInitializer.java:97)
	at com.oracle.glcm.patch.auto.db.integration.model.plan.PatchingProcessInitializer.processInit(PatchingProcessInitializer.java:66)
	at com.oracle.glcm.patch.auto.db.integration.model.productsupport.DBCommonSupport.initializePatchData(DBCommonSupport.java:126)
	at com.oracle.glcm.patch.auto.db.integration.model.productsupport.DBBaseProductSupport.initializePatchData(DBBaseProductSupport.java:408)
	at com.oracle.glcm.patch.auto.db.integration.model.productsupport.DBCommonSupport.loadTopology(DBCommonSupport.java:163)
	at com.oracle.glcm.patch.auto.db.integration.model.productsupport.DBBaseProductSupport.loadTopology(DBBaseProductSupport.java:195)
	at com.oracle.glcm.patch.auto.db.integration.model.productsupport.DBProductSupport.loadTopology(DBProductSupport.java:69)
	at com.oracle.glcm.patch.auto.OPatchAuto.loadTopology(OPatchAuto.java:1732)
	at com.oracle.glcm.patch.auto.OPatchAuto.prepareOrchestration(OPatchAuto.java:730)
	at com.oracle.glcm.patch.auto.OPatchAuto.orchestrate(OPatchAuto.java:397)
	at com.oracle.glcm.patch.auto.OPatchAuto.orchestrate(OPatchAuto.java:344)
	at com.oracle.glcm.patch.auto.OPatchAuto.main(OPatchAuto.java:212)
Caused by: com.oracle.glcm.patch.auto.db.integration.model.productsupport.patch.PatchCollectionException:
	at com.oracle.glcm.patch.auto.db.framework.core.patch.OPatchSingletonPatchValidatorAndGenerator.generate(OPatchSingletonPatchValidatorAndGenerator.java:151)
	at oracle.dbsysmodel.patchsdk.PatchFactory.getInstance(PatchFactory.java:246)
	at com.oracle.glcm.patch.auto.db.framework.core.patch.impl.PatchPackageFactoryImpl.getPatchPackageFromDir(PatchPackageFactoryImpl.java:75)
	at com.oracle.glcm.patch.auto.db.product.patch.BundlePatchObject.prcoessPatch(BundlePatchObject.java:131)
	at com.oracle.glcm.patch.auto.db.product.patch.BundlePatchObject.createPatchBagForPatchLocation(BundlePatchObject.java:124)
	at com.oracle.glcm.patch.auto.db.product.patch.BundlePatchObject.<init>(BundlePatchObject.java:77)
	at com.oracle.glcm.patch.auto.db.integration.model.productsupport.patch.PatchInformationInitializer.createPatch(PatchInformationInitializer.java:43)
	at com.oracle.glcm.patch.auto.db.integration.model.plan.PatchingProcessInitializer.initializePatchPackageBag(PatchingProcessInitializer.java:80)
	... 11 more
2021-01-27 20:52:12,685 INFO  [1] com.oracle.cie.common.util.reporting.CommonReporter - Reporting console output : Message{id='null', message='OPATCHAUTO-72043: Patch collection failed.
OPATCHAUTO-72043: Failed to create bundle patch object.
OPATCHAUTO-72043: Please verify the patch supplied.'}
2021-01-27 20:52:12,685 INFO  [1] com.oracle.cie.common.util.reporting.CommonReporter - Reporting console output : Message{id='null', message='OPatchAuto failed.'}
```

The errors pointed out to Java: [Bug 31997805 - Exception In Thread "root thread" java.lang.exceptionininitializererror in 12.2 Database (Doc ID 31997805.8)](https://support.oracle.com/rs?type=doc&id=31997805.8).
To verify that hypothesis, I downloaded [Java Cryptography Extension (JCE) Unlimited Strength Jurisdiction Policy Files 8](https://www.oracle.com/java/technologies/javase-jce8-downloads.html).
I copied both `local_policy.jar` and `US_export_policy.jar` to `/u01/app/18.3.0/grid/OPatch/jre/lib/security`, and reran `opatchauto`.

Sure enough, the `analyze` command was successful:

```
[root@rac1 ~]# /u01/app/18.3.0/grid/OPatch/opatchauto apply -analyze /u01/swtmp/32226219/ -oh /u01/app/18.3.0/grid/
OPatchauto session is initiated at Wed Jan 27 21:02:05 2021

System initialization log file is /u01/app/18.3.0/grid/cfgtoollogs/opatchautodb/systemconfig2021-01-27_09-02-08PM.log.

Session log file is /u01/app/18.3.0/grid/cfgtoollogs/opatchauto/opatchauto2021-01-27_09-02-10PM.log
The id for this session is D2B1

Executing OPatch prereq operations to verify patch applicability on home /u01/app/18.3.0/grid
Patch applicability verified successfully on home /u01/app/18.3.0/grid


Executing patch validation checks on home /u01/app/18.3.0/grid
Patch validation checks successfully completed on home /u01/app/18.3.0/grid

OPatchAuto successful.

--------------------------------Summary--------------------------------

Analysis for applying patches has completed successfully:

Host:rac1
CRS Home:/u01/app/18.3.0/grid
Version:18.0.0.0.0


==Following patches were SUCCESSFULLY analyzed to be applied:

Patch: /u01/swtmp/32226219/32216973
Log: /u01/app/18.3.0/grid/cfgtoollogs/opatchauto/core/opatch/opatch2021-01-27_21-02-24PM_1.log

Patch: /u01/swtmp/32226219/32216944
Log: /u01/app/18.3.0/grid/cfgtoollogs/opatchauto/core/opatch/opatch2021-01-27_21-02-24PM_1.log

Patch: /u01/swtmp/32226219/28655963
Log: /u01/app/18.3.0/grid/cfgtoollogs/opatchauto/core/opatch/opatch2021-01-27_21-02-24PM_1.log

Patch: /u01/swtmp/32226219/32240606
Log: /u01/app/18.3.0/grid/cfgtoollogs/opatchauto/core/opatch/opatch2021-01-27_21-02-24PM_1.log

Patch: /u01/swtmp/32226219/32204699
Log: /u01/app/18.3.0/grid/cfgtoollogs/opatchauto/core/opatch/opatch2021-01-27_21-02-24PM_1.log



OPatchauto session completed at Wed Jan 27 21:02:38 2021
Time taken to complete the session 0 minute, 33 seconds
```

The policy files themselves should not be needed since Java 8 Update 161: [Unlimited cryptography enabled by default](https://www.oracle.com/java/technologies/javase/8u161-relnotes.html#JDK-8170157).
The Java version that comes with OPatch 12.2.0.1.23 is newer, so that it should contain the fix:

```
[grid@rac1 bin]$ /u01/app/18.3.0/grid/OPatch/jre/bin/java -version
java version "1.8.0_271"
Java(TM) SE Runtime Environment (build 1.8.0_271-b03)
Java HotSpot(TM) 64-Bit Server VM (build 25.271-b03, mixed mode)
```

I also checked with several 19c clusters that these policy files were not there.
How come if the OPatch version was the same?
Turns out that when the OPatch was updated, the proper update procedure was not followed: [How To Download And Install The Latest OPatch(6880880) Version (Doc ID 274526.1)](https://support.oracle.com/rs?type=doc&id=274526.1):

- Policy files are present in a vanilla 18c home:
  ```
  [grid@rac1 grid]$ unzip -l /u01/swtmp/LINUX.X64_180000_grid_home.zip | grep "OPatch/jre/lib/security/.*.jar"
       3026  06-04-2018 00:52   OPatch/jre/lib/security/US_export_policy.jar
       3527  06-04-2018 00:52   OPatch/jre/lib/security/local_policy.jar
  ```

- The old OPatch directory was not removed.
  Instead a newer OPatch version was copied over the existing OPatch folder.

- Since the old OPatch directory was not removed, the policy files were kept after the newer OPatch version was deployed

I just moved the existing OPatch folder and did a clean OPatch deployment:

```
[grid@rac1 grid]$ mv OPatch/ OPatch_$(date +%Y%m%d)/
[grid@rac1 grid]$ unzip /u01/swtmp/p6880880_190000_Linux-x86-64.zip
```

The apply analyze command ran without errors and I applied the release update later on:

```
[root@rac1 ~]# /u01/app/18.3.0/grid/OPatch/opatchauto apply -analyze /u01/swtmp/32226219/ -oh /u01/app/18.3.0/grid/

OPatchauto session is initiated at Wed Jan 27 21:12:01 2021

System initialization log file is /u01/app/18.3.0/grid/cfgtoollogs/opatchautodb/systemconfig2021-01-27_09-12-04PM.log.

Session log file is /u01/app/18.3.0/grid/cfgtoollogs/opatchauto/opatchauto2021-01-27_09-12-07PM.log
The id for this session is 3IKL

Executing OPatch prereq operations to verify patch applicability on home /u01/app/18.3.0/grid
Patch applicability verified successfully on home /u01/app/18.3.0/grid


Executing patch validation checks on home /u01/app/18.3.0/grid
Patch validation checks successfully completed on home /u01/app/18.3.0/grid

OPatchAuto successful.

--------------------------------Summary--------------------------------

Analysis for applying patches has completed successfully:

Host:rac1
CRS Home:/u01/app/18.3.0/grid
Version:18.0.0.0.0


==Following patches were SUCCESSFULLY analyzed to be applied:

Patch: /u01/swtmp/32226219/32216973
Log: /u01/app/18.3.0/grid/cfgtoollogs/opatchauto/core/opatch/opatch2021-01-27_21-12-21PM_1.log

Patch: /u01/swtmp/32226219/32216944
Log: /u01/app/18.3.0/grid/cfgtoollogs/opatchauto/core/opatch/opatch2021-01-27_21-12-21PM_1.log

Patch: /u01/swtmp/32226219/28655963
Log: /u01/app/18.3.0/grid/cfgtoollogs/opatchauto/core/opatch/opatch2021-01-27_21-12-21PM_1.log

Patch: /u01/swtmp/32226219/32240606
Log: /u01/app/18.3.0/grid/cfgtoollogs/opatchauto/core/opatch/opatch2021-01-27_21-12-21PM_1.log

Patch: /u01/swtmp/32226219/32204699
Log: /u01/app/18.3.0/grid/cfgtoollogs/opatchauto/core/opatch/opatch2021-01-27_21-12-21PM_1.log



OPatchauto session completed at Wed Jan 27 21:12:36 2021
Time taken to complete the session 0 minute, 35 seconds
```

It is crucial to follow Oracle instructions to the letter when it makes sense.
Otherwise, it can lead to such uncommon errors.
It is also disappointing that `opatchauto` did not give any clue what was going on with the default logging level.
Thankfully, the logging level can be easily changed.
It is a bit verbose but it usually does the job and gives enough information about the cause of an issue.