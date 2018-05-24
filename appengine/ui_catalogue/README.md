# Chrome UI Catalog Viewer

This is the Chrome UI Catalog Viewer, see [The Requirements Document](
https://docs.google.com/a/google.com/document/d/1Ki8yCzU4YG7jJ4LV-ofQ33W_05ZoqqNi994TiMJGN1M/edit?usp=sharing
) and [The Design Document](DESIGN.md). Note that this is still work in progress.

[TOC]

## Getting started

At the moment there are only two views, a summary view and a screenshot view.

When you open the page you will see an unfiltered view of all the screenshots.
Use the menus to select which screenshots are shown.

To see details of a screenshot click on the screenshot.

To compare two similar sets of screenshots (e.g. versions of the same
screenshots from two versions of Chrome):

* Duplicate the tab by right clicking on the tab strip and selecting duplicate.
* Modify the filters to create the second screenshot set.

## Installing

To install the UI Catalog development environment from scratch (on Linux, not
tested on other OSs):

* Checkout the infra repository from git and go into the UI Catalog directory
within its its workspace
  ```
  fetch infra
  cd infra/appengine/ui_catalogue
  ```
* If you don't already have them installed, install [nodejs](https://nodejs.org)
and [npm](https://www.npmjs.com/) following
the instuctions in https://cloud.google.com/nodejs/docs/setup. Just doing
`sudo apt-get install nodejs` won't work, since it will install a version of
nodejs without npm.

* Install [bower](https://bower.io/):
  ```
  npm install -g bower
  ```
* Install the Polymer CLI:
  ```
  npm install -g polymer-cli
  ```
* Install the Polymer libraries using bower (the libraries are listed in
[bower.json](bower.json)):
  ```
  make deps
  ```

For local use there is no need to build the the viewer.

## Running a local viewer
You can run a local Catalog Viewer using pylib/local_server.py.

* Set up your python environment:
  * (Optionally) create a python
  [virtualenv](https://virtualenv.pypa.io/en/stable/) so that your python
  installs don't modify your normal python environment:
    ```
    pip install virtualenv
    virtualenv [new virtualenv directory]
    . [virtualenv directory]/bin/activate
    ```
  * Install the required Python components using pip:
    ```
    pip install -r local_ui_server.pip`
    ```

Having set up your python environment you can then run the UI Catalog Viewer:

* You can use the UI Catalog to view screenshots generated either by the bots or
by a local test run
  * To capture screenshots in a local test run run the instrumentation tests (or
  a selection of them) with the `--local-output` option.

* If you created a virtualenv, start it using
  ```
  . [virtualenv directory]/bin/activate`
  ```
* Start the local server with the command:
  ```
  python pylib/local_server.py [screenshot description url]
  ```
  The `screenshot description url` is either the "ui screenshots" link output by
  the chrome_public_test_apk step on the bots, or that printed at the end of a
  local run of the instrumention tests.

   * This will open http://localhost:8080 in your default browser, and give you
   a view of the screenshots.

## Packaging the local viewer into a single file

The locally runnable version of the viewer can be packaged into a single file
for distribution using [PyInstaller](http://www.pyinstaller.org/)

* Install as above

* Install pyinstaller:
  ```
  pip install pyinstaller
  ```
* Build the server:
  ```
  make redistributable_local_server
  ```

This will create the executable file `pyinstall/dist/local_server` containing
everything needed to run the viewer. To run it, simply run this file from the
command line. The file can be copied to other locations and will still work.

## Deploying to App Engine

Install as above then:

* To deploy to staging run:
  ```
  make deploy_staging
  ```
  This will deploy to chrome-ui-catalog-staging

* To deploy to production run:
  ```
  make deploy_prod
  ```
  This will deploy to chrome-ui-catalog

## Directory structure

On checkout the top level directory contains three subdirectories:
* src - This contains the HTML and Javascript sources for the front end.
* polymer_test - this containst the tests for the front end.
* pylib - this contains the python sources for both the local and cloud back
  ends.
* pytlib/test - this contains tests for the sources in pylib.
* pylib/third_party - this contains a link to the cloudstorage module, and could
  contain links to other third party python modules.
* images - icons etc. used by the front end.

The top level directory contains index.html, the Makefile, and various
configuration files for building and testing the Viewer.

When the Viewer is built three additional directories may be created:
* bower_components - contains the required Bower components, including Polymer
  components
* build/e5-bundled - created by the Polymer builder, contains the minimized and
  bundled Polymer elements.
* pyinstall - This is used to build the packaged version of the local server.

## Testing

There are two sets of tests. The Polymer front end tests use the
[Polymer Test framework](https://www.polymer-project.org/2.0/docs/tools/tests).
They are run using the command `make polymer_test`.

The Python back end tests are based on the python
[unittest](https://docs.python.org/2/library/unittest.html) and
[unittest.mock](https://docs.python.org/3/library/unittest.mock.html) packages.
They are run using the command `make test`.

Note that the Python 3.3 *unittest.mock* package is backported into Python 2.7
as *mock*.
