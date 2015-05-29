The builders.pyl File Format
============================

builders.pyl is a declarative definition of a buildbot master. It
is intended to hide all of the buildbot-specific implementation
details from the user and just expose the features and settings a
non-buildbot-guru cares about.

What is the .pyl format?
------------------------

`.pyl` is short for PYthon Literal. It is a subset of Python syntax
intended to capture pure declarations of expressions. 
It is roughly analogous to JSON: you can specify any Python object,
but should limit yourself to things like dicts, arrays, strings,
numbers, and booleans. It is basically JSON except that Python-style
comments and trailing commas are allowed.

Overview
--------

Each builders.pyl describes a single "waterfall", which is a collection
of buildbot "builders" that talk to a single buildbot "master". Each
"builder" may be implemented by multiple "slaves"; you can think of
a slave as a single VM.

Each master has one or more builders. A builder is basically a 
single configuration running a single series of steps, collected together
into a `recipe`_. Each builder may have per-builder properties set for
it (to control the logic the recipe executes), and each builder may
also pass along properties from the slave, so there are three levels
of configuration:

1. overall per-master
2. per-builder
3. per-slave

Slaves are usually collected into "pools", so that they can be load
balanced. Every slave in the pool has the same configuration.

(Side note: the "master"/"slave" terminology is buildbot's; we don't
like it, but use it to avoid confusion).

Example
-------

Here's a simple file containing all of the required fields::

  % cat builders.pyl
  {
    "builders": {
       "Chromium Mojo Linux": {
         "recipe": "chromium_mojo",
         "slave_pools": ["linux_precise"],
       },
    },
    "git_repo_url": "https://chromium.googlesource.com/chromium/src.git",
    "master_base_class": "Master1",
    "master_port": 20100,
    "master_port_alt": 40100,
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
    "slave_port": 30100,
  }
  %

Top-level keys
--------------

At the top-level, builders.pyl files contain a single Python dictionary
containing things that are configured per-master.

builders
  This key is *required* and contains a dict of builder names and their
  respective configurations; those configurations are described in
  the per-builder keys section, below.

buildbucket_bucket
  This key is *optional* but must be present if the builders on the
  master are intended to be scheduled through buildbucket (i.e., they
  are tryservers or triggered from other builders, possibly on other masters).

  If set, it should contain the string value of the `buildbucket bucket`_
  created for this buildbot. If it is not set, it defaults to `None`.
  By convention, buckets are named to match the master name, e.g.
  "master.tryserver.nacl".

git_repo_url
  This key is *optional*. If it is not set, the builders on the waterfall
  will only be triggerable by buildbucket (or directly).

  It should contain a string value that is the URL for a repo to be cloned and
  polled for changes.

master_base_class
  This key is *required*. It should specify the name of the Python
  class of the buildbot master that this master is based on. This is 
  usually one of the classes defined in build/site_config/config_bootstrap.py.

  For example, if you were setting up a new master in the -m1 VLAN, you would
  be subclassing Master.Master1, so this value would be 'Master1'.

master_port
  This key is *required*. It is the main IP port that the buildbot
  master instance runs on. You should set this to the port obtained
  from the admins.

master_port_alt
  This key is *required*. It is the alternate IP port that the buildbot
  master instance runs on. You should set this to the port obtained
  from the admins.

service_account_file
  This key is *optional* but must be present if the builders on the
  master are intended to be scheduled through buildbucket (i.e., they
  are tryservers or triggered from other bots).

  If set, it should point to the filename in the credentials directory on the
  slave machine (i.e., just the basename + extension, no directory part), that
  contains the `OAuth service account info`_ the slave will use to connect to
  buildbucket. By convention, the value is "service-account-<project>.json".
  If not set, it defaults to `None`.

slave_pools
  This key is *required* and must contain a dict of pool names and
  properties, as described below.

slave_port
  This key is *required*. It is the port that the buildbot slaves will
  attempt to connect to on the master.


Per-builder configurations
--------------------------

Each builder is described by a dict that contains two or three fields:

properties
  This is an *optional* dict of settings that will be
  passed to the `recipe`_ as (key-value) properties.

recipe
  This is a *required* field that specifies the `recipe name`_.

slave_pools
  This is a *required* field that specifies one or more pools of 
  slaves that can be builders.

Per-pool configurations
-----------------------

Each pool (or group) of slaves consists of a set of machines that
all have the same characteristics. The pool is described by a dict
that contains two fields

slave_data
  This is a *required* field that contains a dict describing the
  characteristcs of all the slaves in the pool, as described below.

slaves
  This is a *required* field that contains list of individual hostnames,
  one for each VM (do not specify the domain, just the basename).

Slave data
----------

The slave_data dict provides a bare description of the physical
characteristics of each machine: operating system name, version, and
architecture, with the following keys:

bits
  This is a *required* field and must have either the value 32
  or 64 (as numbers, not strings).

os
  This is a *required* field that must have one of the following values:
  "mac", "linux", or "win".

version
  This is a *required* field and must have one of the following values:

  If os is "mac": "10.6", "10.7", "10.8", "10.9", "10.10".

  If os is "linux": "precise" or "trusty".

  If os is "win": "xp", "vista", "win7", "win8", "2008"

.. _`buildbucket bucket`: https://cr-buildbucket.appspot.com
.. _`OAuth service account info`: ../master_auth.html
.. _`recipe`: recipes.html
.. _`recipe name`: recipes.html
