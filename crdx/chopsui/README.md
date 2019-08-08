# chopsui

Design Doc: go/chopsui

This directory contains Polymer Web Components that are meant to be shared by
Chrome Operations' application frontends.

chopsui/ has been published as the bower package "chopsui".

## Definitions

[infra repo](https://chromium.googlesource.com/infra/infra/+/master/crdx/chopsui/)

-   The chopsui directory in the infra repo

[chopsui repo](https://chromium.googlesource.com/infra/infra/crdx/chopsui.git)

-   A subdirectory mirror repo of the chopsui directory in the infra repo

Code changes should be done in the infra repo.

New versions of the chopsui bower package are published by pushing git tags.
This should be done in the chopsui repo. See the Pushing a New Version section.

## Documenting elements

Please add demos and documentation for elements as described in the
[polymer docs](https://www.polymer-project.org/2.0/docs/tools/documentation#document-an-element).

Check that your demo and documentation are working and correct by running:

```sh
polymer serve
```

then visit localhost:XXXX/components/chopsui/demo/my-el_demo.html

## Pushing a New Version

New versions are published by pushing git version tags while in the chopsui
repo. Bower will automatically detect a new version tag.

### Prerequisites

You need to be granted permission to push tags in the chopsui repo. if you don't
have permission, please contact jojwang@, zhangtiff@, or seanmccullough@ for
instructions on how to proceed.

Make a clone of the chopsui repo:

```sh
git clone https://chromium.googlesource.com/infra/infra/crdx/chopsui
```

To test your elements, you will need to install `polymer-cli`:

```sh
npm install -g polymer-cli
```

You'll also need to fetch the node module and bower component dependencies
specified specified in `package.json` and `bower.json`:

```sh
npm install
bower install
```

You can run the tests with:

```sh
polymer test
```

Make sure Chromium's `depot_tools` is in your path as well.
[Learn how to set up depot_tools here.](http://commondatastorage.googleapis.com/chrome-infra-docs/flat/depot_tools/docs/html/depot_tools_tutorial.html#_setting_up)

### Push a new version tag

 1. Once the latest change (committed in the infra repo) for the new version
    has landed, switch to the chopsui repo.

 2. To view existing tags, run:

```sh
git tag
```

3. Create a new version tag:

```sh
git tag v0.0.31 # replace 0.0.31 with an appropriate version number
```

4. Push the new tag:

```sh
git push --tags
```

That's it! Now, when you run:

```sh
bower info chopsui
```

You should see the new version tag you just pushed listed under "Available
versions".
