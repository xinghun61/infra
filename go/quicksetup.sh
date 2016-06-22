#!/bin/bash
# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

set -eu

mkdir cr-infra-go-area
cd cr-infra-go-area

# Download depot_tools
echo "Getting Chromium depot_tools.."
git clone https://chromium.googlesource.com/chromium/tools/depot_tools.git depot_tools
echo

echo "Fetching the infra build..."
export PATH="$PWD/depot_tools:$PATH"
fetch infra

echo "Creating enter script..."
# Create a bashrc include file
ENTER_SCRIPT=$PWD/enter-env.sh
cat > $ENTER_SCRIPT <<EOF
#!/bin/bash
#
# DO NOT MODIFY, THIS IS AUTOMATICALLY GENERATED AND WILL BE OVERWRITTEN
#
[[ "\${BASH_SOURCE[0]}" != "\${0}" ]] && SOURCED=1 || SOURCED=0
if [ \$SOURCED = 0 ]; then
	exec bash --init-file $ENTER_SCRIPT
fi

if [ -f ~/.bashrc ]; then . ~/.bashrc; fi

export PS1
export DEPOT_TOOLS="$PWD/depot_tools"
export PATH="\$DEPOT_TOOLS:\$PATH"
export INFRA_PROMPT_TAG="[cr-infra-go-area] "

cd $PWD/infra/go
eval \$($PWD/infra/go/env.py)

echo "Entered cr-infra-go-area setup at '$PWD'"
cd "$PWD/infra/go/src"
EOF


chmod a+x $ENTER_SCRIPT

# Running the env setup for the first time
source $ENTER_SCRIPT

# Output usage instructions
echo "--------------------------------------------------------------------"
echo
if [ -d ~/bin ]; then
	BINPATH=~/bin/cr-infra-go-area-enter
	read -p "Link the enter script to $BINPATH? (y|N) " LINKBIN
	case "$LINKBIN" in
		y|Y )
			ln -sf $ENTER_SCRIPT $BINPATH
			echo "Enter the environment by running 'cr-infra-go-area-enter'"
			exit 0
			;;
		* )
			;;
	esac
fi
echo "Enter the environment by running '$ENTER_SCRIPT'"
