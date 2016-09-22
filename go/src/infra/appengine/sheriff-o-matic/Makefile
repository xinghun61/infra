.PHONY: test
WCT_PATH = ./node_modules/web-component-tester/bin/wct

default: help

help:
	@echo "Available commands:"
	@sed -n '/^[a-zA-Z0-9_]*:/s/:.*//p' <Makefile

deps:
	bower install
	npm install

build: deps
	vulcanize elements/som-app.html -o elements/som-app.vulcanized.html

clean:
	rm elements/som-app.vulcanized.html

test: deps
	go test
	xvfb-run -a $(WCT_PATH)


# In the future we can add different commends for prod and staging.
deploy-prod: build
	./gae.py upload -A sheriff-o-matic
	rm elements/som-app.vulcanized.html

deploy: build
	./gae.py upload
	rm elements/som-app.vulcanized.html
