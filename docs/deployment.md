# Deployment of infra.git services

The infra.git repository contains services which tend to fall into three
different categories: single-homed cron services, multi-homed cron
services, and appengine apps. The deployment mechanisms for each of
these types of services are outlined here.

[TOC]

## Single-homed Cron

Many services are deployed as Buildbot jobs on the
[Infra Cron](https://build.chromium.org/p/chromium.infra.cron/builders)
Buildbot waterfall. These services all have the same basic form:

1. Check out infra.git and its dependencies
2. Invoke the desired service
3. Run the service in a tight loop until it fails too many times, or
   has run for (usually) 10 minutes.
4. Stop the service, finish up the buildbot build, and repeat.

This strategy has a few ramifications for deployment:

* Deployment is via a source checkout
* The source checkout is updated to the latest version every 10
  minutes
* Other data (such as credentials) must use a different deployment
  system

In order to combat tip-of-tree breakages, these services do not run from
ToT of the master branch. Instead, they operate in detached-HEAD mode,
checking out the remote ref origin/deployed before each run.

In order to update the code being run by gnumbd, gsubtreed, or other
similar services you have to push a new value to the origin/deployed
ref:

    git push origin master:deployed

You can also push specific hashes:

    git push origin deadb33fb4adecafdeadb33fb4ddecafdeadb33f:deployed

And for rollbacks, just make sure you pass the `--force` flag (this
should be rare):

    git push -f origin deadb33fb4adecafdeadb33fb4ddecafdeadb33f:deployed

## Multi-homed Cron

Some of our services (in particular monitoring services such as sysmon
and mastermon) are deployed across a wide variety of hosts.
These services are not deployed via source checkouts. Instead, they are
packaged by [CIPD](/appengine/chrome_infra_pacakges) (the Chrome Infra Package
Deployer). The CIPD packages are built for every green revision by the
continuous builders on the [Infra
Continuous](https://build.chromium.org/p/chromium.infra/console) Buildbot
waterfall. Selected versions of these packages (not the packages themselves) are
deployed to specific hosts by Puppet. For instructions on how to update the
version of the CIPD package for these services, see the documentation in the
Puppet repository.

## Appengine

There is no single procedure how to deploy appengine apps. Normally, each app
author deploys his/her app manually, using
[gae.py](../appengine/README.md#Managing-AppEngine-apps) tool.
