# Source code

[TOC]

## Repos
Most of the chrome infra source code lives in these repos:

* [infra.git](..): primary public repo.
  Contains many AppEngine apps, monitoring libraries.
* [infra_internal.git](https://chrome-internal.googlesource.com/infra/infra_internal):
  Google-internal couterpart of infra.git. Contains CQ.
* [build](https://chromium.googlesource.com/chromium/tools/build/): legacy
  repo. Contains Buildbot, recipes, gatekeeper-ng.
* [build_internal](https://chrome-internal.googlesource.com/chrome/tools/build):
  internal couterpart of build repo.
* [build_limited](https://chrome-internal.googlesource.com/chrome/tools/build_limited/scripts/slave/):
  minimal set of internal code that must be checked out on buildbot slaves
  that run internal builds.
* [luci-py](https://github.com/luci/luci-py) on GitHub: chromium-independent
  reusable continuous integration services, written in Python.
  Contains Swarming, Isolate, Auth service, Config service and AppEngine
  components, used by AppEngine apps in infra.git and infra_internal.git
* [luci-go](https://github.com/luci/luci-go): like luci-py, but in Golang.
  Contains Isolate client. ([docs](https://godoc.org/github.com/luci/luci-go))

Standalone one-purpose repos:

* [expect_tests](https://chromium.googlesource.com/infra/testing/expect_tests):
  testing framework used for [recipe tests](users/recipes.md) and
  [infra.git's test.py](../test.py).
* [testing_support](https://chromium.googlesource.com/infra/testing/testing_support):
  utilities to support writing unittests for infra-related tools.
* [gae](https://github.com/luci/gae): Go wrapper interface around appengine APIs for
  better testability. ([docs](https://godoc.org/github.com/luci/gae))

See also
[other internal repos](http://go/chrome-infra-docs-internal/source.md).

## Checkout code

If you're reading this file, you're probably involved in the Chromium
project already. If this is not the case, you might want to read
[Chromium's Get the Code page](http://dev.chromium.org/developers/how-tos/get-the-code)
to get some background information. In particular,
[_depot_tools_ needs to be installed](http://dev.chromium.org/developers/how-tos/install-depot-tools).

First, generate and populate a .gitcookies file to provide authentication for
accessing the repos. Visit chromium.googlesource.com/new-password, choose to
authenticate only chromium.googlesource.com, and follow the provided directions.

The proper way to check out the non-GitHub repositories is to run:

    mkdir chrome_infra   # or whatever name you please
    cd chrome_infra
    fetch infra   # or `fetch infra_internal` if you are a Googler

## Packaging

Some Infra tooling requires manual operations to be performed in order to
package it for distribution. See [Packaging](packaging/index.md) for more
information.

## Make changes

See [Contributing](contributing.md).

## Troubleshooting

If you're a Googler and get authentication errors when running
`fetch infra_internal` you may need to add authentication for the internal repos
to your .gitcookies file. Visit chrome-internal.googlesource.com/new-password,
choose to authenticate only chromium.googlesource.com, and follow the provided directions.

If you're not running a supported distribution, `fetch infra` will
probably fail complaining that it cannot find some packages on Cloud
Storage. This happens with architecture-dependent packages like numpy,
which need to be compiled. The workaround is to build the packages for
yourself. Just run:

    infra/bootstrap/build_deps.py
    gclient runhooks

The first command will build the packages are store them locally. The
second command deploy them into `infra/ENV`. For more details on this
see [bootstraping](/bootstrap/README.md).

## For Googlers

If you are a Googler, see [more detailed
instructions](http://sites/chrome-infrastructure/getting-started) for working in the
other infra repositories.
