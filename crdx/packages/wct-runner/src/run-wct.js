#!/usr/bin/env node
'use strict';
/*
Copyright 2018 The Chromium Authors. All rights reserved.
Use of this source code is governed by a BSD-style license that can be
found in the LICENSE file.

This script runs WCT tests and istanbul coverage.
*/
/* eslint-disable no-console */

const puppeteer = require('puppeteer');
const pti = require('puppeteer-to-istanbul');

const connect = require('connect');
const serveStatic = require('serve-static');
const http = require('http');
const glob = require('glob');
const yargs = require('yargs');

const { html, render } = require('@popeindustries/lit-html-server');

function isLibrary(path) {
  return path.includes('bower_components') || path.includes('node_modules');
}

async function main() {
  const argv = yargs.options({
    debug: {
      type: 'boolean',
      default: false,
      describe: 'keep the browser open',
    },
    base: {
      type: 'string',
      default: '.',
      describe: 'source base directory',
    },
    prefix: {
      type: 'string',
      default: '.',
      describe: 'subdirectory of base containing tests',
    },
    dep: {
      type: 'array',
      default: [],
      describe: 'list of dependency directories',
    },
  }).argv;

  const app = connect();
  let passes = 0;
  let failures = 0;

  app.use('/result', function(req, res, next) {
    let body = [];
    req.on('error', (err) => {
      console.error(err);
      res.end();
    }).on('data', (chunk) => {
      body.push(chunk);
    }).on('end', () => {
      body = Buffer.concat(body).toString();
      const parsedResult = JSON.parse(body);
      const msg = (`[${parsedResult.state}] ` +
                   `File: ${parsedResult.file} ` +
                   `Suite: ${parsedResult.suite} ` +
                   `Test: ${parsedResult.test}`);
      if (parsedResult.state !== 'passed') {
        failures++;
        console.error(msg);
      } else {
        passes++;
        console.log(msg);
      }

      res.on('error', (err) => {
        console.error(err);
      });

      res.writeHead(200, { 'Content-Type': 'text/plain' });
      res.write('ok');
      res.end();
    });
  });

  app.use('/wct-loader', function(req, res, next) {
    res.writeHead(200, { 'Content-Type': 'text/html' });
    const testFiles = [];
    for (const f of glob.sync(`${argv.base}/${argv.prefix}/**/*-test.html`)) {
      if (isLibrary(f)) continue;
      testFiles.push(f.substr(argv.base.length));
    }
    const output = loaderPage(testFiles);
    res.write(output);
    res.end();
  });

  const serverStat = serveStatic(argv.base);
  app.use(serverStat);
  for (const dep of argv.dep) {
    app.use(serveStatic(dep));
  }

  const httpServer = http.createServer(app);
  app.use('/done', async function(req, res, next) {
    res.writeHead(200, { 'Content-Type': 'text/html' });
    res.write('ok');
    res.end();

    console.log('stopping JS, CSS overage reporting...');
    const [jsCoverage, cssCoverage] = await Promise.all([
      page.coverage.stopJSCoverage(),
      page.coverage.stopCSSCoverage(),
    ]);

    console.log('writing coverage report...');
    // Writes to .nyc_output/out.json
    // Coverage by default includes everything loaded in the page, eg tests
    // themselves and all dependencies. We only care about coverage of the code
    // under test, so filter out everything else.
    const allCoverage = [...jsCoverage, ...cssCoverage].filter(entry =>
      !isLibrary(entry.url) && !entry.url.includes('-test.html'));

    // TODO: collapse entries whose URLS end with -NNN.js? NNN appears to be
    // which pass executed the code.  So if three tests exercise code.js there
    // will be code-NNN.js code-NNX.js code-NNY.js in the profiler output.

    // TODO: Map entry urls with '*.htmlpuppeteerTemp-inline-*.js' in them to
    // just the *.html part.  These are elements defined entirely inside html
    // files, no separate js file.

    await pti.write(allCoverage);
    console.log('...wrote coverage report');

    if (!argv.debug) {
      console.log('shutting down browser and http server...');
      await browser.close();
      await httpServer.close();
      console.log(`${passes} passes, ${failures} failures`);
      if (failures > 0) {
        process.exit(1);
      }
    }
  });

  httpServer.listen(0);
  const port = httpServer.address().port;
  console.log('listening on ' + port);

  const launchOptions = {};
  if (argv.debug) {
    launchOptions.devtools = true;
    launchOptions.headless = false;
  }

  const browser = await puppeteer.launch(launchOptions);
  const pages = await browser.pages();
  const page = pages[0];

  await Promise.all([
    page.coverage.startJSCoverage({resetOnNavigation: false}),
    page.coverage.startCSSCoverage({resetOnNavigation: false}),
  ]);

  page.goto('http://127.0.0.1:' + port + '/wct-loader');
}

function loaderPage(testFiles) {
  return html`
    <script src="/bower_components/webcomponentsjs/webcomponents-loader.js">
    </script>
    <script src="/bower_components/web-component-tester/browser.js"></script>

    <script>
    'use strict';
    (() => {
      // The following two functions are sort of a hack to work around WCT's
      // current lack of event listening hooks for things like "test finished"
      // and "suite finished". They exist in order to report test results back
      // to the go app that spawned the chromedriver that runs these tests.
      let end = function() {
        let passes = WCT._reporter.stats.passes;
        let failures = WCT._reporter.stats.failures;
        fetch('/done', {
            method: 'POST',
            body: JSON.stringify({
                'passes': passes,
                'failures': failures,
                // TODO(seanmccullough): Report timeouts, other exceptions?
            }),
        }).then(function(resp) {
          window.console.log('done response', resp);
        }).catch(function(exp) {
          window.console.log('done exception', exp);
        });
      };

      let testEnd = function() {
        let file = WCT._reporter.currentRunner.currentRunner.suite.parent.title;
        let suite = WCT._reporter.currentRunner.currentRunner.suite.title;
        let test = WCT._reporter.currentRunner.currentRunner.test.title;
        let state = WCT._reporter.currentRunner.currentRunner.test.state;

        fetch('/result', {
            method: 'POST',
            body: JSON.stringify({
                'file': file,
                'suite': suite,
                'test': test,
                'state': state,
                // TODO(seanmccullough): Indicate if dom=shadow for this run.
            }),
        }).then(function(resp) {
          window.console.log('result response', resp);
        }).catch(function(exp) {
          window.console.log('result exception', exp);
        });
      };

      document.addEventListener('DOMContentLoaded', function() {
        WCT._reporter.on('test end', testEnd);
        WCT._reporter.on('end', end);
      });
    })();

    WCT.loadSuites([${testFiles.map(file => html`"${file}",`)}]);
    </script>
  `;
}

main();
