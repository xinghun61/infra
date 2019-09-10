# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

INFRAPYTHON := "../../ENV/bin/python"
GAE_PY := "gae.py"
APPID := "findit-for-me"
STAGING_APPID := "findit-for-me-staging"
# Should come with infra repository, if this step fails run
# ...$ gclient sync
PROTOC := "../../cipd/protoc"
PROTO_PATH ?= "model/proto/"
FINDIT_MODULES := default frontend waterfall-backend flake-detection-backend disabled-test-detection-backend auto-action-backend findit-backend
CODE_COVERAGE_MODULES := code-coverage-frontend code-coverage-backend
LOCAL_VERSION := `$(INFRAPYTHON) $(GAE_PY) version`
LOCAL_HASH := `git rev-parse --short HEAD`
# If there are multiple active versions just use the latest one.
REMOTE_FINDIT_VERSION := `$(INFRAPYTHON) $(GAE_PY) active -A $(APPID) | grep "default:" | awk '{print $$2}'`
REMOTE_FINDIT_HASH := `$(INFRAPYTHON) $(GAE_PY) active -A $(APPID) | grep "default:" | awk '{print $$2}' | cut -d '-' -f2`
REMOTE_COVERAGE_VERSION := `$(INFRAPYTHON) $(GAE_PY) active -b -A $(APPID) | grep "code-coverage-backend:" | awk '{print $$2}'`
REMOTE_COVERAGE_HASH := `$(INFRAPYTHON) $(GAE_PY) active -b -A $(APPID) | grep "code-coverage-backend:" | awk '{print $$2}' | cut -d '-' -f2`
TEST_GLOB ?= ""

help:
	@echo "Findit:"
	@echo "To deploy a new version of Findit, check out the appropriate" \
	      "revision and run \`gclient sync\` then run" \
	      "\`make deploy-findit-prod\` for production or \`make deploy-findit-staging\`"\
	      "for staging."
	@echo "To set the newly version as default or revert to a previous one, " \
	      "please migrate traffic for modules: $(FINDIT_MODULES)"
	@echo "https://pantheon.corp.google.com/appengine/versions?project=findit-for-me"
	@echo
	@echo "Code Coverage:"
	@echo "To deploy a new version of Code Coverage, check out the appropriate" \
	      "revision and run \`gclient sync\` then run" \
	      "\`make deploy-coverage-prod\` for production or \`make deploy-coverage-staging\`"\
	      "for staging."
	@echo "To set the newly version as default or revert to a previous one, " \
	      "please migrate traffic for modules: $(CODE_COVERAGE_MODULES)"
	@echo "https://pantheon.corp.google.com/appengine/versions?project=findit-for-me"
	@echo
	@echo "Run tests"
	@echo "To run ALL tests: \`make test\`"
	@echo "To run tests in a sub directory: \`make test TEST_GLOB=services\`"
	@echo "To run a given test: \`make test TEST_GLOB=:*testUnrecognizedMasterUrl*\`"
	@echo
	@echo "To format code use \`make format\`"
	@echo "To run all modules locally use \`make run\`"


##### App Engine ###
findit-predeploy:
	@echo "Uncommitted local changes (Commit, revert or delete):"
	@git status --porcelain
	@echo
	@echo "Changes in local branch. (Upload/land/pull/switch to master to avoid deploying tainted version)"
	@git log origin/master..HEAD --pretty=oneline .
	@echo
	@echo "Deployable Changes. (git pull and client sync if not current)"
	@git log $(REMOTE_FINDIT_HASH)..HEAD --pretty=oneline .

deploy-all-prod: deploy-findit-prod deploy-coverage-prod
	@echo "Both Findit and Code Coverage were deployed to production."

deploy-all-staging: deploy-findit-staging deploy-coverage-staging
	@echo "Both Findit and Code Coverage were deployed to staging."

deploy-findit-prod: test
	@$(INFRAPYTHON) $(GAE_PY) upload -A $(APPID) $(FINDIT_MODULES);
	@echo "New version '$(LOCAL_VERSION)' of Findit was" \
	      "deployed to $(APPID)."
	@echo
	@echo "Please force a re-run of a recent build failure on dashboard: "\
	"https://$(LOCAL_VERSION)-dot-frontend-"\
	"dot-$(APPID).appspot.com/waterfall/list-failures"
	@echo "Choose a first failure to make sure a new try job is triggered."
	@echo "Please also force a re-run of a recent flake analysis on dashboard: "\
	"https://$(LOCAL_VERSION)-dot-frontend-"\
	"dot-$(APPID).appspot.com/p/chromium/flake-portal/analysis"
	@echo "Ensure that the analyses are run in the new versions and give " \
	      "correct results, " \
	      "and then set the new version as default for these modules " \
	      "$(FINDIT_MODULES)."
	@echo
	@echo "If the release is for production, please email" \
	      "chrome-findit@ with the following:"
	@echo "Subject: "$(LOCAL_VERSION)" deployed for Findit"

	@echo "Hi all,"
	@echo
	@echo "$(LOCAL_VERSION) was deployed to Findit. Previous version is " \
	      "$(REMOTE_FINDIT_VERSION)"
	@echo "Changelogs:"
	@echo "https://chromium.googlesource.com/infra/infra/+log/"\
	"$(REMOTE_FINDIT_HASH)..$(LOCAL_HASH)/appengine/findit?pretty=fuller"
	@echo
	@echo "If your bug fixes/features are included in the release," \
	      "please verify on ${app_id} and mark them as verified on" \
	      "http://crbug.com"
	@echo
	@echo "Thanks,"
	@echo "Released by $(USER)@"

deploy-findit-staging: test
	@$(INFRAPYTHON) $(GAE_PY) upload -A $(STAGING_APPID) $(FINDIT_MODULES);

deploy-coverage-prod: test
	@$(INFRAPYTHON) $(GAE_PY) upload -A $(APPID) $(CODE_COVERAGE_MODULES);
	@echo "New version is https://$(LOCAL_VERSION)-dot-code-coverage-frontend-"\
	"dot-$(APPID).appspot.com/p/chromium/coverage"

deploy-coverage-staging: test
	@$(INFRAPYTHON) $(GAE_PY) upload -A $(STAGING_APPID) $(CODE_COVERAGE_MODULES);
	@echo "New version is https://$(LOCAL_VERSION)-dot-code-coverage-frontend-"\
	"dot-$(STAGING_APPID).appspot.com/p/chromium/coverage"

migrate:
	@echo "Please use the Google Cloud Console to migrate traffic to new versions"
	      "https://pantheon.corp.google.com/appengine/versions?project=findit-for-me"
	@echo
	@echo "Findit modules: $(FINDIT_MODULES)"
	@echo "Code Coverage modules: $(CODE_COVERAGE_MODULES)"


##### Development ###
run:
	$(INFRAPYTHON) $(GAE_PY) devserver

YAPF := $(shell command -v yapf 2> /dev/null)
format:
ifndef YAPF
	@echo "Please install yapf first: https://github.com/google/yapf." && false
endif
	git cl format --full --python

proto:
	@$(PROTOC) --proto_path=$(PROTO_PATH) \
		--python_out=$(PROTO_PATH)gen \
		$(PROTO_PATH)*.proto



##### Unit tests ###
clean-expect_tests:  # $$ is to escape $ in makefile.
	ps auxef | grep ENV/bin/expect_tests | grep -v grep | \
	  awk '{print $$2}' | xargs kill -9 >/dev/null 2>&1 | echo

test: clean-expect_tests
ifeq ($(TEST_GLOB),"")
	@mkdir -p $(TMPDIR)/coverage
	$(INFRAPYTHON) ../../test.py test appengine/findit \
      --html-report $(TMPDIR)/coverage
else
	@echo "Note: code coverage disabled when running selected tests."
	@echo
	@mkdir -p $(TMPDIR)/coverage
	$(INFRAPYTHON) ../../test.py test appengine/findit/$(TEST_GLOB) \
      --html-report $(TMPDIR)/coverage --coveragerc appengine/findit/.coveragerc --no-coverage
endif

node_deps:
	npm install

wct: node_deps
	npx run-wct --base ui/ --dep third_party

wct_debug: node_deps
	npx run-wct --base ui/ --dep third_party --debug

##### TMP ###
TMPDIR := $(shell mkdir -p .tmp 2> /dev/null && realpath .tmp)
ifndef TMPDIR
TMPDIR :=  $(shell mktemp -d)
endif

.PHONY: _deploy_findit test update \
        help migrate deploy-findit-prod deploy-findit-staging \
        deploy-coverage-prod deploy-coverage-staging findit-predeploy \
        deploy-all-prod deploy-all-staging
