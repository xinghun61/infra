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

  /**
   * Check if the token is expired.
   * @param {number} tokenExpiresSec: the expiration time of the token.
   */
  function isTokenExpired(tokenExpiresSec) {
    const tokenExpiresDate = new Date(tokenExpiresSec * 1000);
    return tokenExpiresDate < new Date();
  }


  class AutoRefreshPrpcClient {
    constructor(token, tokenExpiresSec) {
      this.token = token;
      this.tokenExpiresSec = tokenExpiresSec;
      this.prpcClient = new window.chops.rpc.PrpcClient({
        insecure: Boolean(location.hostname === 'localhost'),
        fetchImpl: (url, options) => {
          options.credentials = 'same-origin';
          return fetch(url, options);
        },
      });
    }

    /**
     * Refresh the XSRF token if necessary.
     * TODO(ehmaldonado): Figure out how to handle failures to refresh tokens.
     * Maybe fire an event that a root page handler could use to show a message.
     * @async
     */
    async ensureTokenIsValid() {
      if (isTokenExpired(this.tokenExpiresSec)) {
        const message = {
          trace: {
            token: this.token
          },
          token: this.token,
          tokenPath: 'xhr',
        };
        const freshToken = await this.prpcClient.call(
            'monorail.Sitewide', 'RefreshToken', message);
        this.token = freshToken.token;
        this.tokenExpiresSec = freshToken.tokenExpiresSec;
      }
    }

    /**
     * Sends a pRPC request. Adds this.token to the request message after making
     * sure it is fresh.
     * @param service {string} Full service name, including package name.
     * @param method {string} Service method name.
     * @param message {Object} The protobuf message to send.
     */
    call(service, method, message) {
      return this.ensureTokenIsValid().then(() => {
          message.trace = {token: this.token};
          return this.prpcClient.call(service, method, message);
      });
    }
  }

  window.__prpc = window.__prpc || {};
  Object.assign(window.__prpc, {AutoRefreshPrpcClient});
})(window);
