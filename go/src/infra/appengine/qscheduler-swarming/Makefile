# Copyright 2018 The LUCI Authors. All rights reserved.
# Use of this source code is governed under the Apache License, Version 2.0
# that can be found in the LICENSE file.

mkfile_path := $(abspath $(lastword $(MAKEFILE_LIST)))
projdir := $(patsubst %/,%,$(dir $(mkfile_path)))

dev:
	gae.py devserver -A dev --app-dir $(projdir)/app/appengine -- --host 0.0.0.0 --port 8082 --admin_port 7999 --log_level debug

up-dev:
	gae.py upload -A qscheduler-swarming-dev --app-dir $(projdir)/app/appengine

up-prod:
	gae.py upload -A qscheduler-swarming --app-dir $(projdir)/app/appengine

test:
	go test ./...

gen:
	go generate ./...

run-local:
	go run $(projdir)/cmd/qscheduler-swarming/main.go \
		-qscheduler-config $(projdir)/app/appengine/devcfg/services/dev/config.cfg \
		-http-addr "0.0.0.0:8082" \
		-admin-addr "0.0.0.0:8900"
