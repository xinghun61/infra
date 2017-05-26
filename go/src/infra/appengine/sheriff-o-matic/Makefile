.PHONY: test
WCT_PATH = ./node_modules/web-component-tester/bin/wct
VULCANIZE_PATH = ./node_modules/vulcanize/bin/vulcanize

default: help

help:
	@echo "Available commands:"
	@sed -n '/^[a-zA-Z0-9_]*:/s/:.*//p' <Makefile

build:
	cd frontend && make build

clean:
	cd frontend && make clean

format:
	gofmt -s -w .
	cd frontend && make format

test: build
	cd som && go test --cover
	cd frontend && make test

relnotes:
	go run ../../tools/relnotes/relnotes.go -app sheriff-o-matic . ../../monitoring/analyzer ../../monitoring/client ../../monitoring/messages

# This is only used for testing on the continuous build system.
bower-cipd: deps
	cipd pkg-build -pkg-def ./cipd/sheriff-o-matic.yaml -pkg-var platform:linux-amd64 -out ./cipd/bower_components.cipd
	cipd pkg-register ./cipd/bower_components.cipd

# In the future we can add different commends for prod and staging.
deploy-prod: build
	./gae.py upload -A sheriff-o-matic
	rm frontend/elements/som-app/som-app.vulcanized.html

deploy: build
	./gae.py upload
	rm frontend/elements/som-app/som-app.vulcanized.html
