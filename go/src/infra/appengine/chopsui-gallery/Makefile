help:
	@echo "Available commands:"
	@sed -n '/^[a-zA-Z0-9_]*:/s/:.*//p' <Makefile

build: clean
	bower install

	cp -r bower_components/chopsui/demo demo
	for f in demo/* ; do \
		sed -i 's/\.\.\/\.\.\//\/bower_components\//' $$f ; \
		sed -i 's/\.\./\/bower_components\/chopsui/' $$f ; \
	done
	mkdir static
	cd bower_components/chopsui/ && polymer analyze > ../../static/analysis.json

clean:
	rm -r demo || true
	rm -r static || true

deploy_prod: build deploy_prod_run clean

deploy_prod_run:
	gae.py upload -A chopsui-gallery

devserver: build
	gae.py devserver -A chopsui-gallery
