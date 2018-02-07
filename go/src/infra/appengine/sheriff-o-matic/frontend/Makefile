.PHONY: test
WCT_PATH = ./node_modules/web-component-tester/bin/wct
VULCANIZE_PATH = ./node_modules/vulcanize/bin/vulcanize
# TODO: Make install this via CIPD
CHROMEDRIVER_PATH = /usr/local/google/home/$$USER/Downloads/chromedriver
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

CHROMEDRIVER_INSTALLED := $(shell command -v $(CHROMEDRIVER_PATH) 2> /dev/null)
chromedriver_check:
ifndef CHROMEDRIVER_INSTALLED
	@echo "Please install chromedriver from https://sites.google.com/a/chromium.org/chromedriver/downloads" && false
endif


wct: chromedriver_check deps
	xvfb-run go run ../../../tools/wct/wct.go -base=. -chromedriver=$(CHROMEDRIVER_PATH)
