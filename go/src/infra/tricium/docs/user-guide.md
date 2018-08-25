## Tricium User Guide

## Setting up a project to use Tricium

### Add a project config

Project-specific configs are kept in individual project repos. The configs are
accessed via the luci-config service, but edited via CLs in their respective
repos. For instance, the project config for the "playground-gerrit-tricium"
project (which uses the dev instance) is at:
https://chromium.googlesource.com/playground/gerrit-tricium/+/infra/config/tricium-dev.cfg.
The project config for "luci-py", which uses the prod instance, is at:

https://chromium.googlesource.com/infra/luci/luci-py/+/infra/config/tricium-prod.cfg.

Project configs are usually kept in the "infra/config" branch of your project's
repository. The actual location of the project config depends on the project's
configuration in the list of projects for luci-config.

To make changes on this branch, try something like the following, where $REPO is
set to the project name on chromium.googlesource.com.

```
export REPO=chromium/src
mkdir -p infra-config/$REPO
cd infra-config/$REPO
git init
git remote add origin https://chromium.googlesource.com/$REPO
git config --unset-all remote.origin.fetch
git config --add remote.origin.fetch infra/config:refs/remotes/origin/infra/config
git config --add remote.origin.fetch infra/config:infra/config
git fetch origin
git checkout -t origin/infra/config -b my-edit
```

### Add a Gerrit Plugin Config for Project

To modify the plugin tricium.config file for a repository, you must make a
change in
[refs/meta/config](https://gerrit-review.googlesource.com/Documentation/config-project-config.html#_the_refs_meta_config_namespace)
for that repository.

Depending on the configuration of the repository, you may be able to do this in
a similar way as above:

```
export REPO=chromium/src
mkdir -p meta/$REPO
cd meta/$REPO
git init
git remote add origin https://chromium.googlesource.com/$REPO
git config --unset-all remote.origin.fetch
git config --add remote.origin.fetch refs/meta/config:refs/remotes/origin/refs/meta/config
git config --add remote.origin.fetch refs/meta/config:refs/meta/config
git fetch origin
git checkout -t origin/refs/meta/config -b my-edit
```

## Analyzer Development

See [contribute.md](./contribute.md).

