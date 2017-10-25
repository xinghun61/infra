.PHONY: test
WCT_PATH = ./node_modules/web-component-tester/bin/wct
VULCANIZE_PATH = ./node_modules/vulcanize/bin/vulcanize

default: help

help:
	@echo "Available commands:"
	@sed -n '/^[a-zA-Z0-9_]*:/s/:.*//p' <Makefile

build: deps
	$(VULCANIZE_PATH) elements/who-page.html -o elements/who-page.vulcanized.html --inline-scripts

clean:
	rm elements/who-page.vulcanized.html

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

deploy_prod: build getversion deploy_prod_run clean

deploy_prod_run:
	appcfg.py -A chromium-who -V ${VERS} update app.yaml

devserver:
	./gae.py devserver
