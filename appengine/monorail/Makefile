# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

# Makefile to simplify some common AppEngine actions.
# Use 'make help' for a list of commands.

STAGEID= monorail-staging
PRODID= monorail-prod

GAE_PY?= python gae.py
DEV_APPSERVER_FLAGS?=

FRONTEND_MODULES?= default
BACKEND_MODULES?= besearch latency-insensitive

VULCANIZE_PATH = ./node_modules/vulcanize/bin/vulcanize
CRISPER_PATH = ./node_modules/crisper/bin/crisper
VULCANIZE = $(VULCANIZE_PATH) $(1).html --inline-script \
		| $(CRISPER_PATH) \
		--html $(1).vulcanized.html --js $(1).vulcanized.js --only-split

PY_DIRS = api,features,framework,project,proto,search,services,sitewide,testing,tracker

default: help

check:
ifndef NPM_VERSION
	$(error npm not found. Install from nodejs.org or see README)
endif

help:
	@echo "Available commands:"
	@sed -n '/^[a-zA-Z0-9_.]*:/s/:.*//p' <Makefile

prpc_proto:
	touch ../../ENV/lib/python2.7/site-packages/google/__init__.py
	PYTHONPATH=../../ENV/lib/python2.7/site-packages \
	PATH=../../luci/appengine/components/tools:$(PATH) \
	../../cipd/protoc \
	--python_out=. --prpc-python_out=. api/api_proto/*.proto

test:
	../../test.py test appengine/monorail

test_no_coverage:
	../../test.py test appengine/monorail --no-coverage

coverage:
	@echo "Running tests + HTML coverage report in ~/monorail-coverage:"
	../../test.py test appengine/monorail --html-report ~/monorail-coverage

# Commands for running locally using dev_appserver.
serve: deps
	@echo "---[Starting SDK AppEngine Server]---"
	$(GAE_PY) devserver -- $(DEV_APPSERVER_FLAGS)

serve_email: deps
	@echo "---[Starting SDK AppEngine Server]---"
	$(GAE_PY) devserver -- $(DEV_APPSERVER_FLAGS) --enable_sendmail=True

# The _remote commands expose the app on 0.0.0.0, so that it is externally
# accessible by hostname:port, rather than just localhost:port.
serve_remote: deps
	@echo "---[Starting SDK AppEngine Server]---"
	$(GAE_PY) devserver -o -- $(DEV_APPSERVER_FLAGS)

serve_remote_email:
	@echo "---[Starting SDK AppEngine Server]---"
	$(GAE_PY) devserver -o -- $(DEV_APPSERVER_FLAGS) --enable_sendmail=True

run: serve

deps:
	rm -rf bower_components

	bower install
	npm install --no-save

	ln -s ../../../crdx/chopsui bower_components/chopsui

vulcanize: clean_vulcanized
	$(call VULCANIZE, elements/flt/mr-approval-page/mr-approval-page)
	$(call VULCANIZE, elements/chdir/mr-profile-page/mr-profile-page)
	$(call VULCANIZE, elements/mr-bar-chart/mr-bar-chart)
	$(call VULCANIZE, elements/mr-flipper/mr-flipper)

clean_vulcanized:
	find . -name "*.vulcanized.*" -delete

wct: deps
	xvfb-run go run ../../go/src/infra/tools/wct/wct.go  ../../go/src/infra/tools/wct/monkeypatch.go -base=. -prefix=elements/test/ -chrome=google-chrome

wct_debug: deps
	go run ../../go/src/infra/tools/wct/wct.go ../../go/src/infra/tools/wct/monkeypatch.go -base=. -prefix=elements/test/ -chrome=google-chrome -persist

pylint:
	pylint -f parseable *py {$(PY_DIRS)}{/,/test/}*py

# AppEngine apps can be tested locally and in non-default versions upload to
# the main app-id, but it is still sometimes useful to have a completely
# separate app-id.  E.g., for testing inbound email, load testing, or using
# throwaway databases.
deploy_staging: deps vulcanize
	@echo "---[Staging $(STAGEID)]---"
	$(GAE_PY) upload -A $(STAGEID) $(FRONTEND_MODULES) $(BACKEND_MODULES)
	make clean_vulcanized

# This is our production server that users actually use.
deploy_prod: deps vulcanize
	@echo "---[Deploying prod instance $(PRODID)]---"
	$(GAE_PY) upload -A $(PRODID) $(FRONTEND_MODULES) $(BACKEND_MODULES)
	make clean_vulcanized

# Note that we do not provide a command-line way to make the newly-uploaded
# version the default version. This is for two reasons: a) You should be using
# your browser to confirm that the new version works anyway, so just use the
# console interface to make it the default; and b) If you really want to use
# the command line you can use gae.py directly.
