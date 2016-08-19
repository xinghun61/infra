.PHONY: test

default: help

help:
	@echo "Available commands:"
	@sed -n '/^[a-zA-Z0-9_]*:/s/:.*//p' <Makefile

build:
	vulcanize elements/som-app.html -o elements/som-app.vulcanized.html

clean:
	rm elements/som-app.vulcanized.html

# In the future we can add different commends for prod and staging.
deploy:
	vulcanize elements/som-app.html -o elements/som-app.vulcanized.html
	./gae.py upload
	rm elements/som-app.vulcanized.html
