# chopsui-gallery

chopsui-gallery.appspot.com, an app containing documentation
and demos for polymer elements in the chops-ui package.

## Prerequisites

Download and install the [AppEngine SDK for Go](https://cloud.google.com/appengine/docs/flexible/go/download).

You will need a chrome infra checkout as
[described here](https://chromium.googlesource.com/infra/infra/). That will
create a local checkout of the entire infra repo, but that will include this
application and many of its dependencies.

You'll also need some extras that aren't in the default infra checkout.

```sh
# sudo where appropriate for your setup.

npm install -g bower
```

make sure you've
run
```
eval `../../../../env.py`
```
in that shell window.

## Running the app locally

```sh
make devserver
```

## Updating the app

When the chopsui package releases a new version, the chopsui-gallery should be updated.

To have chopsui-gallery reflect the changes made in the chopsui package run the following commands:

```sh
make deploy_prod
```
