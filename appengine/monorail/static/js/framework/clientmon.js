/* Copyright 2016 The Chromium Authors. All Rights Reserved.
 *
 * Use of this source code is governed by a BSD-style
 * license that can be found in the LICENSE file or at
 * https://developers.google.com/open-source/licenses/bsd
 */

(function(window) {
  'use strict';

  // This code sets up a reporting mechanism for uncaught javascript errors
  // to the server. It reports at most every THRESHOLD_MS milliseconds and
  // each report contains error signatures with counts.

  let errBuff = {};
  let THRESHOLD_MS = 2000;

  function throttle(fn) {
    let last, timer;
    return function() {
      let now = Date.now();
      if (last && now < last + THRESHOLD_MS) {
        clearTimeout(timer);
        timer = setTimeout(function() {
          last = now;
          fn.apply();
        }, THRESHOLD_MS + last - now);
      } else {
        last = now;
        fn.apply();
      }
    };
  }
  let flushErrs = throttle(function() {
    let data = {errors: JSON.stringify(errBuff)};
    CS_doPost('/_/clientmon.do', null, data);
    errBuff = {};
  });

  window.addEventListener('error', function(evt) {
    let signature = evt.message;
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
