/* Copyright 2019 The Chromium Authors. All Rights Reserved.
 *
 * Use of this source code is governed by a BSD-style
 * license that can be found in the LICENSE file.
 */

const path = require('path');

process.env.CHROME_BIN = require('puppeteer').executablePath();

module.exports = function(config) {
  const isDebug = process.argv.some((arg) => arg === '--debug');
  const coverage = process.argv.some((arg) => arg === '--coverage');
  config.set({

    // base path that will be used to resolve all patterns (eg. files, exclude)
    basePath: '',


    client: {
      mocha: {
        reporter: 'html',
        ui: 'tdd',
      },
    },

    mochaReporter: {
      showDiff: true,
    },


    // frameworks to use
    // available frameworks: https://npmjs.org/browse/keyword/karma-adapter
    frameworks: ['mocha', 'sinon'],


    // list of files / patterns to load in the browser
    files: [
      'elements/test/index.js',
    ],

    // list of files / patterns to exclude
    exclude: [
    ],

    // preprocess matching files before serving them to the browser
    // available preprocessors: https://npmjs.org/browse/keyword/karma-preprocessor
    preprocessors: {
      'elements/test/index.js': ['webpack', 'sourcemap'],
    },

    plugins: [
      'karma-chrome-launcher',
      'karma-coverage',
      'karma-mocha',
      'karma-sinon',
      'karma-sourcemap-loader',
      'karma-webpack',
    ],

    webpack: {
      // webpack configuration
      devtool: 'inline-source-map',
      mode: 'development',
      resolve: {modules: ['node_modules', 'elements']},
      module: {
        rules: [
          {
            test: /\.js$/,
            loader: 'istanbul-instrumenter-loader',
            include: path.resolve('elements/'),
            exclude: [/\.test.js$/],
            query: {esModules: true},
          },
        ],
      },
    },

    // test results reporter to use
    // possible values: 'dots', 'progress'
    // available reporters: https://npmjs.org/browse/keyword/karma-reporter
    reporters: ['progress'].concat(coverage ? ['coverage'] : []),


    // configure coverage reporter
    coverageReporter: {
      check: {
        global: {
          statements: 75,
          branches: 55,
          functions: 75,
          lines: 75,
        },
      },
      dir: 'coverage',
      reporters: [
        {type: 'lcovonly', subdir: '.'},
        {type: 'json', subdir: '.', file: 'coverage.json'},
        {type: 'html'},
        {type: 'text'},
      ],
    },


    // web server port
    port: 9876,


    // enable / disable colors in the output (reporters and logs)
    colors: true,


    // level of logging
    // possible values: config.LOG_DISABLE || config.LOG_ERROR ||
    // config.LOG_WARN || config.LOG_INFO || config.LOG_DEBUG
    logLevel: config.LOG_INFO,


    // enable/disable watching file and executing tests whenever any file changes
    autoWatch: true,


    // start these browsers
    // available browser launchers: https://npmjs.org/browse/keyword/karma-launcher
    browsers: isDebug ? ['Chrome_latest'] : ['ChromeHeadless'],


    customLaunchers: {
      Chrome_latest: {
        base: 'Chrome',
        version: 'latest',
      },
    },


    // Continuous Integration mode
    // if true, Karma captures browsers, runs the tests and exits
    singleRun: isDebug ? false : true,

    // Concurrency level
    // how many browser should be started simultaneous
    concurrency: Infinity,
  });
};
