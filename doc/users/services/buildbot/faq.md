# Chromium Buildbot FAQ

[TOC]

## How to setup a new buildbot master?

[go/new-master](http://go/new-master)

1.  To set up a new master, you need three ports. File an
    [Infra-Labs ticket](https://code.google.com/p/chromium/issues/entry?labels=Type-Bug,Pri-2,Infra-Labs,Restrict-View-Google)
    requesting ports for a new master and ask which VLAN your master should
    be on (and hence which `master_base_class` you should use). The port numbers
    and `master_base_class` settings go into your `builders.pyl` config file
    (see below).
1.  Create a new master directory in
    [build/masters](https://chromium.googlesource.com/chromium/tools/build/+/master/masters/) or
    [build_internal/masters](https://chrome-internal.googlesource.com/chrome/tools/build/+/master/masters/)
1.  Create a [builders.pyl file](builders.pyl.md) in the master directory
    describing the builders on this master. Set the port numbers and
    `master_base_class` to the values you got in step 1.
1.  File an
    [Infra-Labs ticket](https://code.google.com/p/chromium/issues/entry?labels=Type-Bug,Pri-2,Infra-Labs,Restrict-View-Google)
    for build slaves, and specify how many of each configuration you will need.
    After slaves are allocated, specify them in the
    `builders.pyl` file.
1.  Use [buildbot-tool](https://chromium.googlesource.com/chromium/tools/build/+/master/scripts/tools/buildbot-tool)
    to generate the rest of the master configuration.
1.  Add your new master to the long list in
    [masters_test.py](/chromium/tools/build/+/master/tests/masters_test.py):
    `'master.foo.bar': 'FooBar',`. You can find the class name `FooBar` in the
    `master_site_config.py` that was generated in your master directory.
1.  Commit what you have, then file a third, final
    [Infra-Labs ticket](https://code.google.com/p/chromium/issues/entry?labels=Type-Bug,Pri-2,Infra-Labs)
    asking for the appropriate URLs to be set up for your master, and a database
    configuration.

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