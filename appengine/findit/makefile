# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

INFRAPYTHON := "../../ENV/bin/python"
GAE_PY := "gae.py"
APPID := "findit-for-me"
STAGING_APPID := "findit-for-me-staging"
MODULES := default waterfall-frontend waterfall-backend
LOCAL_VERSION := `$(INFRAPYTHON) $(GAE_PY) version`
LOCAL_HASH := `git rev-parse --short HEAD`
REMOTE_VERSION := `$(INFRAPYTHON) $(GAE_PY) active -b -A $(APPID)`
REMOTE_HASH := `python -c "print '$$($(INFRAPYTHON) $(GAE_PY) active -b -A $(APPID))'.split('-')[:2][-1]"`


help:
	@echo "To deploy a new version of findit, check out the appropriate" \
	      "revision and run \`gclient sync\` then run" \
	      "\`make deploy-prod\` for production or \`make deploy-staging\`"\
	      "for staging."
	@echo "To migrate the traffic to the newly deployed version use " \
	      "\`make migrate\`, this is only necessary for production."
	@echo "To revert to the previous version, use the command displayed " \
	      "by make when running the line above, or better yet, use the" \
	      "web interface to make the previous release default."
	@echo
	@echo "To format code use \`make format\`"
	@echo "To run tests use \`make test\`"
	@echo "To run findit locally use \`make run\`, if needed, run " \
	      "\`make polymer-install\` first."


##### App Engine ###
deploy-prod: _deploy
	@echo "New version '$(LOCAL_VERSION)' of Findit was" \
	      "deployed to $(APPID)."
	@echo
	@echo "Please force a re-run of a recent build failure on dashboard: "\
	"https://$(LOCAL_VERSION)-dot-waterfall-frontend-"\
	"dot-$(APPID).appspot.com/waterfall/list-analyses"
	@echo "Please also force a re-run of a recent flake analysis on dashboard: "\
	"https://$(LOCAL_VERSION)-dot-waterfall-frontend-"\
	"dot-$(APPID).appspot.com/waterfall/list-flakes"
	@echo "ensure that the analyses are run in the new-version waterfall" \
	      "frontend & backend and gives correct results,"
	@echo "and then set the new version as default for three modules" \
	      "default, waterfall-frontend and waterfall-backend."
	@echo "You can do this by running \`make migrate\`"
	@echo
	@echo "If the release is for findit-for-me, please email" \
	      "chrome-findit with the following:"
	@echo "Subject: Release: findit-for-me updated to" \
	      "$(LOCAL_VERSION)"
	@echo "Hi all,"
	@echo
	@echo "The app findit-for-me was updated from" \
	      "$(REMOTE_VERSION) to $(LOCAL_VERSION)"
	@echo "Changelogs:"
	@echo "https://chromium.googlesource.com/infra/infra/+log/"\
	"$(REMOTE_HASH)..$(LOCAL_HASH)"\
	"/appengine/findit"
	@echo
	@echo "If your bug fixes/features are included in the release," \
	      "please verify on ${app_id} and mark them as verified on" \
	      "http://crbug.com"
	@echo
	@echo "Thanks,"
	@echo "Released by $(USER)@"

deploy-staging: test polymer-check
	@$(INFRAPYTHON) $(GAE_PY) upload -A --switch $(STAGING_APPID);

_deploy: test polymer-check
	@$(INFRAPYTHON) $(GAE_PY) upload -A $(APPID);

migrate:
	@echo "To revert to the previous version run the following command:"
	@echo "\`$(INFRAPYTHON) $(GAE_PY) switch -A $(APPID) " \
	"$(REMOTE_VERSION) \`"
	$(INFRAPYTHON) $(GAE_PY) switch -A $(APPID)


##### Development ###
run:
	$(INFRAPYTHON) $(GAE_PY) devserver

YAPF := $(shell command -v yapf 2> /dev/null)
format:
ifndef YAPF
	@echo "Please install yapf first: https://github.com/google/yapf." && false
endif
	git cl format --full --python



##### Unit tests ###
test:
	@mkdir -p $(TMPDIR)/coverage
	$(INFRAPYTHON) ../../test.py test appengine/findit \
	  --html-report $(TMPDIR)/coverage


##### POLYMER ###
# TODO(crbug.com/743146): Use versioned polymer.
polymer-check: polymer-install
	@set -e
	@if [ ! -d third_party/bower_components ]; then \
	false; \
	fi

NPM := $(shell command -v npm 2> /dev/null)
BOWER := $(shell command -v bower 2> /dev/null)

polymer-install: clean
ifndef NPM
	@echo "Please install npm with " \
	      "\`sudo apt-get install nodejs-legacy npm\`" && false
endif
ifndef BOWER
	npm install -g bower
endif
	cd third_party && bower install

clean:
	@-rm -rf third_party/bower_components


##### TMP ###
TMPDIR := $(shell mkdir -p .tmp 2> /dev/null && realpath .tmp)
ifndef TMPDIR
TMPDIR :=  $(shell mktemp -d)
endif

.PHONY: _deploy test polymer-install update clean polymer-check \
        help migrate deploy-prod deploy-staging
