// Web component tester config for cipd frontend. Only run tests on chrome.
//
// Instructions for running tests are in
// ../chrome_infra_console_loadtest/README.md.
//
// TODO(estaab): Ensure tests work on karma instead of wct once
// http://crbug.com/496962 is resolved.

module.exports = {
  verbose: true,
  plugins: {
    local: {
      browsers: ['chrome']
    }
  },
};
