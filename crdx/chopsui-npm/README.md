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

ChopsUI packages are published publicly on npm under the [@chopsui](https://www.npmjs.com/settings/chopsui/packages) organization. To be added to this org, please send your npm username to zhangtiff@.

Each component is published under a separate npm package. Packages are managed using [Lerna](https://lernajs.io/). All packages are published together using a single version number kept in the `lerna.json` file under the `version` key.

To publish, update the version number and run `npx lerna publish`.