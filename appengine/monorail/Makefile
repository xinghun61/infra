# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

# Makefile to simplify some common AppEngine actions.
# Use 'make help' for a list of commands.

DEVID = monorail-dev
STAGEID= monorail-staging
PRODID= monorail-prod

GAE_PY?= python gae.py
DEV_APPSERVER_FLAGS?=

WEBPACK_PATH := ./node_modules/webpack-cli/bin/cli.js

TARDIR ?= "/workspace"

FRONTEND_MODULES?= default
BACKEND_MODULES?= besearch latency-insensitive

BRANCH_NAME := $(shell git rev-parse --abbrev-ref HEAD)

PY_DIRS = api,businesslogic,features,framework,project,proto,search,services,sitewide,testing,tracker

_VERSION ?= $(shell ../../../infra/luci/appengine/components/tools/calculate_version.py)

SPIN = $(shell command -v spin 2> /dev/null)

default: help

check:
ifndef NPM_VERSION
	$(error npm not found. Install from nodejs.org or see README)
endif

help:
	@echo "Available commands:"
	@sed -n '/^[a-zA-Z0-9_.]*:/s/:.*//p' <Makefile

# Run "eval `../../go/env.py`" before running the following
prpc_proto:
	touch ../../ENV/lib/python2.7/site-packages/google/__init__.py
	PYTHONPATH=../../ENV/lib/python2.7/site-packages \
	PATH=../../luci/appengine/components/tools:$(PATH) \
	../../cipd/protoc \
	--python_out=. --prpc-python_out=. api/api_proto/*.proto
	cd ../../go/src/infra/monorailv2 && \
	cproto -proto-path ../../../../appengine/monorail/ ../../../../appengine/monorail/api/api_proto/


test:
	../../test.py test appengine/monorail

test_no_coverage:
	../../test.py test appengine/monorail --no-coverage

coverage:
	@echo "Running tests + HTML coverage report in ~/monorail-coverage:"
	../../test.py test appengine/monorail --html-report ~/monorail-coverage

test_coverage:
	@echo "Running tests + HTML coverage report (for tests) in ~/monorail-test-coverage:"
	../../test.py test appengine/monorail --html-report ~/monorail-test-coverage --coveragerc appengine/monorail/.testcoveragerc

# Commands for running locally using dev_appserver.
serve: config_local
	@echo "---[Starting SDK AppEngine Server]---"
	$(GAE_PY) devserver -- $(DEV_APPSERVER_FLAGS)& $(WEBPACK_PATH) --watch

serve_email: config_local
	@echo "---[Starting SDK AppEngine Server]---"
	$(GAE_PY) devserver -- $(DEV_APPSERVER_FLAGS) --enable_sendmail=True& $(WEBPACK_PATH) --watch

# The _remote commands expose the app on 0.0.0.0, so that it is externally
# accessible by hostname:port, rather than just localhost:port.
serve_remote: config_local
	@echo "---[Starting SDK AppEngine Server]---"
	$(GAE_PY) devserver -o -- $(DEV_APPSERVER_FLAGS)& $(WEBPACK_PATH) --watch

serve_remote_email: config_local
	@echo "---[Starting SDK AppEngine Server]---"
	$(GAE_PY) devserver -o -- $(DEV_APPSERVER_FLAGS) --enable_sendmail=True& $(WEBPACK_PATH) --watch

run: serve

deps: node_deps
	rm -f static/dist/*

	mkdir -p deployed_node_modules/@webcomponents/webcomponentsjs/

	cp node_modules/@webcomponents/webcomponentsjs/webcomponents-bundle.js \
		deployed_node_modules/@webcomponents/webcomponentsjs/webcomponents-bundle.js

build_js:
	$(WEBPACK_PATH) --mode=production

clean_deps:
	rm -rf deployed_node_modules
	rm -rf node_modules

node_deps:
	npm ci --no-save

karma:
	npx karma start --debug --coverage

pylint:
	pylint -f parseable *py {$(PY_DIRS)}{/,/test/}*py

py3lint:
	pylint --py3k *py {$(PY_DIRS)}{/,/test/}*py

config: config_prod_cloud config_non_prod

config_prod:
	m4 -DPROD < app.yaml.m4 > app.yaml
	m4 -DPROD < module-besearch.yaml.m4 > module-besearch.yaml
	m4 -DPROD < module-latency-insensitive.yaml.m4 > module-latency-insensitive.yaml

config_prod_cloud:
	m4 -DPROD < app-cloud.yaml.m4 > app.prod.yaml
	m4 -DPROD < module-besearch-cloud.yaml.m4 > besearch.prod.yaml
	m4 -DPROD < module-latency-insensitive-cloud.yaml.m4 > latency-insensitive.prod.yaml

config_non_prod:
	m4 < app-cloud.yaml.m4 > app.yaml
	m4 < module-besearch-cloud.yaml.m4 > besearch.yaml
	m4 < module-latency-insensitive-cloud.yaml.m4 > latency-insensitive.yaml

config_staging:
	m4 -DSTAGING < app.yaml.m4 > app.yaml
	m4 -DSTAGING < module-besearch.yaml.m4 > module-besearch.yaml
	m4 -DSTAGING < module-latency-insensitive.yaml.m4 > module-latency-insensitive.yaml

config_dev:
	m4 -DDEV < app.yaml.m4 > app.yaml
	m4 -DDEV < module-besearch.yaml.m4 > module-besearch.yaml
	m4 -DDEV < module-latency-insensitive.yaml.m4 > module-latency-insensitive.yaml

config_local:
	m4 app.yaml.m4 > app.yaml
	m4 module-besearch.yaml.m4 > module-besearch.yaml
	m4 module-latency-insensitive.yaml.m4 > module-latency-insensitive.yaml

deploy_dev: clean_deps deps build_js config_dev
	$(eval BRANCH_NAME := $(shell git rev-parse --abbrev-ref HEAD))
	@echo "---[Dev $(DEVID)]---"
	$(GAE_PY) upload --tag $(BRANCH_NAME) -A $(DEVID) $(FRONTEND_MODULES) $(BACKEND_MODULES)

deploy_cloud_dev: clean_deps deps build_js config
	$(eval GCB_DIR:= $(shell mktemp -d -p /tmp monorail_XXXXX))
	rsync -aLK . $(GCB_DIR)  # Dereferences symlinks before snapshotting.
	cd $(GCB_DIR) && tar cf ${_VERSION}.tar .
	gsutil cp $(GCB_DIR)/${_VERSION}.tar gs://chrome-infra-builds/monorail/dev
	rm -rf $(GCB_DIR)


deploy: 
ifeq ($(SPIN),)
	$(error "please install spin go/chops-install-spin")
endif
	$(SPIN) pipeline execute --name "Deploy Monorail" --application monorail
	@echo "Follow progress here: https://spinnaker-1.endpoints.chrome-infra-spinnaker.cloud.goog/#/applications/monorail/executions"

external_deps: clean_deps deps build_js config

package_release:
	rsync -aLK . $(TARDIR)/package



lsbuilds:
	gcloud builds list --filter="tags='monorail'"

# AppEngine apps can be tested locally and in non-default versions upload to
# the main app-id, but it is still sometimes useful to have a completely
# separate app-id.  E.g., for testing inbound email, load testing, or using
# throwaway databases.
deploy_staging: clean_deps deps build_js config_staging
	@echo "---[Staging $(STAGEID)]---"
	$(GAE_PY) upload -A $(STAGEID) $(FRONTEND_MODULES) $(BACKEND_MODULES)

# This is our production server that users actually use.
deploy_prod: clean_deps deps build_js config_prod
	@echo "---[Deploying prod instance $(PRODID)]---"
	$(GAE_PY) upload -A $(PRODID) $(FRONTEND_MODULES) $(BACKEND_MODULES)

# Note that we do not provide a command-line way to make the newly-uploaded
# version the default version. This is for two reasons: a) You should be using
# your browser to confirm that the new version works anyway, so just use the
# console interface to make it the default; and b) If you really want to use
# the command line you can use gae.py directly.
