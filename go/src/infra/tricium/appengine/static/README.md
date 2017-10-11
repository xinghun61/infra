RPC Explorer
------------

RPC Explorer is a web application for making pRPC calls using a browser.
In its built form, it is essentially a collection of static files (HTML,
JavaScript, CSS) that should be deployed to GAE as-is.

Its source code and build scripts are in the luci-go repository. The build
artifacts (static files to upload) are also located in a luci-go subdirectory,
which is pulled into Tricium's `static` GAE module via symlinks (see the
`common` symlink).

To build RPC Explorer:

1. Follow the setup instructions in [luci-go/web/README.md][1].
2. Navigate to the luci-go repo checkout in your `GOPATH`.
3. Build the deliverables: `./web/web.py build rpcexplorer`.
4. Confirm that it works by launching the GAE dev server and navigating to:
   http://localhost:8080/rpcexplorer/

At some point there will be more tooling to automate this process.

[1] https://chromium.googlesource.com/infra/luci/luci-go/+/42b037/web/README.md
