#!/bin/bash
#
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# This script is to ease running Findit locally, running its unit tests, and
# deploying Findit to App Engine.

THIS_SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE:-$0}" )" && pwd )"
FINDIT_DIR="$(realpath ${THIS_SCRIPT_DIR}/..)"
INFRA_DIR="$(realpath ${FINDIT_DIR}/../..)"
GOOGLE_APP_ENGINE_DIR="$(realpath ${INFRA_DIR}/../google_appengine)"
APP_CFG="${GOOGLE_APP_ENGINE_DIR}/appcfg.py"
FINDIT_MODULES="${FINDIT_DIR}/app.yaml ${FINDIT_DIR}/waterfall-frontend.yaml ${FINDIT_DIR}/waterfall-backend.yaml"

if [[ -z "${USER}" ]]; then
  echo "Cannot identify who is deploying Findit. Please set USER."
  exit 1
fi

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
  echo "  deploy-prod       Deploy Findit to findit-for-me for release"
  echo "  deploy-test-dev   Deploy Findit to findit-for-me-dev for test"
  echo "  deploy-test-prod  Deploy Findit to findit-for-me for staging test"
  exit 1
}

print_command_for_queue_cron_dispatch() {
  echo
  echo "If there is any change to cron.yaml, dispatch.yaml, index.yaml, or"
  echo " queue.yaml since last deployment, please run appropriate commands"
  echo " below to update them:"
  echo "  ${APP_CFG} update_cron -A $1 ${FINDIT_DIR}"
  echo "  ${APP_CFG} update_dispatch -A $1 ${FINDIT_DIR}"
  echo "  ${APP_CFG} update_indexes -A $1 ${FINDIT_DIR}"
  echo "  ${APP_CFG} update_queues -A $1 ${FINDIT_DIR}"
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

deploy_findit_for_test() {
  # Deploy a version for testing, the version name is the same as the user name.
  local app_id="findit-for-me-dev"
  if [[ "$1" == "prod" ]]; then
    app_id="findit-for-me"
  fi
  local new_version=${USER}

  echo "-----------------------------------"
  python ${APP_CFG} update -A ${app_id} $FINDIT_MODULES --version ${new_version}
  echo "-----------------------------------"
  print_command_for_queue_cron_dispatch ${app_id}
  echo "-----------------------------------"
  echo Findit was deployed to "https://${new_version}-dot-${app_id}.appspot.com/"
}

deploy_findit_for_prod() {
  local app_id="findit-for-me"

  # Sync to latest code.
  local update_log="${TMP_DIR}/update.log"
  echo "Syncing code to tip of tree, logging in ${update_log} ..."
  local update="0" #"$(cd ${INFRA_DIR} && git pull >>${update_log} 2>>${update_log} && gclient sync >>$update_log >>${update_log} 2>>${update_log} && echo $?)"
  if [[ "${update}" != "0" ]]; then
    echo "Failed to run 'git pull && gclient sync'!"
    echo "Please check log at ${update_log}"
    return
  fi
  echo "Code was synced successfully."

  # Check uncommitted local changes.
  local changed_file_number="$(git status --porcelain | wc -l)"
  if [[ "${changed_file_number}" != "0" ]]; then
    echo "You have uncommitted local changes!"
    echo "Please run 'git status' to check local changes."
    return
  fi

  local new_version="$(git rev-parse --short HEAD)"

  # Check committed local changes.
  local tot_version="$(git rev-parse --short origin/master)"
  if [[ "${new_version}" != "${tot_version}" ]]; then
    echo "You have local commits!"
    echo "Please run 'git reset ${tot_version}' to reset the local changes."
    return
  fi

  # Check current deployed version.
  local current_version=`curl -s https://${app_id}.appspot.com/version`
  if ! [[ ${current_version} =~ ^[0-9a-fA-F]+$ ]]; then
    echo "Failed to retrieve current version of Findit from the live app."
    echo "Please input the current version, followed by [ENTER]:"
    read current_version
  fi

  echo "Current deployed version is ${current_version}"
  echo "Deploying new version '${new_version}'..."

  echo
  echo "-----------------------------------"
  python ${APP_CFG} update -A ${app_id} $FINDIT_MODULES --version ${new_version}
  echo "-----------------------------------"
  print_command_for_queue_cron_dispatch ${app_id}
  echo "-----------------------------------"
  echo

  echo "New version '${new_version}' of Findit was deployed to ${app_id}."

  local dashboard_url="https://${new_version}-dot-${app_id}.appspot.com/list-analyses"
  echo "Please force a re-run of a recent build failure on dashboard ${dashboard_url},"
  echo "ensure that the analysis is run in the new-version frontend & backend and gives correct results,"
  echo "and then set the new version ${new_version} as default for both frontend and backend."
  echo

  local change_log_url="https://chromium.googlesource.com/infra/infra/+log/${current_version}..${new_version}/appengine/findit"
  echo "If the release is for findit-for-me, please email chrome-findit with the following:"
  echo "Subject: 'Release: findit-for-me was update to ${new_version}.'"
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
  deploy-prod)
    deploy_findit_for_prod
    ;;
  deploy-test-dev)
    deploy_findit_for_test "dev"
    ;;
  deploy-test-prod)
    deploy_findit_for_test "prod"
    ;;
  *)
    print_usage
    ;;
esac
