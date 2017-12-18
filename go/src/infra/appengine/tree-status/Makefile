.PHONY: test
WCT_PATH = ./node_modules/web-component-tester/bin/wct
VULCANIZE_PATH = ./node_modules/vulcanize/bin/vulcanize

default: help

help:
	@echo "Available commands:"
	@sed -n '/^[a-zA-Z0-9_]*:/s/:.*//p' <Makefile

build: deps
	$(VULCANIZE_PATH) elements/ts-app/ts-app.html -o elements/ts-app/ts-app.vulcanized.html --inline-scripts

clean:
	rm elements/ts-app/ts-app.vulcanized.html

deps:
	bower install
	npm install

format:
	gofmt -s -w .

test: build
	go test --cover
	xvfb-run -a $(WCT_PATH)

deploy_prod: build deploy_prod_run clean

deploy_prod_run:
	gae.py upload -A tree-status

devserver:
	gae.py devserver -A tree-status
