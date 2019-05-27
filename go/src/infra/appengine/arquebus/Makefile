# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed under the Apache License, Version 2.0
# that can be found in the LICENSE file.

mkfile_path := $(abspath $(lastword $(MAKEFILE_LIST)))
projdir := $(patsubst %/,%,$(dir $(mkfile_path)))

dev:
	gae.py devserver -A dev --app-dir $(projdir)/app -- \
		--host 0.0.0.0 --port 8082 --admin_port 7999 --log_level debug \
		--enable_console --enable_host_checking no --clear_datastore

#------------------------------------------------------------
# Arquebus PROD
deploy-prod: gen
	gae.py upload -A arquebus --app-dir $(projdir)/app

switch-prod:
	gae.py switch -A arquebus --app-dir $(projdir)/app

versions-cleanup-prod:
	gae.py cleanup -A arquebus --app-dir $(projdir)/app

#------------------------------------------------------------
# Arquebus STAGING
deploy-staging: gen
	gae.py upload -A arquebus-staging --app-dir $(projdir)/app

switch-staging:
	gae.py switch -A arquebus-staging --app-dir $(projdir)/app

versions-cleanup-staging:
	gae.py cleanup -A arquebus-staging --app-dir $(projdir)/app

test: gen
	go test ./...

gen:
	cproto app/config
	cproto app/backend
	cproto app/backend/model
	go generate ./...
