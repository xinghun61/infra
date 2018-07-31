default: help

help:
	@echo "Available commands:"
	@sed -n '/^[a-zA-Z0-9_]*:/s/:.*//p' <Makefile

devserver:
	dev_appserver.py cmd/app/app.yaml

devserver-remote:
	dev_appserver.py --host 0.0.0.0 --enable_host_checking no cmd/app/app.yaml
