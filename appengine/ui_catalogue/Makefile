# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

# Makefile to simplify some common AppEngine actions.
# Use 'make help' for a list of commands.

STAGEID= chrome-ui-catalog-staging
PRODID= chrome-ui-catalog

GAE_PY?= python gae.py

default: help

help:
	@echo "Available commands:"
	@sed -n '/^[a-zA-Z0-9_.]*:/s/:.*//p' <Makefile

check:
	bower > /dev/null || (echo ""; echo "Please install bower, see README.md"; echo ""; exit 125)
	polymer > /dev/null || (echo ""; echo "Please install the Polymer CLI, see README.md"; echo ""; exit 125)

test:
	../../test.py test appengine/ui_catalogue

test_polymer: deps
	polymer test polymer_test

test_no_coverage:
	../../test.py test appengine/ui_catalogue --no-coverage

coverage:
	@echo "Running tests + HTML coverage report in ~/ui_catalogue_coverage:"
	../../test.py test appengine/ui_catalogue --html-report ~/ui_catalogue_coverage

build_polymer: deps
	polymer build

deps: check
	bower install

deploy_staging: build_polymer
	@echo "---[Staging $(STAGEID)]---"
	$(GAE_PY) upload -A $(STAGEID)

# This is our production server that users actually use.
deploy_prod: build_polymer
	@echo "---[Deploying prod instance $(PRODID)]---"
	$(GAE_PY) upload -A $(PRODID)
