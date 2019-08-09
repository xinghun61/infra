// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@chopsui/prpc-client/prpc-client.js';

/**
 * @fileoverview pRPC-related helper functions.
 */
export default class AutoRefreshPrpcClient {
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
    if (AutoRefreshPrpcClient.isTokenExpired(this.tokenExpiresSec)) {
      const headers = {'X-Xsrf-Token': this.token};
      const message = {
        token: this.token,
        tokenPath: 'xhr',
      };
      const freshToken = await this.prpcClient.call(
          'monorail.Sitewide', 'RefreshToken', message, headers);
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
      const headers = {'X-Xsrf-Token': this.token};
      return this.prpcClient.call(service, method, message, headers);
    });
  }

  /**
   * Check if the token is expired.
   * @param {number} tokenExpiresSec: the expiration time of the token.
   */
  static isTokenExpired(tokenExpiresSec) {
    const tokenExpiresDate = new Date(tokenExpiresSec * 1000);
    return tokenExpiresDate < new Date();
  }
}
