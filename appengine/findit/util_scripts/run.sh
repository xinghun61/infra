#!/bin/bash
#
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# This script is to ease running Findit locally, running its unit tests, and
# deploying Findit to App Engine.

THIS_SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE:-$0}" )" && pwd )"
FINDIT_DIR="${THIS_SCRIPT_DIR}/.."
INFRA_DIR="${FINDIT_DIR}/../.."
GOOGLE_APP_ENGINE_DIR="${INFRA_DIR}/../google_appengine"
FINDIT_MODULES="${FINDIT_DIR}/app.yaml ${FINDIT_DIR}/build-failure-analysis.yaml"

if [[ -z "${APPENGINE_TMP}" ]]; then
  TMP_DIR="${FINDIT_DIR}/.tmp"
else
  TMP_DIR=${APPENGINE_TMP}
fi

print_usage() {
  echo
  echo "Usage:"
  echo "$0 <command>"
  echo
  echo "Supported commands:"
  echo "  test          Run the unittest"
  echo "  run           Run Findit locally"
  echo "  deploy-test   Deploy Findit to findit-for-waterfall"
  echo "  deploy-prod   Deploy Findit to findit-for-me"
  exit 1
}

run_unittests() {
  local coverage_report_dir="${TMP_DIR}/coverage"
  python ${INFRA_DIR}/test.py test --html-report ${coverage_report_dir} \
    appengine/findit
  echo "Code coverage report file://${coverage_report_dir}/index.html"
}

run_findit_locally() {
  local options="--storage_path ${TMP_DIR}/findit"
  python ${GOOGLE_APP_ENGINE_DIR}/dev_appserver.py ${options} ${FINDIT_MODULES}
}

deploy_findit() {
  local app_id="findit-for-waterfall"
  if [[ "$1" == "prod" ]]; then
    app_id="findit-for-me"
  fi

  local version="$(git rev-parse --short HEAD)"
  local app_cfg="${GOOGLE_APP_ENGINE_DIR}/appcfg.py"

  python ${app_cfg} update -A ${app_id} $FINDIT_MODULES --version ${version}
  echo "Findit(${version}) was deployed to ${app_id}"
}

case "$1" in
  test)
    run_unittests
    ;;
  run)
    run_findit_locally
    ;;
  deploy-test)
    deploy_findit "test"
    ;;
  deploy-prod)
    deploy_findit "prod"
    ;;
  *)
    print_usage
    ;;
esac
