# tricium/appengine/frontend/ui

This directory contains code for the web UI for the Tricium service.

## Development

### Setup

Run `npm install` to install all dependencies.

### Testing

Run `make test` to run tests.

To open tests in a browser and keep the browser open (for debugging etc.),
run `make serve` and navigate to https://localhost:8081/components/tricium/test/.

### Building

Run `make build` before deployment, or before serving via the
App Engine dev server.

### Linting

Run `make lint`.

### Local development

To run a local server with just the UI, run `make serve`.
This allows you to incrementally test changes without rebuilding.

To run a devserver with all endpoints (not just UI, run
`make build` then `gae.py devserver`.
