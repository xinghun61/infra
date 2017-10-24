# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

# Makefile to simplify some common AppEngine actions.
# Use 'make help' for a list of commands.

PRODID= crbadge

GAE_PY?= python gae.py
DEV_APPSERVER_FLAGS?=

FRONTEND_MODULES?= default

default: help

help:
	@echo "Available commands:"
	@sed -n '/^[a-zA-Z0-9_.]*:/s/:.*//p' <Makefile

test:
	../../test.py test appengine/experimental/crbadge

# Commands for running locally using dev_appserver.
serve:
	@echo "---[Starting SDK AppEngine Server]---"
	$(GAE_PY) devserver -- $(DEV_APPSERVER_FLAGS)

# This is our production server that users actually use.
deploy_prod:
	@echo "---[Deploying prod instance $(PRODID)]---"
	$(GAE_PY) upload -A $(PRODID) default


# Note that we do not provide a command-line way to make the newly-uploaded
# version the default version. This is for two reasons: a) You should be using
# your browser to confirm that the new version works anyway, so just use the
# console interface to make it the default; and b) If you really want to use
# the command line you can use gae.py directly.
