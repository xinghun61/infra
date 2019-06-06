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

    // start these browsers
    // available browser launchers: https://npmjs.org/browse/keyword/karma-launcher
    browsers: isDebug ? ['Chrome_latest'] : ['ChromeHeadless'],

    client: {
      mocha: {
        reporter: 'html',
        ui: 'qunit',
      },
    },

    // list of files / patterns to load in the browser
    files: [
      'elements/**/*.test.js',
    ],

    // frameworks to use
    // available frameworks: https://npmjs.org/browse/keyword/karma-adapter
    frameworks: ['mocha'],

    plugins: [
      'karma-chrome-launcher',
      'karma-coverage',
      'karma-mocha',
      'karma-sinon',
      'karma-sourcemap-loader',
      'karma-webpack',
    ],

    // preprocess matching files before serving them to the browser
    // available preprocessors: https://npmjs.org/browse/keyword/karma-preprocessor
    preprocessors: {
      'elements/**/*.test.js': ['webpack'],
    },

    reporters: ['progress'].concat(coverage ? ['coverage'] : []),

    // Continuous Integration mode
    // if true, Karma captures browsers, runs the tests and exits
    singleRun: isDebug ? false : true,

    webpack: {
      // webpack configuration
      devtool: 'inline-source-map',
      mode: 'development',
      resolve: {
        modules: ['node_modules'],
        alias: {
          '@chopsui/chops-checkbox': path.resolve(
            'elements/chops-checkbox/chops-checkbox.js'),
        },
      },
      module: {
        rules: [
          {
            test: /\.js$/,
            loader: 'istanbul-instrumenter-loader',
            include: path.resolve('elements/'),
            exclude: [/\.test.js$/, /node_modules/],
            query: {esModules: true},
          },
        ],
      },
    },

    webpackMiddleware: {
      stats: 'errors-only',
    },

    customLaunchers: {
      Chrome_latest: {
        base: 'Chrome',
        version: 'latest',
      },
    },

    // configure coverage reporter
    coverageReporter: {
      includeAllSources: true,
      check: {
        global: {
          statements: 36,
          branches: 22,
          functions: 44,
          lines: 39,
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
  });
};
