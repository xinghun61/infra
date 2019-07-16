// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// This is a karma reporter that produces test results JSON suitable for
// uploading to test-results.appspot.com. For more details, see
// https://chromium.googlesource.com/chromium/src/+/master/docs/testing/json_test_results_format.md

const path = require('path');
const fs = require('fs');

// Creates a nested path of objects starting at root,
// each step named by elements of s.  Returns the last
// node of the path.
function nest(s, root) {
  let curr = root;
  s.forEach((part) => {
    if (!curr.hasOwnProperty(part)) {
      curr[part] = {};
    }
    curr = curr[part];
  });
  return curr;
}

const ChOpsJSONReporter = function(
    baseReporterDecorator, config, helper, logger) {
  const log = logger.create('chopsui-json-reporter');
  baseReporterDecorator(this);
  const reporterConfig = config.chopsUiReporter || {};
  const stdout = typeof reporterConfig.stdout !== 'undefined' ?
    reporterConfig.stdout : false;
  const outputFile = reporterConfig.outputFile
    ? helper.normalizeWinPath(path.resolve(
      config.basePath, reporterConfig.outputFile))
    : null;
  const builderName = reporterConfig.builderName || 'infra-try-frontend';
  const buildNumber = reporterConfig.buildNumber;
  const history = {
    builder_name: builderName,
    build_number: buildNumber,
    interrupted: false,
    num_failures_by_type: {},
    path_delimiter: '/',
    seconds_since_epoch: new Date().getTime()/1000,
    tests: {},
    version: 3,
  };

  this.onSpecComplete = function(browser, result) {
    const res = nest([...result.suite, result.description], history.tests);
    res.expected = 'PASS';
    res.actual = result.success ? 'PASS' : 'FAIL';
    res.start = result.startTime;
    res.end = result.endTime;
    res.time = result.endTime - result.startTime;
  };

  this.onRunComplete = function(browser, result) {
    history.num_failures_by_type['FAIL'] = result.failed;
    history.num_failures_by_type['PASS'] = result.success;

    const json = JSON.stringify(history, undefined, '\t');
    if (stdout) {
      process.stdout.write(json);
    }
    if (outputFile) {
      helper.mkdirIfNotExists(path.dirname(outputFile), function() {
        fs.writeFile(outputFile, json, function(err) {
          if (err) {
            log.warn('Cannot write JSON\n\t' + err.message);
          } else {
            log.debug('JSON written to "%s".', outputFile);
          }
        });
      });
    } else {
      history.result = {};
    }
  };
};

ChOpsJSONReporter.$inject = ['baseReporterDecorator', 'config', 'helper',
  'logger'];

// PUBLISH DI MODULE
module.exports = {
  'reporter:chopsui-json': ['type', ChOpsJSONReporter],
};
