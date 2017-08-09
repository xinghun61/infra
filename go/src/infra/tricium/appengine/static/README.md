RPC Explorer
------------

RPC Explorer is a web application for making pRPC calls using browser.

As a web application, in its built form, it is essentially a bunch of static
files (HTML, Javascript, CSS) that should be deployed to GAE as-is.

Its source code and build scripts are in luci-go repository. The build artifacts
(static files to upload) are also located in a luci-go subdirectory, which is
pulled into Tricium's `static` GAE module via symlinks (see `common` symlink).

To build RPC Explorer:

1. Follow setup instructions [here](https://go.chromium.org/luci/blob/master/web/README.md).
2. Navigate to luci-go repo checkout in your `GOPATH`.
3. Build the deliverables: `./web/web.py build rpcexplorer`
4. Confirm it works by launching GAE dev server and going to http://localhost:8080/rpcexplorer/

(At some point there'll be more tooling to automate this process)
