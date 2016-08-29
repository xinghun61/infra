(function(window) {
  'use strict';

  let errBuff = {};
  const THRESHOLD_MS = 2000;

  function throttle(fn) {
    let last, timer;
    return () => {
      let now = Date.now();
      if (last && now < last + THRESHOLD_MS) {
        clearTimeout(timer);
        timer = setTimeout(() => {
          last = now;
          fn.apply();
        }, THRESHOLD_MS);
      } else {
        last = now;
        fn.apply();
      }
    };
  }

  let flushErrs = throttle(function() {
    // TODO(seanmccullough): Add xsrf token.
    fetch('/_/ecatcher', {
      method: 'POST',
      body: JSON.stringify(errBuff)
    }).catch(error => {
      window.console.error('Failed to report JS erors.', error);
    });
    errBuff = {};
  });

  window.addEventListener('error', evt => {
    let signature = evt.error.toString();
    if (evt.error instanceof Error) {
      signature += '\n' + evt.error.stack;
    }
    if (!errBuff[signature]) {
      errBuff[signature] = 0;
    }
    errBuff[signature] += 1;
    flushErrs();
  });

})(window);

