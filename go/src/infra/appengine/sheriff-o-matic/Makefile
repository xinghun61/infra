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
	clang-format -i elements/**/*.js -style=file

build: deps
	vulcanize elements/som-app/som-app.html -o elements/som-app/som-app.vulcanized.html

clean:
	rm elements/som-app/som-app.vulcanized.html

test: deps
	cd som && go test
	xvfb-run -a $(WCT_PATH)

relnotes:
	go run ../../tools/relnotes/relnotes.go -app sheriff-o-matic

# This is only used for testing on the continuous build system.
bower-cipd: deps
	cipd create -pkg-def ../../../../../build/packages/sheriff-o-matic.yaml -pkg-var platform:linux-amd64

# In the future we can add different commends for prod and staging.
deploy-prod: build
	./gae.py upload -A sheriff-o-matic
	rm elements/som-app.vulcanized.html

deploy: build
	./gae.py upload
	rm elements/som-app.vulcanized.html
