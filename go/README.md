# Chromium Infra Go Area

[TOC]


## Get the code

The steps for getting the code are:

 1. [Install depot_tools](https://www.chromium.org/developers/how-tos/install-depot-tools)
 1. Run `fetch infra`
 1. Run `infra/go/env.py`


### Quick Setup

If you are on Linux you can run the [quicksetup script](quicksetup.sh) like so:

```shell
cd /where/you/want/source/code
wget -O- "https://chromium.googlesource.com/infra/infra/+/master/go/quicksetup.sh?format=TEXT" | base64 -d | bash
```

This will create a self-contained `cr-infra-go-area` directory and populate it
will all necessary tools and source for using or contributing to Chromium's Go
Infrastructure. Once run, look in `cr-infra-go-area/infra/go/src` for the
editable source code.


## Structure

This directory contains a set of scripts to setup and manage a hermetic Go
building environment. We pin versions of the Go toolset and all third party
dependencies that the infra code is using. It is important for getting
non-flaky, reproducible builds of Go code on a CI and on developers' machines.

Structurally `infra/go` represents two workspaces (two directories in
`$GOPATH`):

   * `infra/go` itself is a GOPATH with Chrome Infra go code and a bunch of
     Chrome Infra owned projects
     (e.g. [luci-go](https://chromium.googlesource.com/infra/luci/luci-go)),
     that are DEPSed in into `infra/go/src/`. Such structure allows us to run CI
     for these projects in a hermetic environment on Chrome Infra waterfalls.
   * `infra/go/.vendor` is a GOPATH with locked versions of all third party code
     that `infra/go/src/*` depends on (including code needed by luci-go repo and
     other such DEPSed in dependencies). This directory is managed by `deps.py`
     script, based on configuration specified in `deps.yaml` and `deps.lock`.
     See "Dependency management" section below.

Note that `infra/go` is not "go get"-able, since it's not a go package. It's
GOPATH workspace.

The majority of active development is happening in
[luci-go](https://chromium.googlesource.com/infra/luci/luci-go) project that
**is** a proper Go package and can be fetched with `go get`.

luci-go doesn't pin any dependencies, assuming the end users (whoever links to
it) will do it themselves. `infra/go` workspace is one such end user. This
approach allows projects that use multiple big libraries (like luci-go) to
manage all dependencies centrally in a single place, thus avoiding issues of
version conflicts and binary bloat due to inclusion of a same third party code
via multiple import paths.


## Bootstrap

`infra/go` knows how to bootstrap itself from scratch (i.e. from a fresh
checkout) by downloading pinned version of Go toolset, and installing pinned
versions of third party packages it needs into `infra/go/.vendor` directory, and
adding a bunch of third party tools (like `goconvey` and `protoc-gen-go`) to
`$PATH`.

The bootstrap (and self-update) procedure is invoked whenever `go/bootstrap.py`
or `go/env.py` run. There's **no** DEPS hook for this. We only want the Go
toolset to be present on systems that need it, since it's somewhat big and
platform-specific.

`go/env.py` can be used in two ways. If invoked without arguments, it verifies
that everything is up-to-date and then just emits a small shell script that
tweaks the environment. This script can be executed in the current shell
process to modify its environment. Once it's done, Go tools can be invoked
directly. This is the recommended way of "entering" `infra/go` build
environment.

For example:

```shell
cd infra/go
eval `./env.py`
go install go.chromium.org/luci/tools/cmd/...
./bin/cproto --help  # infra/go/bin is where executables are installed
cproto --help        # infra/go/bin is also in $PATH
```

Alternatively `go/env.py` can be used as a wrapping command that sets up an
environment and invokes some other process. It is particularly useful on
Windows.

If the `INFRA_PROMPT_TAG` environment variable is exported while running
`go/env.py`, the new environment will include a modified `PS1` prompt containing
the `INFRA_PROMPT_TAG` value to indicate that the modified environment is being
used. By default, this value is "[cr go] ", but it can be changed by exporting
a different value or disabled by exporting an empty value.

## Dependency management

All third party code needed to build `infra/go` is installed into
`infra/go/.vendor` via `deps.py` script that is invoked as part of the bootstrap
process.

There are two files that control what code to fetch:

   * `deps.yaml` specifies what packages `infra/go` code depends on directly and
     where to get them (i.e. what git mirror repos to use). It **does not**
     specify package revisions in general, though some packages may optionally
     be pinned here too (too avoid being updated during `deps.py update` run,
     see below).
   * `deps.lock` is produced by `deps.py update` command and it specifies
     **the exact revisions** of all the packages in `deps.yaml` and all their
     transitive dependencies. This is a list of what is getting installed into
     `infra/go/.vendor`.

It is totally OK to modify `deps.yaml` or `deps.lock` by hand if you know what
you are doing. These files are actually consumed by [glide](http://glide.sh/).
See [glide.yaml file format](https://glide.readthedocs.org/en/latest/glide.yaml/)
for some details.


## Updating dependencies

`deps.lock` file should be periodically updated by running `deps.py update`.
Running this command bumps all revisions specified in `deps.lock` to the most
recent ones.

Here's the suggested workflow for updating all deps at once:

```shell
cd infra/go
eval `./env.py`
./deps.py update                    # bump revisions
./deps.py install                   # install new versions into .vendor/*
go test go.chromium.org/luci/...    # make sure everything works
git add deps.lock                   # commit new versions into the repo
git commit ...
```


## Adding a dependency

When `infra/go` code grows a dependency on some new third party library, this
library has to be added to `deps.yaml` and `deps.lock` files, or the code won't
build on a CI.

Here's the suggested workflow for doing this:

```shell
cd infra/go
eval `./env.py`
./deps.py add github.com/steveyen/go-slab

# deps.py will ask you to modify deps.yaml to specify location of a git
# mirror. Do that.
vi deps.yaml

./deps.py update
./deps.py install

git add deps.yaml
git add deps.lock
git commit ...
```


## Git mirrors for dependencies

All dependencies should be fetched from a `*.googlesource.com` host.

Some Golang related packages are already on `*.googlesource.com` (though it may
be non obvious at the first glance). For example all `golang.org/x/*` ones are
actually served from `https://go.googlesource.com/`.

`deps.py` will warn you if it sees a package being referenced from
a source-of-truth repo, and not a mirror.

If you are positive that a mirror is needed, file
[Infra-Git](https://bugs.chromium.org/p/chromium/issues/entry?template=Infra-Git)
ticket specifying what repository you need to be mirrored.
