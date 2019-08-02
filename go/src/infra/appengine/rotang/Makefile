default: help

help:
	@echo "Available commands:"
	@sed -n '/^[a-zA-Z0-9_]*:/s/:.*//p' <Makefile

protogen:
	go generate ./...

buildjs:
	cd cmd/app/static && make build

cleanjs:
	cd cmd/app/static && make clean

clean: cleanjs

devserver: buildjs protogen
	dev_appserver.py cmd/app/app_local.yaml

devserver-remote: buildjs protogen
	dev_appserver.py --host 0.0.0.0 --enable_host_checking no cmd/app/app_local.yaml

deploy-staging: buildjs protogen
	gcloud app deploy cmd/app/app_staging.yaml --project rota-ng-staging

deploy-prod: buildjs protogen
	gcloud app deploy cmd/app/app_prod.yaml  --project rota-ng
