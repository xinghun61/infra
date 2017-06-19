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
  let file = WCT._reporter.currentRunner.name;
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

// Only register these listeners when running via the golang runner.
if (window.location.search.includes('wct=go')) {
  document.addEventListener('DOMContentLoaded', function() {
    WCT._reporter.on('test end', testEnd);
    WCT._reporter.on('end', end);
  });
}
