.PHONY: test
WCT_PATH = ./node_modules/web-component-tester/bin/wct

default: help

help:
	@echo "Available commands:"
	@sed -n '/^[a-zA-Z0-9_]*:/s/:.*//p' <Makefile

deps:
	bower install
	npm install

format:
	gofmt -s -w .

getversion:
	$(eval VERS := $(shell ../../../../../luci/appengine/components/tools/calculate_version.py | cut -c 1-35))
	echo version is $(VERS)

test: build
	go test --cover
	xvfb-run -a $(WCT_PATH)

deploy_prod: getversion deploy_prod_run

deploy_prod_run:
	./gae.py upload

devserver:
	./gae.py devserver
