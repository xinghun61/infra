#!/bin/bash
# This should be run manually on a developer workstation for the time being.
# It requires npm to be installed and that's not available on builders by
# default.

# Make sure node_modules directory exists.
pushd .
cd ../../go/src/infra/appengine/sheriff-o-matic
npm install
popd

# Make sure we build the package from scratch.
rm -f wct.cipd

# Build wct CIPD package (without uploading it)
cipd pkg-build -pkg-def wct.yaml -pkg-var platform:linux-amd64 -out wct.cipd
# Upload it. Comment this line if you just want to build it locally.
cipd pkg-register wct.cipd

# Then do cipd set-ref infra/testing/wct/linux-amd64 -version [...] -ref prod
