.PHONY: test
VULCANIZE_PATH = ./node_modules/vulcanize/bin/vulcanize
WCT_DIR = ../../../tools/wct
WCT_GO = $(WCT_DIR)/wct.go $(WCT_DIR)/loader.go
default: help

help:
	@echo "Available commands:"
	@sed -n '/^[a-zA-Z0-9_]*:/s/:.*//p' <Makefile

node_deps:
	npm ci

bower_deps: node_deps
	npx bower install

format:
	clang-format -i elements/**/*.js -style=file

lint:
	polylint -i elements/som-app/som-app.html

build: bower_deps
	$(VULCANIZE_PATH) elements/som-app/som-app.html -o elements/som-app/som-app.vulcanized.html --inline-scripts

clean:
	rm elements/som-app/som-app.vulcanized.html

wct: bower_deps
	npx run-wct

wct_debug: bower_deps
	npx run-wct --debug
