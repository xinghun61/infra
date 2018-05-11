.PHONY: test
VULCANIZE_PATH = ./node_modules/vulcanize/bin/vulcanize
default: help

help:
	@echo "Available commands:"
	@sed -n '/^[a-zA-Z0-9_]*:/s/:.*//p' <Makefile

deps:
	npm install
	bower install

format:
	clang-format -i elements/**/*.js -style=file

lint:
	polylint -i elements/som-app/som-app.html

build: deps
	$(VULCANIZE_PATH) elements/som-app/som-app.html -o elements/som-app/som-app.vulcanized.html --inline-scripts

clean:
	rm elements/som-app/som-app.vulcanized.html

wct: deps
	xvfb-run go run ../../../tools/wct/wct.go ../../../tools/wct/monkeypatch.go -base=. -chrome=google-chrome

wct_debug: deps
	go run ../../../tools/wct/wct.go ../../../tools/wct/monkeypatch.go -base=. -chrome=google-chrome -persist
