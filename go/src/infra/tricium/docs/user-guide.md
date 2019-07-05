## Tricium User Guide

This doc is intended for people who either want to set up a project to use
Tricium, or for those who want to configure where and how Tricium is triggered.

## Setting Up a Project to use Tricium

### Adding or Editing a Project Config

Project-specific configs are kept in individual project repositories. The
configs are accessed via the luci-config service, but edited via CLs in their
respective repos. For instance, the project config for "luci-py" is
[tricium-prod.cfg on infra/config branch in luci-py](https://chromium.googlesource.com/infra/luci/luci-py/+/infra/config/tricium-prod.cfg).

Project configs are generally kept in the "infra/config" branch of your
project's repository. The actual location of the project config depends on the
project's configuration in the list of projects for `luci-config`.

To make changes on this branch, you can make a new branch with
origin/infra/config as the upstream, for example by running:

```
git checkout -B branch-name --track origin/infra/config
```

A project config for the production instance of Tricium is always called
`tricium-prod.cfg`, and generally looks something like this:

```
selections {
  function: "GitFileIsolator"
  platform: UBUNTU
}
selections {
  function: "Pylint"
  platform: UBUNTU
}
repos {
  gerrit_project {
    host: "chromium-review.googlesource.com"
    project: "my/project"
    git_url: "https://chromium.googlesource.com/my-project"
  }
}
service_account: "tricium-prod@appspot.gserviceaccount.com"
swarming_service_account: "swarming@tricium-prod.iam.gserviceaccount.
```

Available functions are in [functions](../functions) directory.

If you are just enabling a new project with existing Analyzers, then you don't
need to edit the service config, which mostly contains the Analyzer definitions.

If you are adding a new Analyzer to be used across multiple projects, the
definition should go in the service config (which is in an internal location,
please contact tricium-dev@google.com).

### Enabling the Tricium Gerrit Plugin for a Gerrit Instance

If your project uses a Gerrit instance that already has Tricium enabled (e.g.
chromium) then you don't need to do anything here.

To enable the Tricium plugin for a new Gerrit instance, make a change in
[refs/meta/config](https://gerrit-review.googlesource.com/Documentation/config-project-config.html#_the_refs_meta_config_namespace).

Depending on the configuration of the repository, you may be able to do this in
a similar way as above, except using origin/refs/meta/config as the upstream
instead of origin/infra/config.

## Analyzer Development

See [contribute.md](./contribute.md) for more details about adding your own
analyzers.

## Selectively Disabling Tricium Based on Path

There are some types of files for which we may never want to run Tricium,
including generated files such as test expectation files. These can be skipped
on a per-repo and per-directory basis by specifying git attributes.

For example, if we wanted to skip all `.x` files in a directory tree, we could
add a `.gitattributes` file to that directory tree root with the line `*.x
-tricium`.

## Disabling Tricium for a Particular CL

To make Tricium skip a particular change, you can add "Tricium: disable" to the
CL description. A few alternate words besides "disable" are also recognized,
including "false", "skip", and "no".
