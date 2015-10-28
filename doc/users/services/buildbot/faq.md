# Chromium Buildbot FAQ

[TOC]

## How to setup a new buildbot master?

[go/new-master](http://go/new-master)

1. Determine the host machine for your buildbot master.
   Refer to [go/chrome-infra-mastermap] for examples.
   Do not put an internal master together with public ones, otherwise public
   slaves with possibly untrusted code will have network access to your slaves.
   Typical safe choices for new chrome infra clients: `master3` (public) or
   `master7` (internal).
1. Choose a master name, e.g. `master.client.x`.
1. File a [slave-request ticket] early.  Include master's vlan (m3, m7 or so),
   and slave types (GCE or VMs).
1. Create a new master directory in
   [build/masters](https://chromium.googlesource.com/chromium/tools/build/+/master/masters/) or
   [build_internal/masters](https://chrome-internal.googlesource.com/chrome/tools/build/+/master/masters/).
1. Create a [builders.pyl file](builders.pyl.md) in the master directory
   describing the builders on this master.  You could leave 0 for
   `master_port`, `master_port_alt` and `slave_port`.  `mastermap.py` will find
   it for you in later step.
1. Run `../../../build/scripts/tools/buildbot-tool gen .` in your master dir
   to regenerate master configuration. Run it whenever `builders.pyl` changes.
1. Run `../../../build/scripts/tools/mastermap.py --find <master-class-name>`
   where `master-class-name` is
   a name of the class in the generated `master_site_config.py`.
   It will search for available master port numbers.
   Put them to `builders.pyl` and regenerate the configuration.
1. Add your new master to the list of masters in [masters_test.py]:
   `'<master-name>': '<master-class-name>',`,
   so the master is included in presubmit checks.
1. If you were provided with slaves, update builders.pyl.
1. Send the CL, land it.
1. File a [master deployment ticket].

Whenever you modify builders.pyl, e.g. add/remove slaves, you need to
[restart the master].

## How to run buildbot locally for testing?

Commit your changes to a local branch. Many builders will `git reset --hard
HEAD` which will wipe out your local changes.

    $ cd build/masters/master.foo.bar
    $ make restart

To run a test slave locally to run the build:

    $ cd build/slave
    $ TESTING_MASTER=FooBar TESTING_MASTER_HOST=localhost TESTING_SLAVENAME=FooSlave make restart

`FooBar` is the same class name pulled from master_site_config.py above.
`FooSlave` is a slave listed in the builders.pyl, or slaves.cfg that you want to
impersonate locally.

## How to restart a buildbot master?

[Contact a trooper](https://chromium.googlesource.com/infra/infra/+/master/doc/users/contacting_troopers.md).

## How to schedule builds on buildbot from an external system?

Use [buildbucket](/appengine/cr-buildbucket/README.md) to schedule builds and
check their status:

1.  [Create a build bucket](/appengine/cr-buildbucket/doc/faq.md)
1.  Set `buildbucket_bucket` attribute in your [builders.pyl](builders.pyl.md)
1.  Set `service_account_file` attribute in your
    [builders.pyl](builders.pyl.md). [File a bug][master-service-account-bug] to
    deploy a new service account, or not sure what service account to use.
1.  Call [buildbucket.put].
1.  Check that your build was created using [buildbucket.get] or
    [buildbucket.search].
1.  Buildbot master will poll the build and schedule it on buildbot.
1.  When the buildbot build is completed, buildbucket build will be updated.

## How to write a build/test script?

Use [recipes](../../recipes.md)


[buildbucket.put]: https://cr-buildbucket.appspot.com/_ah/api/explorer/#p/buildbucket/v1/buildbucket.put
[buildbucket.get]: https://cr-buildbucket.appspot.com/_ah/api/explorer/#p/buildbucket/v1/buildbucket.get
[buildbucket.search]: https://cr-buildbucket.appspot.com/_ah/api/explorer/#p/buildbucket/v1/buildbucket.search
[go/bug-a-trooper]: http://go/bug-a-trooper
[master-service-account-bug]: https://code.google.com/p/chromium/issues/entry?cc=nodir@chromium.org&labels=Infra-Buildbucket,Restrict-View-Google&summary=Service%20account%20[short%20name]%20for%20master.[master_name]&comment=Please%20provide%20a%20service%20account%20json%20key%20file%20%22service-account-[short%20name].json%22%20for%20[master%20name]%0A%0APlease%20remove%20Restrict-View-Google%20label%20if%20this%20not%20for%20an%20internal%20master.

[buildbot-tool]: https://chromium.googlesource.com/chromium/tools/build/+/master/scripts/tools/buildbot-tool
[slave-request ticket]: https://code.google.com/p/chromium/issues/entry?labels=Type-Bug,Pri-2,Infra-Labs,Restrict-View-Google&summary=[Slave%20request]%20for%20%3Cmaster%20name%3E&comment=Request%20for%20new%20slaves%20for%20master%20%3Cmaster-name%3E.%0A%0AQuantity:%0AOS:%0AVersion:%20default%0ABitness:%20default%20%0AExample:%20%3Cspecify%20an%20example%20slave%3E%0A%0ARepeat%20this%20block%20if%20you%20need%20different%20configurations.
[master deployment ticket]: https://code.google.com/p/chromium/issues/entry?labels=Type-Bug,Pri-2,Infra-Labs,Restrict-View-Google&summary=[Deploy%20master]%20%3Cmaster%20name%3E&comment=Please%20deploy%20master%20%3Cmaster-name%3E.%20It%20is%20committed%20to%20%3Cgitiles%20link%20to%20master,%20e.g.%20https://chromium.googlesource.com/chromium/tools/build/+/master/masters/master.tryserver.blink%3E%0A%0AFor%20admins:%20this%20typically%20includes%20%0A*%20configuring%20the%20reverse%20proxy%20on%20chromegw%0A*%20adding%20a%20.dbconfig.%0A*%20starting%20the%20master%20for%20the%20first%20time.
[go/chrome-infra-mastermap]: http://go/chrome-infra-mastermap
[restart the master]: contacting_troopers.md
[masters_test.py]: https://chromium.googlesource.com/chromium/tools/build/+/master/tests/masters_test.py
