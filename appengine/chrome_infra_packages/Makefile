.PHONY: test
APP_DIR := $(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))
NODE_DIR := ${APP_DIR}/../../node

default: help

help:
	@echo "Available commands:"
	@sed -n '/^[a-zA-Z0-9_]*:/s/:.*//p' <Makefile

setup:
	${NODE_DIR}/npm.py install --save vulcanize@1.10.4

clean:
	rm -f ${APP_DIR}/static/html/*-vulcanized.html

build:
	${NODE_DIR}/node.py ${APP_DIR}/node_modules/vulcanize/bin/vulcanize \
		--inline-css --inline-scripts \
		${APP_DIR}/static/html/index.html > \
		${APP_DIR}/static/html/index-vulcanized.html

devserver: clean
	${APP_DIR}/tools/gae devserver

deploy_staging:	build
	${APP_DIR}/tools/gae upload -A chrome-infra-packages-dev
	rm -f ${APP_DIR}/static/html/*-vulcanized.html

deploy_prod:	build
	${APP_DIR}/tools/gae upload -A chrome-infra-packages
	rm -f ${APP_DIR}/static/html/*-vulcanized.html

test:
	${APP_DIR}/tools/run_tests.sh
