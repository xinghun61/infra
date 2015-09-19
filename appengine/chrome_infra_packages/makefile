APP_DIR:=$(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))
NODE_DIR:=${APP_DIR}/../../node

setup:
	${NODE_DIR}/npm.py install --save vulcanize@1.10.4

clean:
	rm -f ${APP_DIR}/static/html/*-vulcanized.html

build:
	${NODE_DIR}/node.py ${APP_DIR}/node_modules/vulcanize/bin/vulcanize \
		--inline-css --inline-scripts \
		${APP_DIR}/static/html/index.html > \
		${APP_DIR}/static/html/index-vulcanized.html

deploy-staging:	build
	${APP_DIR}/tools/gae upload -A chrome-infra-packages-dev
	rm -f ${APP_DIR}/static/html/*-vulcanized.html

deploy-prod:	build
	${APP_DIR}/tools/gae upload -A chrome-infra-packages
	rm -f ${APP_DIR}/static/html/*-vulcanized.html
