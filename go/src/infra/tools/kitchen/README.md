# kitchen

kitchen is a command line tool that can fetch a git _repository_, checkout at a
specific _revision_ and run a named _recipe_.
We call these three parameters _RRR_.

The only kitchen's runtime dependencies are git and python.
They must be in `$PATH.`

Although this repository is called `recipe-py`, kitchen is in Go to simplify
deployment.

## Installation

To compile and install kitchen, pick a go code directory, e.g.

    $ export GOPATH=$HOME/go

then just install kitchen using `go get`:

    $ go get -u github.com/luci/recipes-py/go/cmd/kitchen

The binary will be located in `$GOPATH/bin/kitchen`.

Authenticate into the isolate server using:
`isolate login https://isolateserver.appspot.com`

If you use go v1.5 or above, ignore the portion about the cross compilation
toolchain.
If you use go v1.4 or below, you will need to install the cross compilation
toolchains by:
`wget
https://raw.githubusercontent.com/davecheney/golang-crosscompile/master/crosscompile.bash`
`source crosscompile.bash`
`go-crosscompile-build-all`
