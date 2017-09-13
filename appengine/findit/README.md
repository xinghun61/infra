# Assumptions

The Current Working Directory is $SRC_ROOT/infra/appengine/findit, i.e. the
directory that contains this file. Please `cd` into it for the commands below to
work.

Note:
1. For Mac, if GoogleAppEngineLauncher is used to run Findit locally, you
    may have to set the field "Extra Flags" under "Launch Settings" with value
   "$SRC_ROOT/infra/appengine/findit/waterfall-backend.yaml
    $SRC_ROOT/infra/appengine/findit/waterfall-frontend.yaml".
2. For Windows, you may have to read the contents of the makefile to learn how
   to run all of the commands manually.

# How to set up Polymer?
  Install nodejs and npm.

  If you must install nodejs system-wide you could use
  `sudo apt-get install nodejs-legacy npm` but be aware that the version of
  nodejs that this will get you tends to be old.

  Get polymer:
  `npm install -g bower`
  And install it inside findit:
  `cd $SRC_ROOT/infra/appengine/findit/third_party && bower install && cd -`

  (Or you can also use `make polymer-install`)

# How to run Findit locally?

From command line, run:
  `make run`

Then open http://localhost:8080 for the home page.

# How to run unit tests for Findit?

From command line, run:
  `make test`

If a code path branch is not tested and no line number is shown in the command
line output, you could check the code coverage report shown in the output.

# How to automatically format python code?

YAPF is used to format the code in chromium style, and it is expected to format
the code before uploading a CL for review. To install YAPF, please refer to
https://github.com/google/yapf.

From command line, run:
  `make format`

# How to deploy to appengine?

## Staging
Deploy to the staging instance (and make it default):
  `make clean && make deploy-staging`

## Production
Deploy to findit-for-me.appspot.com (production):
  `make clean && make deploy-prod`

To make the new version the default:
  `make migrate`

# Code Structure
* [services/](services/) contains service-layer code for the core analysis logic
  for compile failures, reliable test failures, and flaky tests.
* [pipelines/](pipelines/) contains code for the pipeline flows that connect the
  different analysis units from the service layer.
We are refactoring [waterfall/](waterfall/) into services/ and pipelines/ to
separate analysis logic from pipeline flow.
