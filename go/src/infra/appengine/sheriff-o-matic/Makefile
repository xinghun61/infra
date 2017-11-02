.PHONY: test
WCT_PATH = ./node_modules/web-component-tester/bin/wct
VULCANIZE_PATH = ./node_modules/vulcanize/bin/vulcanize

default: help

help:
	@echo "Available commands:"
	@sed -n '/^[a-zA-Z0-9_]*:/s/:.*//p' <Makefile

build:
	cd frontend && make build
	cd som/model && go generate

clean:
	cd frontend && make clean

format:
	gofmt -s -w .
	cd frontend && make format

test: build
	cd som && go test ... --cover
	cd frontend && make test

relnotes:
	go run ../../tools/relnotes/relnotes.go -app sheriff-o-matic . ../../monitoring/analyzer ../../monitoring/client ../../monitoring/messages

# This is only used for testing on the continuous build system.
bower_cipd: deps
	cipd pkg-build -pkg-def ./cipd/sheriff-o-matic.yaml -pkg-var platform:linux-amd64 -out ./cipd/bower_components.cipd
	cipd pkg-register ./cipd/bower_components.cipd

getversion:
	$(eval VERS := $(shell ../../../../../luci/appengine/components/tools/calculate_version.py | cut -c 1-35))
	echo version is $(VERS)

deploy_prod: build getversion
	gcloud app deploy --no-promote --no-stop-previous-version frontend/app.yaml backend/app.yaml dispatch.yaml cron.yaml frontend/queue.yaml --project sheriff-o-matic --version $(VERS)
	rm frontend/elements/som-app/som-app.vulcanized.html

bqtools:
	go install go.chromium.org/luci/tools/cmd/bqschemaupdater

update_bq_staging: bqtools
	bqschemaupdater -proto-dir ./som/model/gen -table sheriff-o-matic-staging.events.alerts -message gen.SOMAlertsEvent
	bqschemaupdater -proto-dir ./som/model/gen -table sheriff-o-matic-staging.events.annotations -message gen.SOMAnnotationEvent

update_bq_prod: bqtools
	bqschemaupdater -proto-dir ./som/model/gen -table sheriff-o-matic.events.alerts -message gen.SOMAlertsEvent
	bqschemaupdater -proto-dir ./som/model/gen -table sheriff-o-matic.events.annotations -message gen.SOMAnnotationEvent

deploy_staging: build getversion
	gcloud app deploy --no-promote --no-stop-previous-version frontend/app.yaml backend/app.yaml dispatch.yaml cron.yaml frontend/queue.yaml --project sheriff-o-matic-staging --version $(VERS)
	rm frontend/elements/som-app/som-app.vulcanized.html

devserver:
	dev_appserver.py frontend/app.yaml backend/app.yaml

# The -remote commands expose the app on 0.0.0.0, so that it is externally
# accessible by hostname:port, rather than just localhost:port.
devserver_remote:
	dev_appserver.py --host 0.0.0.0 frontend/app.yaml backend/app.yaml
