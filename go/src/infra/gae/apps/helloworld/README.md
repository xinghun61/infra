Simple multi-module classic GAE app
-----------------------------------

Provides an example of GAE app directory structure, unit testing and gae.py
integration.

All commands below assume infra.git go env is active. To active it:

    cd infra.git/go
    eval `./env.py`

To run unit tests:

    go test infra/gae/apps/helloworld/...

To run app locally:

    $ ./src/infra/gae/apps/helloworld/gae.py devserver
    INFO     2015-08-30 21:46:56,952 api_server.py:205] Starting API server at:
    ...

To deploy a new version to hello-app (but do not switch to it yet):

    $ ./src/infra/gae/apps/helloworld/gae.py upload -A hello-app
    Upload new version, update indexes, queues and cron jobs?
      Directory: helloworld
      App ID:    hello-app
      Version:   2769-2b8589a
      Modules:   default, backend
    Continue? [y/N] y
    02:48 PM Host: appengine.google.com
    ...
    02:48 PM Uploading cron entries.
    --------------------------------------------------------------
    New version:
      2769-2b8589a
    Uploaded as:
      https://2769-2b8589a-dot-hello-app.appspot.com
    Manage at:
      https://appengine.google.com/deployment?app_id=s~hello-app
    --------------------------------------------------------------

To switch default version:

    $ ./src/infra/gae/apps/helloworld/gae.py switch -A hello-app
    02:52 PM Host: appengine.google.com
    Specify a version to switch to:
      1242-1034dcb
      1248-de04da4
      2769-2b8589a
    Switch to version [2769-2b8589a]: <enter>
    Switch default version?
      Directory: helloworld
      App ID:    hello-app
      Version:   2769-2b8589a
      Modules:   default, backend
    Continue? [y/N] y
    02:53 PM Host: appengine.google.com
    02:53 PM Setting the default version of modules backend, default of application hello-app to 2769-2b8589a.

See gae.py help output for more available command.
