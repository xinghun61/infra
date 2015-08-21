# Luci-config

Stores a registery of projects that use chrome-infra.
Imports config files from repos and provides unified API to read them.

*   Location: [luci-config.appspot.com](http://luci-config.appspot.com)
*   [Documentation](https://github.com/luci/luci-py/blob/master/appengine/config_service/README.md)
*   [Design Doc](http://go/luci-config)
*   [API](https://luci-config.appspot.com/_ah/api/explorer#p/config/v1/)
*   Safe to use for internal projects: yes, has ACLs.
*   Crbug label: [Infra-Config](https://code.google.com/p/chromium/issues/list?q=Infra%3DConfig)
*   Owner: nodir@

[TOC]

## Import

Luci-config imports config files from
[Gitiles](https://code.google.com/p/gitiles/) every 10 min:

* Service configs are imported from
  [infradata/config repo](https://chrome-internal.googlesource.com/infradata/config/+/master/configs/)
* Project configs are imported from `infra/config` branch of project repos
  (example: [infra.git](https://chromium.googlesource.com/infra/infra/+/infra/config))
* Ref configs are typically imported from `infra/config` directory of a branch.

ConfigSet->Location mapping can be found by calling
[config.get_mapping](https://luci-config.appspot.com/_ah/api/explorer#p/config/v1/config.get_mapping).

### Validation

* luci-config validates
  [its owns configs](https://chrome-internal.googlesource.com/infradata/config/+/master/configs/luci-config),
  including
  [the project registry](https://chrome-internal.googlesource.com/infradata/config/+/master/configs/luci-config/projects.cfg).
* [chrome-infra-auth](https://chrome-infra-auth.appspot.com) and
  [buildbucket](https://cr-buildbucket.appspot.com) expose a
  [metadata endpoint](https://apis-explorer.appspot.com/apis-explorer/?base=https://cr-buildbucket.appspot.com/_ah/api#p/config/v1/config.get_metadata)
  that specify that they can validate their configs. The metadata endpoints are
  registered in
  [services/luci-config:services.cfg](https://chrome-internal.googlesource.com/infradata/config/+/master/configs/luci-config/services.cfg).
  Luci-Config discovers and talks to them to delegate the validation.

Invalid configs are **NOT** imported into luci-config. Entire config set
revision (all files) is rejected if at least one file is invalid. Services that
consume configs through luci-config are guaranteed not to receive invalid
configs, as long as they make backward-compatible changes to validation code.

As of 2015-08-13, when an invalid config is not imported, an error is emitted
in [luci-config logs](https://console.developers.google.com/project/luci-config/logs?service=appengine.googleapis.com&key1=backend&minLogLevel=500)
and ereporter2 sends an email to
[config-ereporeter2-config group](https://chrome-infra-auth.appspot.com/auth/groups#config-ereporter2-reports)
with max an hour latency. The plan is to implement presubmit check for configs
through luci-config API, and maybe send an email to a commit author.

## Security

A project declares its visibility in `project.cfg` configuration file in
`infra/config` branch. Example:

    access: "group:all"

Means the project is public. If not set, it is visible only to a whitelist of
trusted services.

## See also

* [FAQ](faq.md)
