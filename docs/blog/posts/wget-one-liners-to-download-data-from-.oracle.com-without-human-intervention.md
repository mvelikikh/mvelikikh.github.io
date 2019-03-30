---
categories:
  - Linux
date:
  created: 2019-03-30T23:40:00
description: >-
  Sample command-line wget scripts to download data from *.oracle.com sites without human intervention.
tags:
  - OS
---

# `wget` one liners to download data from \*.oracle.com without human intervention

When the topic of downloading Oracle software comes up, there is a common misconception that it requires a human intervention to accept the license terms.

<!-- more -->

Here are `wget` commands that I use to download data from Oracle sites, such as [edelivery.oracle.com](https://edelivery.oracle.com), [download.oracle.com](https://download.oracle.com), and [support.oracle.com](https://support.oracle.com):

```bash
wget \
  --user "<oracleaccount>" \
  --ask-password \
  --load-cookies <(printf '.oracle.com\tTRUE\t/\tFALSE\t0\toraclelicense\taccept-securebackup-cookie') \
  "<https_downloadlink>"
```

Or its fully automatic version:

```bash
wget \
  --user "<oracleaccount>" \
  --password "<password>" \
  --load-cookies <(printf '.oracle.com\tTRUE\t/\tFALSE\t0\toraclelicense\taccept-securebackup-cookie') \
  "<https_downloadlink>"
```

It has been tested against all of those sites and works fine as of now.

A few examples are below.

[edelivery.oracle.com](https://edelivery.oracle.com):

```bash
wget \
  --user "<oracleaccount>" \
  --ask-password \
  --load-cookies <(printf '.oracle.com\tTRUE\t/\tFALSE\t0\toraclelicense\taccept-securebackup-cookie') \
  "https://edelivery.oracle.com/akam/otn/linux/oracle18c/xe/oracle-database-xe-18c-1.0-1.x86_64.rpm"
```

[download.oracle.com](https://download.oracle.com):

```bash
wget \
  --user "<oracleaccount>" \
  --ask-password \
  --load-cookies <(printf '.oracle.com\tTRUE\t/\tFALSE\t0\toraclelicense\taccept-securebackup-cookie') \
  "https://download.oracle.com/otn/linux/oracle18c/xe/oracle-database-xe-18c-1.0-1.x86_64.rpm"
```

[support.oracle.com](https://support.oracle.com) - this one does not require the cookie:

```bash
wget \
  --user "<oracleaccount" \
  --ask-password \
  "https://updates.oracle.com/Orion/Services/download/p6880880_180000_Linux-x86-64.zip?aru=22569537&patch_file=p6880880_180000_Linux-x86-64.zip"
```
