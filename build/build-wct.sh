# This should be run manually on a developer workstation for the time being.
# It requires npm to be installed and that's not available on builders by
# default.

# Make sure node_modules directory exists.
pushd .
cd ../go/src/infra/appengine/sheriff-o-matic
npm install
popd

# Build wct CIPD package
cipd create -pkg-def packages/wct.yaml -pkg-var platform:linux-amd64

# Then do cipd set-ref infra/testing/wct/linux-amd64 -version [...] -ref prod

