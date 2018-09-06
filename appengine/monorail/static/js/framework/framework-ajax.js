/* Copyright 2016 The Chromium Authors. All Rights Reserved.
 *
 * Use of this source code is governed by a BSD-style
 * license that can be found in the LICENSE file or at
 * https://developers.google.com/open-source/licenses/bsd
 */


/**
 * @fileoverview AJAX-related helper functions.
 */


var DEBOUNCE_THRESH_MS = 2000;


/**
 * Simple debouncer to handle text input.  Don't try to hit the server
 * until the user has stopped typing for a few seconds.  E.g.,
 * var debouncedKeyHandler = debounce(keyHandler);
 * el.addEventListener('keyup', debouncedKeyHandler);
 */
function debounce(func, opt_threshold_ms) {
  var timeout;
  return function() {
    var context = this, args = arguments;
    var later = function() {
      timeout = null;
      func.apply(context, args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, opt_threshold_ms || DEBOUNCE_THRESH_MS);
  };
}


/**
 * Builds a POST string from a parameter dictionary.
 * @param {Array|Object} args: parameters to encode. Either an object
 *   mapping names to values or an Array of doubles containing [key, value].
 * @return {string} encoded POST data.
 */
function CS_postData(args) {
  var params = [];

  if (args instanceof Array) {
    for (var key in args) {
      var inputValue = args[key];
      var name = inputValue[0];
      var value = inputValue[1];
      if (value !== undefined) {
        params.push(name + "=" + encodeURIComponent(String(value)));
      }
    }
  } else {
    for (var key in args) {
      params.push(key + "=" + encodeURIComponent(String(args[key])));
    }
  }

  params.push('token=' + encodeURIComponent(window.prpcClient.token));

  return params.join('&');
}

/**
 * Helper for an extremely common kind of XHR: a POST with an XHRF token
 * where we silently ignore server or connectivity errors.  If the token
 * has expired, get a new one and retry the original request with the new
 * token.
 * @param {string} url request destination.
 * @param {function(event)} callback function to be called
 *   upon successful completion of the request.
 * @param {Object} args parameters to encode as POST data.
 */
function CS_doPost(url, callback, args) {
  window.prpcClient.ensureTokenIsValid().then(() => {
    var xh = XH_XmlHttpCreate();
    XH_XmlHttpPOST(xh, url, CS_postData(args), callback);
  });
}


/**
 * Helper function to strip leading junk characters from a JSON response
 * and then parse it into a JS constant.
 *
 * The reason that "}])'\n" is prepended to the response text is that
 * it makes it impossible for a hacker to hit one of our JSON servlets
 * via a <script src="..."> tag and do anything with the result.  Even
 * though a JSON response is just a constant, it could be passed into
 * hacker code by tricks such as overriding the array constructor.
 */
function CS_parseJSON(xhr) {
  return JSON.parse(xhr.responseText.substr(5));
}


/**
 * Promise-based version of CS_parseJSON using the fetch API.
 *
 * Sends a GET request to a JSON endpoint then strips the XSSI prefix off
 * of the response before resolving the promise.
 *
 * Args:
 *   url (string): The URL to fetch.
 * Returns:
 *   A promise, resolved when the request returns. Also be sure to call
 *   .catch() on the promise (or wrap in a try/catch if using async/await)
 *   if you don't want errors to halt script execution.
 */
function CS_fetch(url) {
  return fetch(url, {credentials: 'same-origin'})
    .then((res) => res.text())
    .then((rawResponse) => JSON.parse(rawResponse.substr(5)));
}


/**
 * After we refresh the form token, we need to actually submit the form.
 * formToSubmit keeps track of which form the user was trying to submit.
 */
var formToSubmit = null;

/**
 * If the form token that was generated when the page was served has
 * now expired, then request a refreshed token from the server, and
 * don't submit the form until after it arrives.
 */
function refreshTokens(event, formToken, formTokenPath, tokenExpiresSec) {
  if (!isTokenExpired(tokenExpiresSec)) {
    return;
  }

  formToSubmit = event.target;
  event.preventDefault();
  const message = {
    token: formToken,
    tokenPath: formTokenPath
  };
  const refreshTokenPromise = window.prpcClient.call(
      'monorail.Sitewide', 'RefreshToken', message);

  refreshTokenPromise.then(freshToken => {
    var tokenFields = document.querySelectorAll("input[name=token]");
    for (var i = 0; i < tokenFields.length; ++i) {
        tokenFields[i].value = freshToken.token;
    }
    if (formToSubmit) {
      formToSubmit.submit();
    }
  });
}
