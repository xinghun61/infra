#!/bin/bash

METADATA_URL="http://metadata.google.internal"

_help() {
  echo -e "Usage: $0 <monitoring-proxy-path> <credentials-dir>"
  echo -e ""
  echo -e "  monitoring-proxy-path\tThe path to the monitoring proxy binary."
  echo -e "  credentials-dir\tThe path to the credentials storage directory."
}

MONITORING_PROXY=$1; shift
if [ -z "${MONITORING_PROXY}" ]; then
  echo "ERROR: Missing argument <monitoring-proxy-path>"
  _help
  exit 1
fi
MONITORING_PROXY=$(readlink -f "${MONITORING_PROXY}")
if [ ! -x "${MONITORING_PROXY}" ]; then
  echo "ERROR: Monitoring proxy path is not an executable file \
[${MONITORING_PROXY}]"
  exit 1
fi

CREDENTIALS_DIR=$1; shift
if [ -z "${CREDENTIALS_DIR}" ]; then
  echo "ERROR: Missing argument <credentials-dir>"
  _help
  exit 1
fi
CREDENTIALS_DIR=$(readlink -f ${CREDENTIALS_DIR})
if [ ! -d "${CREDENTIALS_DIR}" ]; then
  echo "INFO: Creating credentials directory [${CREDENTIALS_DIR}]"
  mkdir -p "${CREDENTIALS_DIR}"
fi

_load_metadata_domain() {
  local __resultvar=$1; shift
  local domain=$1; shift
  local resource=$1; shift

  OUTPUT=$(curl \
    -s \
    --fail \
    "${METADATA_URL}/computeMetadata/v1/${domain}/attributes/${resource}" \
    -H "Metadata-Flavor: Google")
  RV=$?
  if [ ${RV} != 0 ]; then
    return ${RV}
  fi
  if [ -z "${OUTPUT}" ]; then
    return 1
  fi

  eval $__resultvar="'${OUTPUT}'"
}

# Loads metadata from the GCE metadata server.
_load_metadata() {
  local __resultvar=$1; shift
  local resource=$1; shift

  # Try loading from 'instance' domain.
  _load_metadata_domain "$__resultvar" "instance" "$resource"
  if [ $? == 0 ]; then
    return 0
  fi

  # Try loading from 'project' domain.
  _load_metadata_domain "$__resultvar" "project" "$resource"
  if [ $? == 0 ]; then
    return 0
  fi

  echo "WARN: Failed to load metadata [${resource}]."
  return 1
}

_load_metadata_check() {
  local __resultvar=$1; shift
  local resource=$1; shift

  _load_metadata "$__resultvar" "$resource"
  if [ $? != 0 ]; then
    echo "ERROR: Metadata resource [${resource}] is required."
    exit 1
  fi

  return 0
}

_write_credentials() {
  local path=$1; shift
  local data=$1; shift

  echo "${data}" > "${path}"
}

# Test if we're running on a GCE instance.
curl \
  -s \
  --fail \
  "${METADATA_URL}" \
  1>/dev/null
if [ $? != 0 ]; then
  echo "ERROR: Not running on GCE instance."
  exit 1
fi

# Load metadata.
_load_metadata_check E_URL "monitoring_proxy_endpoint_url"
_load_metadata_check E_AUTH_JSON "monitoring_proxy_endpoint_auth_json"

_load_metadata_check PS_PROJECT "monitoring_proxy_pubsub_project"
_load_metadata_check PS_SUBSCRIPTION "monitoring_proxy_pubsub_subscription"
_load_metadata PS_BATCH_SIZE "monitoring_proxy_pubsub_batch_size"

_load_metadata CLOUD_AUTH_JSON "monitoring_proxy_cloud_auth_json"
_load_metadata WORKERS "monitoring_proxy_workers"
_load_metadata LOG_LEVEL "monitoring_proxy_log_level"

# Export credentials data.
E_AUTH_PATH="${CREDENTIALS_DIR}/endpoint_service_account.json"
_write_credentials "${E_AUTH_PATH}" "${E_AUTH_JSON}"

if [ ! -z "${CLOUD_AUTH_JSON}" ]; then
  CLOUD_AUTH_PATH="${CREDENTIALS_DIR}/cloud_service_account.json"
  _write_credentials "${CLOUD_AUTH_PATH}" "${CLOUD_AUTH_JSON}"
fi

# Compose command line.
ARGS=(
  "-endpoint-url" "${E_URL}"
  "-endpoint-service-account-json" "${E_AUTH_PATH}"

  "-pubsub-project" "${PS_PROJECT}"
  "-pubsub-subscription" "${PS_SUBSCRIPTION}"
  )

if [ ! -z "${PS_BATCH_SIZE}" ]; then
  ARGS+=("-pubsub-batch-size" "${PS_BATCH_SIZE}")
fi
if [ ! -z "${WORKERS}" ]; then
  ARGS+=("-workers" "${WORKERS}")
fi
if [ ! -z "${LOG_LEVEL}" ]; then
  ARGS+=("-log_level" "${LOG_LEVEL}")
fi
if [ ! -z "${CLOUD_AUTH_PATH}" ]; then
  ARGS+=("-proxy-service-account-json" "${CLOUD_AUTH_PATH}")
fi

echo "INFO: Running command line args: ${MONITORING_PROXY} ${ARGS[*]}"
"${MONITORING_PROXY}" ${ARGS[*]}
