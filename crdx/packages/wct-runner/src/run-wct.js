#!/usr/bin/env node

const puppeteer = require('puppeteer');
const pti = require('puppeteer-to-istanbul');

const connect = require('connect');
const serveStatic = require('serve-static');
const http = require('http');
const glob = require('glob');
const yargs = require('yargs');

const { html, render } = require('@popeindustries/lit-html-server');

async function main() {
  const argv = yargs.boolean('debug')
    .describe('debug', 'keeps the browser instance running instead of exiting')
    .string('chrome')
    .describe('chrome', 'binary location for chrome executable')
    .demandOption(['chrome'])
    .argv;

  const app = connect();
  let passes = 0;
  let failures = 0;

  app.use('/result', function(req, res, next){
    let body = [];
    req.on('error', (err) => {
      console.error(err);
      res.end();
    }).on('data', (chunk) => {
      body.push(chunk);
    }).on('end', () => {
      body = Buffer.concat(body).toString();
      parsedResult = JSON.parse(body)
      if (parsedResult.state != 'passed') {
        failures++;
        console.error(`[${parsedResult.state}] File: ${parsedResult.file} Suite: ${parsedResult.suite} Test: ${parsedResult.test}`);
      } else {
        passes++;
        console.log(`[${parsedResult.state}] File: ${parsedResult.file} Suite: ${parsedResult.suite} Test: ${parsedResult.test}`);
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
    const testFiles = glob.sync('**/*-test.html').filter(f => {
        return f.indexOf('bower_components') == -1 && f.indexOf('node_modules') == -1;
    }).map(f => `/${f}`);
    const output = loaderPage(testFiles);
    res.write(output);
    res.end();
  });

  const serverStat = serveStatic('.');
  app.use(serverStat);

  const httpServer = http.createServer(app);
  app.use('/done', async function(req, res, next) {
    console.log('stopping JS, CSS overage reporting...');
    const [jsCoverage, cssCoverage] = await Promise.all([
      page.coverage.stopJSCoverage(),
      page.coverage.stopCSSCoverage(),
    ]);

    console.log('writing coverage report...');
    // Writes to .nyc_output/out.json
    const allCoverage = [...jsCoverage, ...cssCoverage].filter(entry => {
      // Coverage by default includes everything loaded in the page, eg tests themselves and
      // all dependencies. We only care about coverage of the code under test, so filter out
      // everything else.
      return entry.url.indexOf('bower_components') == -1 && entry.url.indexOf('node_modules') == -1 &&
        entry.url.indexOf('-test.html') == -1;
    });

    // TODO: collapse entries whose URLS end with -NNN.js? NNN appears to be which pass executed the code.
    // So if three tests exercise code.js there will be code-NNN.js code-NNX.js code-NNY.js in
    // the profiler output. /shrug.

    // TODO: Map entry urls with '*.htmlpuppeteerTemp-inline-*.js' in them to just the *.html part.
    // These are elements defined entirely inside html files, no separate js file.

    await pti.write(allCoverage);

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

  const launchOptions = {
    executablePath: argv.chromeBinary
  };

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
  page.focus('*');
}

function loaderPage(testFiles) {
  const tmpl = html`
<script src="/bower_components/webcomponentsjs/webcomponents-loader.js"></script>
<script src="/bower_components/web-component-tester/browser.js"></script>

<script>
'use strict';
(() => {
  // The following two functions are sort of a hack to work around WCT's
  // current lack of event listening hooks for things like "test finished" and
  // "suite finished". They exist in order to report test results back to
  // the go app that spawned the chromedriver that runs these tests.
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

WCT.loadSuites([${testFiles.map((file)=>{ return html`"${file}",`})}]);
</script>
    `;
  return tmpl;
}

(async () => {
  await main();
})();