# Copyright 2018 The LUCI Authors. All rights reserved.
# Use of this source code is governed under the Apache License, Version 2.0
# that can be found in the LICENSE file.

mkfile_path := $(abspath $(lastword $(MAKEFILE_LIST)))
projdir := $(patsubst %/,%,$(dir $(mkfile_path)))

dev:
	gae.py devserver -A dev --app-dir $(projdir)/app/appengine -- --host 0.0.0.0 --port 8082 --admin_port 7999 --log_level debug

up-prod:
	gae.py upload -A chromeos-skylab-bot-fleet --app-dir $(projdir)/app/appengine

switch-prod:
	gae.py switch -A chromeos-skylab-bot-fleet --app-dir $(projdir)/app/appengine

versions-cleanup-prod:
	gae.py cleanup -A chromeos-skylab-bot-fleet --app-dir $(projdir)/app/appengine

up-staging:
	gae.py upload -A skylab-staging-bot-fleet --app-dir $(projdir)/app/appengine

switch-staging:
	gae.py switch -A skylab-staging-bot-fleet --app-dir $(projdir)/app/appengine

versions-cleanup-staging:
	gae.py cleanup -A skylab-staging-bot-fleet --app-dir $(projdir)/app/appengine

test:
	go test ./...

gen:
	go generate ./...
