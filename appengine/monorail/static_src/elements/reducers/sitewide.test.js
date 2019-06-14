// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import sinon from 'sinon';
import {assert} from 'chai';

import {store} from 'elements/reducers/base.js';
import {prpcClient} from 'prpc-client-instance.js';
import * as sitewide from './sitewide.js';

let prpcCall;
let stateUpdated;

describe('sitewide', () => {
  beforeEach(() => {
    prpcCall = sinon.stub(prpcClient, 'call');
    stateUpdated = new Promise((resolve) => {
      store.subscribe(resolve);
    });
  });

  afterEach(() => {
    prpcClient.call.restore();
  });

  describe('getServerStatus', () => {
    it('gets server status', async () => {
      prpcCall.callsFake(() => {
        return {
          bannerMessage: 'Message',
          bannerTime: 1234,
          readOnly: true,
        };
      });

      store.dispatch(sitewide.getServerStatus());

      await stateUpdated;
      const state = store.getState();

      assert.deepEqual(sitewide.bannerMessage(state), 'Message');
      assert.deepEqual(sitewide.bannerTime(state), 1234);
      assert.isTrue(sitewide.readOnly(state));

      assert.deepEqual(sitewide.requests(state), {
        serverStatus: {
          error: null,
          requesting: false,
        },
      });
    });

    it('gets empty status', async () => {
      prpcCall.callsFake(() => {
        return {};
      });

      store.dispatch(sitewide.getServerStatus());

      await stateUpdated;
      const state = store.getState();

      assert.deepEqual(sitewide.bannerMessage(state), '');
      assert.deepEqual(sitewide.bannerTime(state), 0);
      assert.isFalse(sitewide.readOnly(state));

      assert.deepEqual(sitewide.requests(state), {
        serverStatus: {
          error: null,
          requesting: false,
        },
      });
    });

    it('fails', async () => {
      const error = new Error('error');
      prpcCall.callsFake(() => {
        throw error;
      });

      store.dispatch(sitewide.getServerStatus());

      await stateUpdated;
      const state = store.getState();

      assert.deepEqual(sitewide.bannerMessage(state), '');
      assert.deepEqual(sitewide.bannerTime(state), 0);
      assert.isFalse(sitewide.readOnly(state));

      assert.deepEqual(sitewide.requests(state), {
        serverStatus: {
          error: error,
          requesting: false,
        },
      });
    });
  });
});
