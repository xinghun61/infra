# Chromium Infra Go Area


## Why Go?

Python is great, except when you need to deploy same python program (with tons
of dependencies) simultaneously to Windows, Mac and Linux machines, or when
"lets fetch all the source code and just run it" approach no longer works.

For example, consider a daemon or a cron job that runs under 'root'. Bringing
an entire infra/infra gclient and virtualenv machinery, and running it as 'root'
each time cron job needs to be updated is a bad idea.

So we need to be able to transform source code into a binary package and deploy
the package instead. Unfortunately, there's no good support for building
self contained deployable packages from python source code uniformly across
all platforms. Most existing (mostly linux) tools (e.g. 'pex') look pretty
scary, and require some effort to mix them with infra/infra wheelhouse
structure.

On the other hand, Go code always compiles to s single statically linked
self contained executable. There's just no other way to run Go code. It's only
natural to split building and deployment into two distinct phases, and deploy
only the executable.

What makes Go to stand out even more:
  * Go code is much more cross platform (compared to other compiled languages)
  * Go has batteries included
  * Go package management, while not without holes, is pretty good
  * Go is fast
  * Go is easy to learn


## Bootstrap

infra/go is self contained. It knows how to bootstrap itself from scratch (i.e.
from a fresh checkout) by downloading pinned version of Go toolset, and
installing pinned versions of third party packages it needs into
infra/go/.vendor directory (using [goop](https://github.com/nitrous-io/goop)
tool).

Bootstrap (and self-update) procedure is invoked whenever go/bootstrap.py
or go/env.py runs. There's **no** DEPS hook for this. We only want the Go
toolset to be present on systems that need it, since it's somewhat big and
platform-specific.

go/env.py can be used in two ways. If invoked without arguments, it verifies
that everything is up-to-date and then just emits a small shell script that
tweaks the environment. This script can be executed in the current shell
process to modify its environment:

    cd infra/go
    eval `./env.py`

Once it's done, Go tools can be invoked directly.

Alternatively go/env.py can be used as a wrapping command that sets up an
environment and invokes some other process, e.g.

    cd infra/go
    ./env.py go fmt ./...

It is particularly useful on Window.


## Code structure

All third party dependencies are managed by goop. They are not checked in into
infra/infra repository, but rather just referenced in Goopfile and Goopfile.lock
files (with pinned revision). Bootstrap procedure takes care of fetching and
building them.

All infra Go code should live in infra/ package (i.e. in go/src/infra directory)
and nowhere else.


## Workflows

Building everything and installing binaries into infra/go/bin:

    cd infra/go
    ./go.py install ./...

Running all tests:

    cd infra/go
    ./go.py test ./...

(You've got the idea, ./go.py just wraps 'go').


## Dependencies

Adding or updating a dependency:

    cd infra/go
    vi Goopfile
    <modify revision of the appropriate package, add new package, etc>
    ./env.py goop update
    <review Goopfile.lock diff, revert undesired changes>
    ./bootstrap.py
    <verify everything works>
    <commit the change to Goopfile and Goopfile.lock>

**Do not use 'go get'. Modify Goopfile instead.**

See more information about Goopfile file format on
[goop github page](https://github.com/nitrous-io/goop).


## Git mirrors for dependencies

All dependencies should be fetched from chromium.googlesource.com host.

To convert Mercurial project to Git you may use fast-export tool. For example,
the entire process of importing goauth2 package looks like this:

    hg clone https://code.google.com/p/goauth2/
    git clone git://repo.or.cz/fast-export.git
    git init goauth2.git
    cd goauth2.git
    ../fast-export/hg-fast-export.sh -r ../goauth2
    git push https://chromium.googlesource.com/infra/third_party/go/code.google.com/p/goauth2.git refs/*:refs/*

For Go projects that are originally in Git use git_updater service.

Once the mirror is up, add pinned dependency to Goopfile, asking goop to
use the mirror when fetching it:

    code.google.com/p/goauth2/oauth #f02aa781ad087b29b5b6276564da3215d39a6d61 !https://chromium.googlesource.com/infra/third_party/go/code.google.com/p/goauth2.git

(note: .git suffix is important)
