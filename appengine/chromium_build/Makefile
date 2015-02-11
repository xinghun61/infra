# Makefile to simplify some common AppEngine actions.
# Use 'make help' for a list of commands.

# Helper code to detect SDK location
define DETECT_SDK
import os
locations = [
  "../../../google_appengine", # For fetch-based checkouts.
  "../google_appengine",
  "/usr/local/google_appengine",
  ".locally/google_appengine",
]
for path in locations:
  if os.path.exists(path):
    print(path)
    break
endef
# /Helper

APPID?= `cat app.yaml | sed -n 's/^application: *//p'`
STAGEID= $(APPID)-staging

SDK_PATH ?= $(shell python -c '$(DETECT_SDK)')

DEV_APPSERVER?= $(if $(SDK_PATH), $(SDK_PATH)/,)dev_appserver.py
DEV_APPSERVER_FLAGS?=

APPCFG?= $(if $(SDK_PATH), $(SDK_PATH)/,)appcfg.py
APPCFG_FLAGS?=

# Set dirty suffix depending on output of "git status".
dirty=
ifneq ($(shell git status --porcelain),)
        dirty="-tainted"
endif
VERSION_TAG= `git show --format='%h' --no-patch`$(dirty)
# AppEngine version cannot use ':' in its name so use a '-' instead.
VERSION?= `git show --format='%h' --no-patch`$(dirty)

PYTHON?= python2.7

NPM_VERSION := $(shell npm --version 2>/dev/null)
# APP_VERSIONS := $(shell $(APPCFG) $(APPCFG_FLAGS) list_versions . 2>/dev/null 1>&2)
APP_VERSIONS := $(shell $(APPCFG) $(APPCFG_FLAGS) list_versions -q . 2>/dev/null 0</dev/null)

default: help

# TODO(???): Nice to have: test that appcfg.py list_versions fails and tell the
#            how to get a credential.
# verify_permission:
# ifndef APP_VERSIONS
# 	$(error \"$(APPCFG) $(APPCFG_FLAGS list_versions .\" failed.  Please run with \"$(APPCFG) $(APPCFG_FLAGS) list_versions . --noauth_local_webserver\" and try again.)
# endif

help:
	@echo "Available commands:"
	@sed -n '/^[a-zA-Z0-9_.]*:/s/:.*//p' <Makefile | sort

run: serve

update_revision:
	@echo "---[Updating REVISION]---"
	@echo "$(VERSION_TAG)" >REVISION

serve: update_revision
	@echo "---[Starting SDK AppEngine Server]---"
	$(DEV_APPSERVER) $(DEV_APPSERVER_FLAGS) .

serve_remote: update_revision
	$(DEV_APPSERVER) $(DEV_APPSERVER_FLAGS) --host 0.0.0.0  --admin_host 0.0.0.0 .

update: update_revision
	@echo "---[Updating $(APPID)]---"
	$(APPCFG) $(APPCFG_FLAGS) update . --application $(APPID) --version $(VERSION)

upload: update

deploy: update

update_indexes:
	$(APPCFG) $(APPCFG_FLAGS) update_indexes . --application $(APPID)

vacuum_indexes:
	$(APPCFG) $(APPCFG_FLAGS) vacuum_indexes . --application $(APPID)

# This target should only be run from within appengine/chromium_build/.
test:
	../../test.py test appengine/chromium_build

# AppEngine apps can be tested locally and in non-default versions upload to
# the main app-id, but it is still sometimes useful to have a completely
# separate app-id.  E.g., for testing inbound email, load testing, or something
# that might clutter the real datastore.
stage: update_revision
	@echo "---[Staging $(STAGEID)]---"
	$(APPCFG) $(APPCFG_FLAGS) update . --application $(STAGEID) --version $(VERSION)

stage_indexes:
	$(APPCFG) $(APPCFG_FLAGS) update_indexes . --application $(STAGEID)
