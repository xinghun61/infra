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

  local current_version=`curl -s https://${app_id}.appspot.com/version`
  if ! [[ $current_version =~ ^[0-9a-fA-F]+$ ]]; then
    echo $current_version
    echo "Failed to retrieve current version of Findit from the live app."
    echo "Please input the current version, followed by [ENTER]:"
    read current_version
    echo
  fi

  local new_version="$(git rev-parse --short HEAD)"
  local app_cfg="${GOOGLE_APP_ENGINE_DIR}/appcfg.py"

  echo "Current deployed version is '$current_version'."
  echo "Deploying new version '${new_version}'..."

  echo
  echo "-----------------------------------"
  python ${app_cfg} update -A ${app_id} $FINDIT_MODULES --version ${new_version}
  echo "-----------------------------------"
  echo

  echo "New version '${new_version}' of Findit was deployed to ${app_id}."
  if ! [[ "$1" == "prod" ]]; then
    return
  fi

  local dashboard_url="https://${new_version}-dot-${app_id}.appspot.com/list-analyses"
  echo "Please force a re-run of a recent build failure on dashboard ${dashboard_url},"
  echo "ensure that the analysis is run in the new version and gives correct results,"
  echo "and then set the new version ${new_version} as default for all modules."
  echo

  local change_log_url="https://chromium.googlesource.com/infra/infra/+log/${current_version}..${new_version}/appengine/findit"
  echo "Please also email chrome-findit@ with the following:"
  echo "Subject: 'Release: findit-for-me was updated to ${new_version}.'"
  echo "Hi all,"
  echo
  echo "The app findit-for-me was updated from ${current_version} to ${new_version}."
  echo "Changelogs: ${change_log_url}"
  echo
  echo "If your bug fixes/features are included in the release, please verify on ${app_id} and mark them as verified on http://crbug.com"
  echo
  echo "Thanks,"
  echo "Released by ${USER}@"
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
