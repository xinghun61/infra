#!/bin/bash
# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

# The existing replicas all have this prefix:
REPLICA_PREFIX="replica-7"

# The new replicas made from the restored master will have this prefix:
NEW_REPLICA_PREFIX="replica-8"

CLOUD_PROJECT="monorail-staging"

DRY_RUN=true

echo Restoring backups to master for $CLOUD_PROJECT. Dry run: $DRY_RUN
echo This will delete all read replicas with the prefix "$REPLICA_PREFIX"
echo and create a new set of replicas with the prefix "$NEW_REPLICA_PREFIX"
echo
echo Checking for existing read replicas to delete:

EXISTING_REPLICAS=($(gcloud sql instances list --project=$CLOUD_PROJECT | grep $REPLICA_PREFIX- | awk '{print $1}'))

if [ ${#EXISTING_REPLICAS[@]} -eq 0 ]; then
  echo No replicas found with prefix $REPLICA_PREFIX
  echo List instances to find the replica prefix by running:
  echo gcloud sql instances list --project=$CLOUD_PROJECT
  exit 1
fi

echo Deleting ${#EXISTING_REPLICAS[@]} existing replicas found with the prefix $REPLICA_PREFIX

for r in "${EXISTING_REPLICAS[@]}"; do
  echo Deleting $r
  cmd="gcloud sql instances delete $r --project=$CLOUD_PROJECT"
  echo $cmd
  if [ $DRY_RUN == false ]; then
    $cmd
  fi
done

echo Checking for available backups:

DUE_TIMES=($(gcloud sql backups list --instance master --project=$CLOUD_PROJECT | grep SUCCESSFUL | awk '{print $1}'))

for index in ${!DUE_TIMES[*]}; do
  echo "[$index] ${DUE_TIMES[$index]}"
done

echo "Choose one of the above due_time values."
echo "NOTE: selecting anything besides 0 will require you to manually"
echo "complete the rest of the restore process."
echo "Recover from date [0: ${DUE_TIMES[0]}]:"
read DUE_TIME_INDEX

DUE_TIME=${DUE_TIMES[$DUE_TIME_INDEX]}

cmd="gcloud sql instances restore-backup master --due-time=$DUE_TIME --project=$CLOUD_PROJECT --async"
echo $cmd
if [ $DRY_RUN == false ]; then
  $cmd
fi

if [ "$DUE_TIME_INDEX" -ne "0" ]; then
  echo "You've restored an older-than-latest backup. Please contact speckle-oncall@"
  echo "to request an on-demand backup of the master before attemtping to restart replicas,"
  echo "which this script does not do automatically in this case."
  echo "run 'gcloud sql instances create' commands to create new replicas manually after"
  echo "you have confirmed with speckle-oncall@ the on-demand backup is complete."
  echo "Exiting"
  exit 0
fi

echo "Finding restore operation ID..."

RESTORE_OP_IDS=($(gcloud sql operations list --instance=master --project=$CLOUD_PROJECT | grep RESTORE_VOLUME | awk '{print $1}'))

# Assume the fist RESTORE_VOLUME is the operation we want; they're listed in reverse chronological order.
echo Waiting on restore operation ID: ${RESTORE_OP_IDS[0]}

# This isn't waiting long enough. Or it says it's done before it really is.  Either way, the replica create steps fail
# with e.g. "Failed in: CATCHING_UP Operation token: 03dd57a9-37a9-4f6f-9aa6-9c3b8ece01bd Message: Saw error in IO and/or SQL thread"
gcloud sql operations wait ${RESTORE_OP_IDS[0]} --instance=master --project=$CLOUD_PROJECT

echo Restore is finished on master. Now create the new set of read replicas with the new name prefix $NEW_REPLICA_PREFIX:

for i in `seq 0 9`; do
  cmd="gcloud sql instances create $NEW_REPLICA_PREFIX-0$i --master-instance-name master --project=$CLOUD_PROJECT --follow-gae-app=$CLOUD_PROJECT --authorized-gae-apps=$CLOUD_PROJECT --async --tier=D2"
  echo $cmd
  if [ $DRY_RUN == false ]; then
    $cmd
  fi
done

echo If the replica creation steps above did not succeed due to authentication
echo errors, you may need to retry them manually.
echo
echo
echo Backup restore is nearly complete.  Check the instances page on developer console to see when
echo all of the replicas are "Runnable" status. Until then, you may encounter errors in issue search.
echo In the mean time:
echo - edit settings.py to change the db_replica_prefix variable to be "$NEW_REPLICA_PREFIX-"
echo   Then either "make deploy_prod" or "make deploy_staging" for search to pick up the new prefix.
echo   Then set the newly deploy version for besearch and besearch2 on the dev console Versons page.
echo Follow-up:
echo - Submit the change.
echo - Delete old versions of besearch because they run up the GAE bill.
