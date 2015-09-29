# Chromium Infra Go Area

[TOC]

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

*   Go code is much more cross platform (compared to other compiled languages)
*   Go has batteries included
*   Go package management, while not without holes, is pretty good
*   Go is fast
*   Go is easy to learn


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

It is particularly useful on Windows.


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
    ./env.py go install ./...

Running all tests:

    cd infra/go
    ./env.py go test ./...

OR, to also grab code coverage report:

    cd infra/go
    ./env.py ./test.py


## Adding or updating a single dependency

In a nutshell, to add a dependency add it to Goopfile, run goop update to
fetch all new dependencies (i.e. indirect ones). Then copy over all new
dependencies from Goopfile.lock to Goopfile. We need to move them to Goopfile
to be able to attach git mirror locations (see below).

    cd infra/go
    vi Goopfile
    <modify revision of the appropriate package, add new package, etc>
    ./env.py goop update
    <review Goopfile.lock diff, copy new lines to Goopfile>
    <setup git mirrors, update Goopfile with location of git mirrors>
    ./env.py goop update # run again to ensure mirrors work
    ./bootstrap.py
    <verify everything works>
    <commit the change to Goopfile and Goopfile.lock>

**Packages fetched by 'go get' do not persist. Modify Goopfile instead.**

See more information about Goopfile file format on
[goop github page](https://github.com/nitrous-io/goop).


## Rolling all dependencies at once

Use roll_goop.py script. The full workflow:

    ./roll_goop.py
    ./env.py goop update

    # Examine diff. Setup mirrors for all new dependencies. Copy all new
    # dependencies from Goopfile.lock to Goopfile, otherwise next 'goop update'
    # will overwrite mirror URLs.
    git diff Goopfile.lock
    vi Goopfile

    # Now that Goopfile is updated with mirror URLs, make sure everything looks
    # fine by repeating exact same procedure again. There should be no new
    # dependencies.
    ./roll_goop.py
    ./env.py goop update
    git diff Goopfile.lock

    # Test that our code still works.
    ./env.py go test github.com/luci/gae/...
    ./env.py go test github.com/luci/luci-go/...
    ./env.py go test infra/...

    # Commit, upload the CL.
    git add ...
    git commit ...
    git cl upload

    # Send try jobs on Windows. There may be Windows specific dependencies.
    git cl try -m tryserver.infra -b "Infra Win Tester"

    # Add some missing one (you may need to setup a mirror and/or transfer more
    # dependencies from Goopfile.lock to Goopfile).
    vi Goopfile
    ./env.py goop update
    git diff Goopfile.lock

    # Rinse and repeat until all Win dependencies added.
    git add ...
    git commit --amend
    git cl upload
    git cl try -m tryserver.infra -b "Infra Win Tester"

If you suspect that some packages are no longer needed, you can run
clean_goop.py script. It will detect potentially unused packages and print them.
It's not fully trusted to work yet, and thus it's not used automatically.

    ./env.py python clean_goop.py
    <remove what it said to remove>

    ./env.py goop update
    git diff Goopfile.lock
    <ensure packages are gone from Goopfile.lock>

    # Test that our code still works.
    ./env.py go test github.com/luci/gae/...
    ./env.py go test github.com/luci/luci-go/...
    ./env.py go test infra/...

Note: both roll_goop.py and clean_goop.py have lists of exceptional packages
hardcoded in them. If you encounter some stubborn package that is handled badly
by these scripts, consider adding it to the exceptions.


## Git mirrors for dependencies

All dependencies should be fetched from a *.googlesource.com host.

Some Golang related packages are already on *.googlesource.com (though it may
be non obvious at the first glance). For example all golang.org/x/* ones are
actually served from https://go.googlesource.com/.

If you are positive that mirror is needed, file
[Infra-Git](https://code.google.com/p/chromium/issues/entry?template=Infra-Git)
ticket specifying what repository you need to be mirrored.
