.PHONY: test

default: help

help:
	@echo "Available commands:"
	@sed -n '/^[a-zA-Z0-9_]*:/s/:.*//p' <Makefile

generate:
	go generate ./...

build: generate format
	go build ./...

format:
	go fmt ./...

getversion:
	$(eval VERS := $(shell ../../../../../luci/appengine/components/tools/calculate_version.py | cut -c 1-35))
	echo version is $(VERS)

deploy_prod: getversion
	gcloud app deploy --promote --stop-previous-version frontend/app.yaml api/app.yaml dispatch.yaml --project test-trove --version $(VERS)
