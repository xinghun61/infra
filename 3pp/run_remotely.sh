#!/bin/bash
# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

set -e
set -o pipefail

case $1 in
  help|-h|--help)
      cat <<'EOF'
This script is a thin wrapper for running the 3pp recipe on swarming using
`led`.

By default this will:
  * Pull your logged-in email from `luci-auth` to derive a CIPD package
    prefix (if your email is `user@example.com`, this will try to upload
    to `experimental/user_at_example.com`)
  * Use the gerrit CL associated with this branch for pulling the 3pp package
    definitions. This means you need to `git cl upload` any changes to the 3pp
    directory in order to have this script pick them up.
  * Synthesize and launch a swarming task with led in the public
    `luci.flex.try` swarming pool. This swarming task will isolate the
    recipes.

Options:
  * Pass additional arguments to the script to pass directly to the
    recipe_engine. In particular:
      * 'to_build=["json","list","of","package","names"]' - This will allow
        you to restrict the packages that are built.
      * 'platform="linux-amd64"' - Allows you to select which CIPD platform
        you're targeting. This will also affect the os dimension selected for
        the led task. By default this will use Windows as the target os (since
        most of our devs have easy local access to Linux/Mac).

Tips:
  * If you end up uploading a bad package to your experimental prefix. You'll
    need to be a CIPD admin to delete them, but you can file a bug and ping
    iannucci@ or vadimsh@ to do this.

BUGS:
  * Currently (as of 2018-11-05) won't work when targetting linux because docker
    isn't configured on these bots :(.

Notes:
  * You will need to give the
    `infra-try-builder@chops-service-accounts.iam.gserviceaccount.com`
    service account CIPD writer access to the experimental prefix that this
    script derives from your email (e.g.
    `cipd acl-edit -writer email:... experimental/user_at_example.com`)
EOF

      exit 0
    ;;
esac

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null && pwd )"

LOGIN_EMAIL=$(luci-auth info | awk '/Logged in/{gsub("\.$", "", $4); print $4}')
CIPD_EMAIL=$(sed 's/@/_at_/' <<<"$LOGIN_EMAIL")

# scan for platforms
TARG_OS=Windows
for arg in "$@"; do
  if [[ $arg == platform* ]]; then
    case $arg in
      *linux*)
        TARG_OS=Linux
        ;;
      *mac*)
        TARG_OS=Mac
        ;;
      *windows*)
        TARG_OS=Windows
        ;;
    esac
  fi
done

CL_URL=$(git cl issue --json >(python ./run_remotely_slurp_cl.py) > /dev/null)

echo Using upload prefix: experimental/$CIPD_EMAIL
echo Using os:$TARG_OS
echo Using CL \'$CL_URL\'

TMPFILE=$SCRIPT_DIR/run_remotely.tmp.task

EXTRA_PROPERTIES=()
for property in "$@"; do
  EXTRA_PROPERTIES+=(-pa "$property")
done

set -x
# pick a super-vanilla builder
led get-builder -canary 'luci.infra.try:Infra Presubmit' | \
  # Remove the first task slice; we don't want its named cache entry for the
  # builder, and swarming prevents us from triggering a task with two identical
  # task slices (which, if we remove the named cache, the two slices will be the
  # same).
  python $SCRIPT_DIR/run_remotely_tweak_task.py | \
  # Tweak dimensions
  led edit -d builder= -d caches= -d os=$TARG_OS | \
  # Remove LUCI global properties
  led edit -p buildbucket= -p buildername= -p buildnumber= | \
  # Remove 'Infra Presubmit' properties
  led edit -p repo_name= -p runhooks | \
  # This is always experimental
  led edit -p '$recipe_engine/runtime={"is_luci": true, "is_experimental": true}' | \
  # Add our isolated recipes
  led edit-recipe-bundle | \
  # Add 3pp properties
  led edit \
    -r 3pp \
    -p package_prefix=\"$CIPD_EMAIL\" \
    "${EXTRA_PROPERTIES[@]}" \
  > $TMPFILE
set +x

# GIANT HACK: The 3pp recipe needs the repo and ref in the form of:
#
#   https://host.example.com/actual/repo
#   refs/whatever/thingy
#
# `led launch` knows how to calculate these, and reimplementing them would be
# a pain, so we cheat and have `led launch` dump the task as swarming JSON,
# then extract these back. It's gross.
RAW_TMP=$TMPFILE.raw
led edit-crl-cl $CL_URL < $TMPFILE | led launch -dump > $RAW_TMP 2> /dev/null
REPO=$(python ./run_remotely_extract_repo_ref.py repo < $RAW_TMP)
REF=$(python ./run_remotely_extract_repo_ref.py ref < $RAW_TMP)
rm $RAW_TMP

set -x
led edit \
  -p 'package_locations=[{"repo": "'"$REPO"'", "ref": "'"$REF"'", "subdir": "3pp"}]' \
  < $TMPFILE | \
led launch
set +x

rm $TMPFILE
