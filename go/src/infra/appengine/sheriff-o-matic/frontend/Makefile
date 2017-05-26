.PHONY: test
WCT_PATH = ./node_modules/web-component-tester/bin/wct
VULCANIZE_PATH = ./node_modules/vulcanize/bin/vulcanize

default: help

help:
	@echo "Available commands:"
	@sed -n '/^[a-zA-Z0-9_]*:/s/:.*//p' <Makefile

deps:
	bower install
	npm install

format:
	clang-format -i elements/**/*.js -style=file

lint:
	polylint -i elements/som-app/som-app.html

build: deps
	$(VULCANIZE_PATH) elements/som-app/som-app.html -o elements/som-app/som-app.vulcanized.html --inline-scripts

clean:
	rm elements/som-app/som-app.vulcanized.html

test: deps
	xvfb-run -a $(WCT_PATH)

