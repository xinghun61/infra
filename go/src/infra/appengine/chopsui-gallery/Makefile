help:
	@echo "Available commands:"
	@sed -n '/^[a-zA-Z0-9_]*:/s/:.*//p' <Makefile

build:
	bower install
	cp -r bower_components/chops-ui/demo demo
	for f in demo/* ; do \
		sed -i 's/\.\.\/\.\.\//\/bower_components\//' $$f ; \
		sed -i 's/\.\./\/bower_components\/chops-ui/' $$f ; \
	done
	mkdir static
	cd bower_components/chops-ui/ && polymer analyze > ../../static/analysis.json

clean:
	rm -r demo
	rm -r static
