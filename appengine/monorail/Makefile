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
BACKEND_MODULES?= besearch

default: help

check:
ifndef NPM_VERSION
	$(error npm not found. Install from nodejs.org or see README)
endif

help:
	@echo "Available commands:"
	@sed -n '/^[a-zA-Z0-9_.]*:/s/:.*//p' <Makefile

test:
	../../test.py test appengine/monorail

test_no_coverage:
	../../test.py test appengine/monorail --no-coverage

# Commands for running locally using dev_appserver.
serve:
	@echo "---[Starting SDK AppEngine Server]---"
	$(GAE_PY) devserver -- $(DEV_APPSERVER_FLAGS)

serve_email:
	@echo "---[Starting SDK AppEngine Server]---"
	$(GAE_PY) devserver -- $(DEV_APPSERVER_FLAGS) --enable_sendmail=True

# The _remote commands expose the app on 0.0.0.0, so that it is externally
# accessible by hostname:port, rather than just localhost:port.
serve_remote:
	@echo "---[Starting SDK AppEngine Server]---"
	$(GAE_PY) devserver -o -- $(DEV_APPSERVER_FLAGS)

serve_remote_email:
	@echo "---[Starting SDK AppEngine Server]---"
	$(GAE_PY) devserver -o -- $(DEV_APPSERVER_FLAGS) --enable_sendmail=True

run: serve


# AppEngine apps can be tested locally and in non-default versions upload to
# the main app-id, but it is still sometimes useful to have a completely
# separate app-id.  E.g., for testing inbound email, load testing, or using
# throwaway databases.
deploy_staging:
	@echo "---[Staging $(STAGEID)]---"
	$(GAE_PY) upload -A $(STAGEID) $(FRONTEND_MODULES) $(BACKEND_MODULES)


# This is our production server that users actually use.
deploy_prod:
	@echo "---[Deploying prod instance $(PRODID)]---"
	$(GAE_PY) upload -A $(PRODID) $(FRONTEND_MODULES) $(BACKEND_MODULES)


# Note that we do not provide a command-line way to make the newly-uploaded
# version the default version. This is for two reasons: a) You should be using
# your browser to confirm that the new version works anyway, so just use the
# console interface to make it the default; and b) If you really want to use
# the command line you can use gae.py directly.
