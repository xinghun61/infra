help:
	@echo "Available commands:"
	@sed -n '/^[a-zA-Z][a-zA-Z0-9_]*:/s/:.*//p' <Makefile

build: clean deps _build_docs

_build_docs:
	cp -r bower_components/chopsui/demo demo
	for f in demo/* ; do \
		sed -i 's/\.\.\/\.\.\//\/bower_components\//' $$f ; \
		sed -i 's/\.\./\/bower_components\/chopsui/' $$f ; \
	done
	mkdir static
	cd bower_components/chopsui/ && polymer analyze > ../../static/analysis.json

_build_dirty: clean deps _fetch_dirty _build_docs

_fetch_dirty:
	rm -r bower_components/chopsui/
	cp -r ../../../../../crdx/chopsui/ bower_components/chopsui

clean:
	rm -r demo || true
	rm -r static || true

deploy_demo: _build_dirty deploy_prod_run clean

deploy_prod: build deploy_prod_run clean

deploy_prod_run:
	gae.py upload -A chopsui-gallery

deps:
	rm -r bower_components || true
	bower install

devserver: build
	gae.py devserver -A chopsui-gallery
