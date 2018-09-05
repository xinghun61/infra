/* Copyright 2018 The Chromium Authors. All Rights Reserved.
 *
 * Use of this source code is governed by a BSD-style
 * license that can be found in the LICENSE file or at
 * https://developers.google.com/open-source/licenses/bsd
 */


/**
 * @fileoverview pRPC-related helper functions.
 */

(function (window){
  'use strict';

  const EXPIRATION_BUFFER_MS = 50;

  const prpcClient = new window.chops.rpc.PrpcClient({
    insecure: Boolean(location.hostname === 'localhost'),
    fetchImpl: (url, options) => {
      options.credentials = 'same-origin';
      return fetch(url, options);
    },
  });


  /**
   * Check if the token is expired.
   * @param {number} opt_tokenExpiresSec: the optional expiration time of the
   * token. If not supplied, CS_env.tokenExpiresSec will be used.
   */
  function isTokenExpired(opt_tokenExpiresSec) {
    const expiresSec = opt_tokenExpiresSec || CS_env.tokenExpiresSec;
    // Leave some buffer to account for the time it might take to fire the
    // request.
    const tokenExpiresDate = new Date(expiresSec * 1000 - EXPIRATION_BUFFER_MS);
    return tokenExpiresDate < new Date();
  }


  /**
   * Refresh the XSRF token if necessary.
   * TODO(ehmaldonado): Display a message to the user asking them to refresh the
   * page if we fail to refresh the token.
   * @param {string} opt_token: an optional XSRF token. If not supplied, defaults
   * to CS_env.token.
   * @param {string} opt_tokenPath: the optional path for the XSRF token. If not
   * supplied, defaults to 'token'.
   * @param {number} opt_tokenExpiresSec: the expiration time of the token. If not
   * supplied, defaults to CS_env.tokenExpiresSec.
   */
  function ensureTokenIsValid(opt_token, opt_tokenPath, opt_tokenExpiresSec) {
    const token = opt_token || CS_env.token;
    const tokenPath = opt_tokenPath || 'xhr';
    const tokenExpiresSec = opt_tokenExpiresSec || CS_env.tokenExpiresSec;
    if (isTokenExpired(tokenExpiresSec)) {
      // In EZT some tokens are limited to work with the specific servlet path
      // of the servlet that processes them, but to make a pRPC request we need
      // to authenticate with a token with the 'xhr' path.
      // CS_env.token is always be defined in EZT, and we can use it to make the
      // request. Polymer pages don't define CS_env, but all tokens refer to the
      // 'xhr' so we can use the token we're passed to make the request.
      let xhrToken = token;
      if (typeof CS_env !== 'undefined') {
        xhrToken = CS_env.token;
      }
      const message = {
        trace: {
          token: xhrToken
        },
        token: token,
        tokenPath: tokenPath
      };
      const refreshTokenPromise = prpcClient.call(
          'monorail.Sitewide', 'RefreshToken', message);
      return refreshTokenPromise;
    } else {
      return new Promise(resolve => {
        resolve({
          token: token,
          tokenExpiresSec: tokenExpiresSec
        });
      });
    }
  }


  /**
   * Sends a pRPC request. Adds CS_env.token to the request message after making
   * sure it is fresh.
   * @async
   * @param service {string} Full service name, including package name.
   * @param method {string} Service method name.
   * @param message {Object} The protobuf message to send.
   */
  function call(service, method, message, opt_token, opt_tokenExpiresSec) {
    const token = opt_token || CS_env.token;
    const tokenExpiresSec = opt_tokenExpiresSec || CS_env.tokenExpiresSec;
    return ensureTokenIsValid(token, 'xhr', tokenExpiresSec).then(() => {
      message.trace = {token: token};
      return prpcClient.call(service, method, message);
    });
  }

  window.__prpc = window.__prpc || {};
  Object.assign(
      window.__prpc, {prpcClient, isTokenExpired, ensureTokenIsValid, call});
})(window);
