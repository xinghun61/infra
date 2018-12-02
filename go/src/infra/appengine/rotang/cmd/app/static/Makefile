help:
	@echo "Available commands:"
	@sed -n '/^[a-zA-Z0-9_]*:/s/:.*//p' <Makefile

deps:
	npm install

build: deps
	npx webpack

clean:
	rm dist/bundle.js
