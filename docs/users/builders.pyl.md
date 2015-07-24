# The builders.pyl File Format

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
builder may be implemented by multiple *slaves*; you can think of a
slave as a single VM.

Each master has one or more builders. A builder is basically a single
configuration running a single series of steps, collected together into
a [recipe](recipes.md). Each builder may have per-builder properties
set for it (to control the logic the recipe executes), and each builder
may also pass along properties from the slave, so there are four types
of configuration:

1.  overall per-master
2.  per-builder
3.  per-scheduler
4.  per-slave

The keys in the dict should follow that order; within each section, all
required keys should appear first (sorted alphabetically), then all
optional keys (sorted alphabetically).

Slaves are usually collected into *pools*, so that they can be load
balanced. Every slave in the pool has the same configuration.

*** aside
Side note: the "master"/"slave" terminology is buildbot's; we don't
like it, but use it to avoid confusion.
***

## Example

Here's a simple file containing all of the required fields:

```python
{
  "master_base_class": "Master1",
  "master_port": 20100,
  "master_port_alt": 40100,
  "slave_port": 30100,
  "templates": ["../master.chromium/templates"],

  "builders": {
     "Chromium Mojo Linux": {
       "recipe": "chromium_mojo",
       "scheduler": "chromium_src_commits",
       "slave_pools": ["linux_precise"],
       "category": "0builders",
     },
  },

  "schedulers": {
    "chromium_src_commits": {
      "type": "git_poller",
      "git_repo_url": "https://chromium.googlesource.com/chromium/src.git",
    },
  },

  "slave_pools": {
    "linux_precise": {
      "slave_data": {
        "bits": 64,
        "os": "linux",
        "version": "precise",
      },
      "slaves": ["vm46-m1"],
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
[build/site-config/config-bootstrap.py](/chromium/tools/build/+/master/site_config/config_bootstrap.py).

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

### slave_port
This is a *required* field. It must be set to the port that the buildbot
slaves will attempt to connect to on the master.

### templates
This is a *required* field. It must be set to a list of directory paths
(relative to the master directory) that contains the HTML templates that
will be used to display the builds. Each directory is searched in order
for templates as needed (so earlier directories override later
directories).

### buildbucket_bucket
This is an *optional* field but must be present if the builders on the
master are intended to be scheduled through buildbucket (i.e., they are
tryservers or triggered from other bots). Such builders normally have
their scheduler set to `None`, so, equivalently, if any of the builders
have their scheduler set to `None`, this field must be present.

If set, it should contain the string value of the [buildbucket
bucket](buildbucket.md) created for this buildbot.
If it is not set, it defaults to `None`. By convention, buckets are
named to match the master name, e.g. "master.tryserver.nacl".

### master_classname
This is an *optional* field. If it is not specified, it is synthesized
from the name of the directory containing the builders.pyl file.

For example, if the builders.pyl file was in
[masters/master.client.crashpad](https://chromium.googlesource.com/chromium/tools/build/+/master/masters/master.client.crashpad/builders.pyl),
the master-classname would default to ClientCrashpad.

### service_account_file
This is an *optional* field but must be present if the builders on the
master are intended to be scheduled through buildbucket (i.e., they are
tryservers or triggered from other builders, possibly on other masters).

Such builders normally have their scheduler set to `None`, so,
equivalently, if any of the builders have their scheduler set to `None`,
this field must be present.

If set, it should point to the filename in the credentials directory on
the slave machine (i.e., just the basename + extension, no directory
part), that contains the [OAuth service account
info](../master_auth.md) the slave will use to connect to buildbucket.
By convention, the value is "service-account-\<project\>.json". If not
set, it defaults to None.

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

### slave_pools
This is a *required* field and must be a dict of pool names and
properties, as described below.

## Per-builder configurations

Each builder is described by a dict that contains three or four fields:

### recipe
This is a *required* field that specifies the [recipe
name](recipes.md).

### scheduler
This is a *required* field that indicates which scheduler will be used
to schedule builds on the builder.

The field have must be set to either `None` or to one of the keys in the
top-level `schedulers` dict. If it is set to None, then the builder will
only be schedulable via buildbucket; in this situation, the master must
have top-level `buildbucket_bucket` and `service_account_file` values
set (as noted above).

A builder that has a scheduler specified may also potentially be
scheduled via buildbucket, but that doing so would be unusual (builders
should normally only have one purpose).

### slave_pools
This is a *required* field that specifies one or more pools of slaves
that can be builders.

### auto_reboot
This is an *optional* field that specifies whether the builder should
reboot after each build. If not specified, it defaults to `True`.

### properties
This is an *optional* field that is a dict of settings that will be
passed to the [recipe](recipes.md) as key/value properties.

### slavebuilddir
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

## Per-scheduler configurations

### type
This is a *required* field used to the type of scheduler this is; it
must have one of the following two values: `"cron"` or `"git_poller"`.

The former indicates that builds will be scheduled periodically (one or
more times every day); the latter indicates that builds will be
scheduled when there are new commits to the given repo.

If the type is "cron", the scheduler dict must also have the "hour" and
"minute" fields; if the type is "git-poller"; the scheduler dict must
also have the "git-repo-url" field.

### git_repo_url
This is an *optional* field but must be present if the scheduler type is
"git-poller".

It must contain a string value that is the URL for a repo to be cloned
and polled for changes.

### hour
This is an *optional* field but must be present if and only if the
scheduler type is "cron". If this field is present, `minute` must be
also.

This field and the `minute` field control when cron jobs are scheduled
on the builder.

The field may have a value of either `"*"`, an integer, or a list of
integers, where integers must be in the range [0, 23). The value `"*"`
is equivalent to specifying a list containing every value in the range.
This matches the syntax used for the `Nightly` scheduler in buildbot.

### minute
This is an *optional* field but must be present if and only if the
scheduler type is "cron". If this field is present, `hour` must be also.

This field and the `hour` field control when cron jobs are scheduled on
the builder.

The field may have a value of either `"*"`, an integer, or a list of
integers, where integers must be in the range [0, 60). The value `"*"`
is equivalent to specifying a list containing every value in the range.
This matches the syntax used for the `Nightly` scheduler in buildbot.

## Per-pool configurations

Each pool (or group) of slaves consists of a set of machines that all
have the same characteristics. The pool is described by a dict that
contains two fields

### slave_data
This is a *required* field that contains a dict describing the
configuration of every slaves in the pool, as described below.

### slaves
This is a *required* field that contains list of individual hostnames,
one for each VM (do not specify the domain, just the basename).

## Per-slave configurations

The slave-data dict provides a bare description of the physical
characteristics of each machine: operating system name, version, and
architecture, with the following keys:

### bits
This is a *required* field and must have either the value 32 or 64 (as
numbers, not strings).

### os
This is a *required* field that must have one of the following values:
`"mac"`, `"linux"`, or `"win"`.

### version
This is a *required* field and must have one of the following values:

os       | Valid values
---------|-------------
`"mac"`  | `"10.6"`, `"10.7"`, `"10.8"`, `"10.9"`, `"10.10"`
`"linux"`| `"precise"`, `"trusty"`
`"win"`  |   `"xp"`, `"vista"`, `"win7"`, `"win8"`, `"2008"`
