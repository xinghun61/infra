# chopsui

This directory contains Web Components shared across Chrome Operations' application frontends.

## Using chopsui components

Find the name of the specific component and install it within the `@chopsui` package scope. For example, to install `chops-header`, run `npm install @chopsui/chops-header`.

## Contributing

To set up project development:
1. Clone this repo with `git clone`.
2. Install dependencies with `npm run bootstrap`.
3. Run tests with `npm test`.
4. Run demos with `npm start`. The demos will be at http://localhost:8080/.

### Publishing packages

ChopsUI packages are published publicly on npm under the [@chopsui](https://www.npmjs.com/settings/chopsui/packages) organization.

Each component is published under a separate npm package. Packages are managed using [Lerna](https://lernajs.io/). All packages are published together using a single version number kept in the `lerna.json` file under the `version` key.

To set up:
1. Send your npm username to zhangtiff@ to be added to [@chopsui](https://www.npmjs.com/settings/chopsui/packages).
2. Authenticate in npm with `npm adduser`.

To publish a new version:
1. Sync a clean branch with upstream set to `origin/master`.
2. Create a new version with `npx lerna version --no-git-tag-version`. Lerna will prompt you to select a new version number, detect which packages have changed since the last version, and locally update the json files.
3. Commit the changes, upload them for code review, and land them.
4. Sync to the newly landed commit.
5. Publish to npm with `npx lerna publish from-package`.
