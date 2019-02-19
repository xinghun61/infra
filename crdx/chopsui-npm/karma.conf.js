module.exports = function(config) {
  config.set({

    // start these browsers
    // available browser launchers: https://npmjs.org/browse/keyword/karma-launcher
    browsers: ['ChromeHeadless'],

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
      'karma-mocha',
      'karma-webpack',
    ],

    // preprocess matching files before serving them to the browser
    // available preprocessors: https://npmjs.org/browse/keyword/karma-preprocessor
    preprocessors: {
      'elements/**/*.test.js': ['webpack'],
    },

    // Continuous Integration mode
    // if true, Karma captures browsers, runs the tests and exits
    singleRun: true,

    webpack: {
      mode: 'development',
    },

    webpackMiddleware: {
      stats: 'errors-only',
    },
  });
};
