WEBPACK_PATH := ./node_modules/webpack-cli/bin/cli.js
DEV_APPSERVER_FLAGS?=

deps:
	npm install --no-save
	mkdir -p deployed_node_modules/@webcomponents/webcomponentsjs/
	cp node_modules/@webcomponents/webcomponentsjs/webcomponents-bundle.js \
		deployed_node_modules/@webcomponents/webcomponentsjs/webcomponents-bundle.js

build_js:
	$(WEBPACK_PATH) --mode=production

clean_deps:
	rm -rf bower_components	
	rm -rf node_modules

serve: clean_deps deps
	gae.py devserver -- $(DEV_APPSERVER_FLAGS)& $(WEBPACK_PATH) --watch

deploy: clean_deps deps build_js
	gae.py upload -A chopsdash

node_deps:
	npm install

karma: node_deps
	npx karma start --debug --coverage



