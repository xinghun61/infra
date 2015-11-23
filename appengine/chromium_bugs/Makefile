# Makefile to simplify some common AppEngine actions.
# Use 'make help' for a list of commands.

APPID?= `cat app.yaml | sed -n 's/^application: *//p'`

GAE_PY?= python gae.py
DEV_APPSERVER_FLAGS?=

MODULES?= default

default: help

help:
	@echo "Available commands:"
	@sed -n '/^[a-zA-Z0-9_.]*:/s/:.*//p' <Makefile

test:
	../../test.py test appengine/chromium_bugs

# Commands for running locally using dev_appserver.
serve:
	@echo "---[Starting SDK AppEngine Server]---"
	$(GAE_PY) devserver $(DEV_APPSERVER_FLAGS)

# The _remote commands expose the app on 0.0.0.0, so that it is externally
# accessible by hostname:port, rather than just localhost:port.
serve_remote:
	@echo "---[Starting SDK AppEngine Server]---"
	$(GAE_PY) devserver -o $(DEV_APPSERVER_FLAGS)

run: serve


# This is our production server that users actually use.
deploy_prod:
	@echo "---[Deploying prod instance $(APPID)]---"
	$(GAE_PY) upload -A $(APPID) $(MODULES)


# Note that we do not provide a command-line way to make the newly-uploaded
# version the default version. This is for two reasons: a) You should be using
# your browser to confirm that the new version works anyway, so just use the
# console interface to make it the default; and b) If you really want to use
# the command line you can use gae.py directly.
