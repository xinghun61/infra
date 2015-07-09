# Chrome Infra Configuration service (luci-config)

* Owner: nodir@
* Prod instance: luci-config.appspot.com

[TOC]

## Overview

* Stores a registry of projects (clients) and chrome infra services
* Gathers configuration files scattered across repositories and provides unified
  API to discover and read them.
* Validates config files

Non-chromium detailed documentation can be found on
[GitHub](https://github.com/luci/luci-py/tree/master/appengine/config_service).
This page explains specifics of chromium's instance.

## Project registry

Projects that want to use CQ or BuildBucket must be registered in
[projects.cfg](https://chrome-internal.googlesource.com/infradata/config/+/master/configs/luci-config/projects.cfg).

Send a CL or file a bug to nodir@ or sergiyb@.

## Import

Luci-config imports config files from
[Gitiles](https://code.google.com/p/gitiles/) every 10 min:

* Service configs are imported from
  [infradata/config repo](https://chrome-internal.googlesource.com/infradata/config/+/master/configs/)
* Project configs are imported from project repositories. They are either in
  the root of `infra/config` branch
  (example: [infra.git](https://chromium.googlesource.com/infra/infra/+/infra/config)) or
  `infra/project-config` dir of `master` branch (example:
  [chromium/src.git](https://chromium.googlesource.com/chromium/src/+/master/infra/project-config))
* Ref configs are typically imported from `infra/config` directory of a branch.

ConfigSet->Location mapping can be found by calling
[get_mapping API](https://luci-config.appspot.com/_ah/api/explorer#p/config/v1/config.get_mapping).

## Who uses it?

* CQ [reads cq.cfg files](https://luci-config.appspot.com/_ah/api/explorer#p/config/v1/config.get_ref_configs?path=cq.cfg),
  discovers projects and reads a list of builders to trigger
* [BuildBucket](https://cr-buildbucket.appspot.com)
  [reads cr-buildbucket.cfg](https://luci-config.appspot.com/_ah/api/explorer#p/config/v1/config.get_project_configs?path=cr-buildbucket.cfg),
  discovers and registers buckets.
* [CIA](https://chrome-infra-auth.appspot.com) reads
  [its configs](https://chrome-internal.googlesource.com/infradata/config/+/master/configs/chrome-infra-auth/)
  and updates its internal state.

## Validation

* luci-config validates
  [its owns configs](https://chrome-internal.googlesource.com/infradata/config/+/master/configs/luci-config).
* [chrome-infra-auth](https://chrome-infra-auth.appspot.com) and
  [buildbucket](https://cr-buildbucket.appspot.com) expose a
  [metadata endpoint](https://apis-explorer.appspot.com/apis-explorer/?base=https://cr-buildbucket.appspot.com/_ah/api#p/config/v1/config.get_metadata)
  that specify that they can validate their configs. The metadata endpoints are
  registed in
  [servies/luci-config:services.cfg](https://chrome-internal.googlesource.com/infradata/config/+/master/configs/luci-config/services.cfg).
  Luci-Config discovers and talks to them to delegate the validation.

Invalid configs are **NOT** imported into luci-config. Entire config set
revision (all files) is rejected if at least one file is invalid. Services that
consume configs through luci-config are guaranteed not to receive invalid
configs, as long as they make backward-compatible changes to validation code.

As of 2015-07-09 an, when an invalid config is not imported, an error is emitted
in [luci-config logs](https://console.developers.google.com/project/luci-config/logs?service=appengine.googleapis.com&key1=backend&minLogLevel=500)
and ereporter2 sends an email to
[config-ereporeter2-config group](https://chrome-infra-auth.appspot.com/auth/groups#config-ereporter2-reports)
with max an hour latency. The plan is to implement presubmit check for configs
through luci-config API, and maybe send an email to a commit author.
