# The builders.pyl File Format

[go/builders-pyl]

builders.pyl is a declarative definition of a buildbot master. It is
intended to hide all of the buildbot-specific implementation details
from the user and just expose the features and settings a
non-buildbot-guru cares about.

[TOC]

## What is the .pyl format?

`.pyl` is short for PYthon Literal. It is a subset of Python syntax
intended to capture pure declarations of expressions. It is roughly
analogous to JSON: you can specify any Python object, but should limit
yourself to things like dicts, arrays, strings, numbers, and booleans.
It is basically JSON except that Python-style comments and trailing
commas are allowed.

## Overview

Each builders.pyl describes a single *waterfall*, which is a collection
of buildbot *builders* that talk to a single buildbot *master*. Each
builder may be implemented by multiple *bots*; you can think of a
bot as a single VM or machine.

Each master has one or more builders. A builder is basically a single
configuration running a single series of steps, collected together into
a [recipe](recipes.md). Each builder may have per-builder properties
set for it (to control the logic the recipe executes), and each builder
may also pass along properties from the bot, so there are four types
of configuration:

1.  overall per-master
2.  per-builder
3.  per-scheduler
4.  per-bot/bot pool

The keys in the dict should follow that order; within each section,
required keys should generally precede alternate keys, but things should
be ordered in the way that reads best.

Bots are usually collected into *pools*, so that they can be load
balanced. Every bot in the pool has the same configuration.

*** aside
Side note: buildbot used to call things "slaves" instead of "bots", and
lots of Chromium docs still use "slave".

For compatibility with older versions of builders.pyl, if the file contains
a field called "slave_port", then any field named "bot_X" must be called
"slave_X" instead. Once all of the builders.pyl files have been updated,
this support will be dropped.
***

## Example

Here's a simple file containing all of the required fields:

```python
{
  "master_base_class": "Master1",
  "master_port": 20100,
  "master_port_alt": 40100,
  "templates": ["../master.chromium/templates"],
  "bot_port": 30100,

  "builders": {
     "Linux": {
       "recipe": "chromium",
       "scheduler": "chromium_src_commits",
       "os": "linux",
       "version": "precise",
       "bot": "vm1-m1",
     },
  },

  "schedulers": {
    "chromium_src_commits": {
      "type": "git_poller",
      "git_repo_url": "https://chromium.googlesource.com/chromium/src.git",
    },
  },
}
```

## Top-level keys

At the top-level, builders.pyl files contain a single Python dictionary
containing things that are configured per-master.

### master_base_class

This is a *required* field. It must be set to the name of the Python
class of the buildbot master that this master is based on. This is
usually one of the classes defined in
[site_config/config_default.py](https://chromium.googlesource.com/chromium/tools/build/+/master/site_config/config_default.py).

For example, if you were setting up a new master in the -m1 VLAN, you
would be subclassing Master.Master1, so this value would be `'Master1'`.

### master_port

This is a *required* field. It must be set to the main IP port that the
buildbot master instance runs on. You should set this to the port
obtained from the admins.

### master_port_alt

This is a *required* field. It must be set to the alternate IP port that
the buildbot master instance runs on. You should set this to the port
obtained from the admins.

### bot_port

This is a *required* field. It must be set to the port that the buildbot
bots will attempt to connect to on the master.

### templates

This is a *required* field. It must be set to a list of directory paths
(relative to the master directory) that contains the HTML templates that
will be used to display the builds. Each directory is searched in order
for templates as needed (so earlier directories override later
directories).

### buildbot_url

This is an *optional* field. It can be set to customize the URL
the HTML templates use to refer to the top-level web page. If it
is not provided, we will synthesize one for build.chromium.org based
on the master name.

### buildbucket_bucket

This is an *optional* field but must be present if the builders on the
master are intended to be scheduled through buildbucket (i.e., they are
tryservers or triggered from other bots). Such builders normally have
their scheduler set to `None`, so, equivalently, if any of the builders
have their scheduler set to `None`, this field must be present.

If set, it should contain the string value of the
[buildbucket bucket](/appengine/cr-buildbucket/README.md) created for this
buildbot master. If it is not set, it defaults to `None`. By convention,
buckets are named to match the master name, e.g. "master.tryserver.nacl".

### default_remote_run_repository

This is an *optional* field, and is deprecated; Setting this is
equivalent to specifying `remote_run_repository` in builder_defaults,
and you should set that instead (or set it in a mixin or per-builder).

### master_classname

This is an *optional* field. If it is not specified, it is synthesized
from the name of the directory containing the builders.pyl file.

For example, if the builders.pyl file was in
[masters/master.client.crashpad](https://chromium.googlesource.com/chromium/tools/build/+/master/masters/master.client.crashpad/builders.pyl),
the master-classname would default to ClientCrashpad.

### pubsub_service_account_file

Similar to service_account_file, this is also an *optional* field but
must be present if the builders on the master are intended to send build data
to pubsub.

If set, it should point to the filename in the credentials directory on
the bot machine (i.e., just the basename + extension, no directory
part), that contains the [OAuth service account
info](../master_auth.md) the bot will use to connect to pubsub.
By convention, the value is "service-account-\<project\>.json".
The <project> field is usually "luci-milo" for most masters.  If not
set, it defaults to None.

### service_account_file

This is an *optional* field but must be present if the builders on the
master are intended to be scheduled through buildbucket (i.e., they are
tryservers or triggered from other builders, possibly on other masters).

Such builders normally have their scheduler set to `None`, so,
equivalently, if any of the builders have their scheduler set to `None`,
this field must be present.

If set, it should point to the filename in the credentials directory on
the bot machine (i.e., just the basename + extension, no directory
part), that contains the [OAuth service account
info](../master_auth.md) the bot will use to connect to buildbucket.
By convention, the value is "service-account-\<project\>.json". If not
set, it defaults to None.

### builder_defaults

This is an *optional* field and may be set to a dict of keys and values.
The values in this dict will be treated as a mixin (see below) that is
applied to every builder, prior to any other mixins.

### mixins

This is an *optional* field and may be set to a dict of keys and values;
each value must itself be a dictionary of keys and values. These dicts
may then be referenced in the builder dicts, in which case the values
from each mixin will be applied in left-to-right order as if they had
been specified directly in the builder dict. If the dict contains a
'mixins' key itself, the evaluation process will recursively apply the
sub-mixins specified before applying the values listed in the mixin
directly.

### builders

This is a *required* field and must be a dict of builder names and their
respective configurations; valid values for those configurations are
described in the per-builder configurations section, below.

### schedulers

This is a *required* field and must be a dict of scheduler names and
their respective configurations; valid values for those configurations
are described in the per-scheduler configurations section, below. The
dict may be empty, if there are no scheduled builders, only tryservers,
but it must be present even in that case.

### bot_pools

This is a *optional* field and must be a dict of pool names and
properties, as described below. If this field is missing, every builder
must specify bots directly inline in their definitions.

## Per-builder configurations

Each builder is described by a dict that may contain multiple fields, as
follows. Most of these fields may also be specified in the builder_defaults
and mixins keys, so that they may be applied to multiple builders.

### recipe

This is a *required* field that specifies the [recipe
name](/doc/users/recipes.md).

### scheduler

This is a *required* field that indicates which scheduler will be used
to schedule builds on the builder.

The field must be set to either `None` or to one of the keys in the
top-level `schedulers` dict. If it is set to None, then the builder will
only be schedulable via buildbucket; in this situation, the master must
have top-level `buildbucket_bucket` and `service_account_file` values
set (as noted above).

A builder that has a scheduler specified may also potentially be
scheduled via buildbucket, but that doing so would be unusual (builders
should normally only have one purpose).

### os

This is an *optional* field that may be used alongside `bot` or `bots` to
configure a builder inline instead of via a `bot_pool`. See the per-pool
`os` entry for additional restrictions.

### version

This is an *optional* field that may be used alongside `bot` or `bots` to
configure a builder inline instead of via a `bot_pool`. See the per-pool
`version` entry for additional restrictions.

### bot

This is an *optional* field that can be used to specify a single bot.
It is equivalent to `bots` except that it cannot be a list, it must be a
single string, and it cannot use hostname expansion wildcards.

### bots

This is an *optional* field that can be used to specify bots for the
builder directly, rather than specifying a bot_pool. The value may be
a single string representing either a single bot, or a wildcarded list
of bots, or a list of either of those two things.

### subdir

This is an *optional* field that may be used alongside `bot` or `bots` to
configure a builder inline instead of via a `bot_pool`. See the per-pool
`subdir` entry for additional restrictions.

### bot_pool

This is an *optional* field. If specified, it must be a string that
is a key into the top-level bot_pools dict.

### bot_pools

This is an *optional* field that specifies a list of one or more pools of bots
that can be builders; Each entry in the list must be a key in the top-level
bot_pools dict.

Either this field, or `bot_pool`, or the triple of either `os`, `version`,
and either `bot` or `bots` keys must be present in the builder entry.

### mergeRequests

This is an *optional* field that specifies whether buildbot will merge duplicate
requests together. If unspecified, this field defaults to True if a named
scheduler is specified, and False otherwise.

You might want to merge builds if you have a waterfall builder that is polling
a repository, because you want to always test the most current revision.
You would not want to merge builds for tryservers because you want to test each
revision in isolation.

### mixins

This is an *optional* list of mixins to be applied to the builder. Any
additional fields specified in the builder will override the values specified
in the mixins.

### auto_reboot

This is an *optional* field that specifies whether the builder should
reboot after each build. If not specified, it defaults to `True`.

### properties

This is an *optional* field that is a dict of settings that will be
passed to the [recipe](recipes.md) as key/value properties.

### botbuilddir

This is an *optional* field; if it is not set, it defaults to the
builder name. This field can be used to share a single build directory
between multiple builders (so, for example, you don't have to check out
the source tree twice for a debug builder and a release builder).

### category

This is an *optional* field that specifies a category for the builder, so you
can group builders visually on the master.  The categories are sorted
left-to-right in ascending order, and for display any initial number is
stripped.  So categories will often be specified like `"0builders"`,
`"1testers"`, etc.

### builder_timeout_s

If set, forcibly kill builds that run longer than this many seconds. If unset
(or None), builds may run indefinitely.

### use_remote_run

This is an *optional* boolean field. If set to true, it tells buildbot
to use the 'remote_run' factory to configure builds. Users should usually
set this to true at this point.

### remote_run_repository

This is an *optional* field that should be present and set to the repository
the recipe is found in if `use_remote_run` is set to true.

### remote_run_sync_revision

This is an *optional* field; if present and set to true, then the
repository used for the recipe (i.e., the `remote_run_repository`)
will be synced to the revision specified in the `revision` property
of the build, rather than using the HEAD version. This is useful for
when the recipe lives in the same repo as the code you are checking out
(i.e., for src-side recipes or the equivalent), in which case you probably
want to use the same revision for both the recipe and the code being built
and tested. In other situations, you almost certainly want this to be false,
since the revision will not even be for the right repo.

### repository

This is an *optional*, deprecated field and means the same thing as
`remote_run_repository`. If `remote_run_repository` is not set and this is,
it will be used. `remote_run_repository` is preferred because it makes the
purpose clearer; `repository` might be construed to be the repo that is
being checked out in the build, but that is not controlled here, it
is controlled in the recipe itself.

### no_output_timeout_s

This is an *optional* field. If set, a build will be aborted if no output
occurs for longer than the given number of seconds.

## Per-scheduler configurations

### type

This is a *required* field used to the type of scheduler this is; it
must have one of the following three values: `"cron"`, `"git_poller"`, or
`"repo_poller"`.

`cron` indicates that builds will be scheduled periodically (one or
more times every day). The scheduler dict must also have the "hour" and
"minute" fields.

`git_poller` indicates that builds will be scheduled when there are new
commits to the given repo. The scheduler dict must also have the "git-repo-url"
field.

`git_poller_any` like above, but can schedule builds for multiple branches. The
`"branch"` field may contain a list of uncompiled regular expressions.

`repo_poller` behaves the same as `git_poller`, but uses repo rather than git
(repo being the meta repository used in projects such as Android or ChromiumOS).
The scheduler dict must also have the `"repo_url"` field.

### git_repo_url

This is a *required* field if the scheduler type is "git_poller". It must
not be present otherwise.

It must contain a string value that is the URL for a repo to be cloned
and polled for changes.

### branch

This is an *optional* field that is used if the scheduler type is
"git_poller", "git_poller_any" or "repo_poller". It must not be present
otherwise.

It must contain a string value that is the branch name in the repo to watch.
If it is not specified, it defaults to "master".

For "git_poller_any" also a list of uncompiled regular expressions is
supported.

### repo_url

This is a *required* field if the scheduler type is "repo_poller". It must
not be present otherwise.

The URL that is the base of the repo tree. It is assumed that the manifest is
located in the `manifest` subdirectory of this path. For example, Android would
use `"https://android.googlesource.com/platform"` rather than
`"https://android.googlesource.com/platform/manifest"`.

### rev_link_template

This is an *optional* field that may be used with the "repo_poller" scheduler
type. It is a format string that will be used to generate a link to the change
being built in the build page.

The format string expects two string arguments: the project path and the
revision SHA. For example, Android uses
"https://android.googlesource.com/platform/%s/+/%s".

### hour

This is a *required* if the scheduler type is "cron". It must not be
present otherwise.

This field and the `minute` field control when cron jobs are scheduled
on the builder.

The field may have a value of either `"*"`, an integer, or a list of
integers, where integers must be in the range \[0, 23). The value `"*"`
is equivalent to specifying a list containing every value in the range.
This matches the syntax used for the `Nightly` scheduler in buildbot.

### minute

This is a *required* field if the scheduler type is "cron". It must
not be present otherwise.

This field and the `hour` field control when cron jobs are scheduled on
the builder.

The field may have a value of either `"*"`, an integer, or a list of
integers, where integers must be in the range \[0, 60). The value `"*"`
is equivalent to specifying a list containing every value in the range.
This matches the syntax used for the `Nightly` scheduler in buildbot.

## Per-pool configurations

Each pool (or group) of bots consists of a set of machines that all
have the same characteristics. The pool is described by a dict that
contains the following fields.

### bots

This is a *required* field that contains list of either individual hostnames,
one for each VM (do not specify the domain, just the basename), or a
string that can specify a range of hostnames, expanded as the bash shell
would expand them. So, for example, `vm{1..3}-m1` would expand to `vm1-m1`,
`vm2-m1`, `vm3-m1`.

### subdir

This is an *optional* string field specifying a name extension of a host
running multiple bots in separate processes. The bot's name will be
constructed as hostname#subdir. The same host can be specified multiple
times, using different subdir entries.

### bits

This is an *optional* field and must have either the value 32 or 64 (as
numbers, not strings). If not specified, this defaults to 64.

### os

This is a *required* field that must have one of the following values:
`"mac"`, `"linux"`, or `"win"`.

### version

This is an *optional* field and may have one of the following values (other
values may also be valid depending on what chrome-infra is supporting):

os       | Valid values
---------|-------------
`"mac"`  | `"10.9"`, `"10.10"`, `"10.11"`, `"10.12"`
`"linux"`| `"trusty"`, `"xenial"`
`"win"`  | `"win7"`, `"win10"`, `"2008"`

## Feedback

[crbug](https://crbug.com) label:
[Infra-MasterGen](https://crbug.com?q=label:Infra-MasterGen)

[go/builders-pyl]: http://go/builders-pyl
