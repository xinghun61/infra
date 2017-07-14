#!/bin/bash
#
# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# This script is to ease running Predator locally, running its unit tests, and
# deploying Predator to App Engine.

THIS_SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE:-$0}" )" && pwd )"
PREDATOR_DIR="${THIS_SCRIPT_DIR}/.."
INFRA_DIR="${PREDATOR_DIR}/../.."
GOOGLE_APP_ENGINE_DIR="${INFRA_DIR}/../google_appengine"
has_realpath="$(which realpath 1>/dev/null 2>/dev/null && echo 0)"
if [[ ${has_realpath} == "0" ]]; then
  PREDATOR_DIR="$(realpath ${PREDATOR_DIR})"
  INFRA_DIR="$(realpath ${INFRA_DIR})"
  GOOGLE_APP_ENGINE_DIR="$(realpath ${GOOGLE_APP_ENGINE_DIR})"
fi
APP_CFG="${GOOGLE_APP_ENGINE_DIR}/appcfg.py"

DEFAULT_MODULE="${PREDATOR_DIR}/app.yaml"
BACKEND_MODULES="${PREDATOR_DIR}/backend-clusterfuzz.yaml ${PREDATOR_DIR}/backend-fracas.yaml ${PREDATOR_DIR}/backend-cracas.yaml ${PREDATOR_DIR}/backend-uma-sampling-profiler.yaml ${PREDATOR_DIR}/backend-process.yaml"


if [[ -z "${USER}" ]]; then
  echo "Cannot identify who is deploying Predator. Please set USER."
  exit 1
fi

if [[ -z "${APPENGINE_TMP}" ]]; then
  TMP_DIR="${PREDATOR_DIR}/.tmp"
else
  TMP_DIR=${APPENGINE_TMP}
fi

print_usage() {
  echo
  echo "Usage:"
  echo "$0 <command>"
  echo
  echo "Supported commands:"
  echo "  test                 Run unittests"
  echo "  run                  Run Predator locally"
  echo "  deploy-prod          Deploy predator to predator-for-me for release"
  echo "  deploy-test-prod     Deploy predator to predator-for-me-test for test"
  echo "  deploy-staging       Deploy predator to predator-for-me-staging for test"
  exit 1
}

print_command_for_queue_cron_dispatch() {
  app_id=$1
  echo
  echo "If there is any change to cron.yaml, dispatch.yaml, index.yaml, or"
  echo " queue.yaml since last deployment, please run appropriate commands"
  echo " below to update them:"
  echo "  ${APP_CFG} update_cron -A ${app_id} ${PREDATOR_DIR}"
  echo "  ${APP_CFG} update_dispatch -A ${app_id} ${PREDATOR_DIR}"
  echo "  ${APP_CFG} update_indexes -A ${app_id} ${PREDATOR_DIR}"
  echo "  ${APP_CFG} update_queues -A ${app_id} ${PREDATOR_DIR}"
}

run_unittests() {
  local predator="appengine/predator"
  local coverage_report_parent_dir="${TMP_DIR}/coverage"
  mkdir -p ${coverage_report_parent_dir}
  python ${INFRA_DIR}/test.py test ${predator} --html-report ${coverage_report_parent_dir}
  echo "Code coverage report file://${coverage_report_parent_dir}/${predator}/index.html"
}

run_locally() {
  local storage_path="${TMP_DIR}/predator"
  local options="--storage_path ${storage_path}"
  mkdir -p "${storage_path}"
  python ${GOOGLE_APP_ENGINE_DIR}/dev_appserver.py ${options} ${DEFAULT_MODULE} ${BACKEND_MODULES}
}

deploy_for_test() {
  # Deploy a version for testing, the version name is the same as the user name.
  local app_id_to_use=${APP_ID}
  local app_env=$1
  if [[ -z ${app_id_to_use} ]]; then
    if [[ "${app_env}" == "prod" ]]; then
      local app_id_to_use="predator-for-me"
    else
      local app_id_to_use="predator-for-me-staging"
    fi
  fi
  echo "app id is ${app_id_to_use}"

  local new_version="${USER}"

  echo "-----------------------------------"
  python ${APP_CFG} update -A ${app_id_to_use} --version ${new_version} ${DEFAULT_MODULE} ${BACKEND_MODULES}
  echo "-----------------------------------"
  print_command_for_queue_cron_dispatch ${app_id_to_use}
  echo "-----------------------------------"
  echo "Predator was deployed to https://${new_version}-dot-${app_id_to_use}.appspot.com/"
}

deploy_for_prod() {
  local app_id="predator-for-me"

  # Sync to latest code.
  local update_log="${TMP_DIR}/update.log"
  echo "Syncing code to tip of tree, logging in ${update_log} ..."
  local update="0" #"$(cd ${INFRA_DIR} && git pull >>${update_log} 2>>${update_log} && gclient sync >>${update_log} >>${update_log} 2>>${update_log} && echo $?)"
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
    echo "Failed to retrieve current version of predator from the live app."
    echo "Please input the current version, followed by [ENTER]:"
    read current_version
  fi

  echo "Current deployed version is ${current_version}"
  echo "Deploying new version '${new_version}'..."

  echo
  echo "-----------------------------------"
  python ${APP_CFG} update -A ${app_id} --version ${new_version} ${DEFAULT_MODULE} ${BACKEND_MODULES}
  echo "-----------------------------------"
  print_command_for_queue_cron_dispatch ${app_id}
  echo "-----------------------------------"
  echo

  echo "New version '${new_version}' of Predator was deployed to ${app_id}."

  app_console_url="https://pantheon.corp.google.com/appengine/versions?project=${app_id}"
  local frontend_url="https://${new_version}-dot-${app_id}.appspot.com/"
  echo "Please checkout the frontend ${frontend_url}, and verify that the new version works as expected."
  echo
  echo "Then press [ENTER] to confirm that the new version works as expected:"
  read unused_var
  echo "Now please set the new version ${new_version} as default for the modules default, and backend-* on ${app_console_url}."
  echo "Then press [ENTER] to confirm that the new version was set default:"
  read unused_var

  local change_logs_url="https://chromium.googlesource.com/infra/infra/+log/${current_version}..${new_version}/appengine/predator"
  echo "Please email chrome-predator@ with the following:"
  echo
  echo "Subject: Release: ${app_id} updated to ${new_version}."
  echo "Hi all,"
  echo
  echo "The app ${app_id} was updated from ${current_version} to ${new_version}."
  echo "Changelogs: ${change_logs_url}"
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
    run_locally
    ;;
  deploy-prod)
    deploy_for_prod
    ;;
  deploy-test-prod)
    deploy_for_test "prod"
    ;;
  deploy-staging)
    deploy_for_test "dev"
    ;;
  *)
    print_usage
    ;;
esac
