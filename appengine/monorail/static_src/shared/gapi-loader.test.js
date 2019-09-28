// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import sinon from 'sinon';
import loadGapi, {fetchGapiEmail, getSigninInstance} from './gapi-loader.js';

describe('gapi-loader', () => {
  let signinImpl;
  beforeEach(() => {
    window.CS_env = {gapi_client_id: 'rutabaga'};
    signinImpl = {
      init: sinon.stub(),
      getUserProfileAsync: () => (
        Promise.resolve({
          getEmail: sinon.stub().returns('rutabaga@google.com'),
        })
      ),
    };
    // Preload signinImpl with a fake for testing.
    getSigninInstance(signinImpl, true);
    delete window.__gapiLoadPromise;
  });

  afterEach(() => {
    delete window.CS_env;
  });

  describe('loadGapi()', () => {
    it('errors out if no client_id', () => {
      window.CS_env.gapi_client_id = undefined;
      assert.throws(() => loadGapi());
    });

    it('returns the same promise when called multiple times', () => {
      const callOne = loadGapi();
      const callTwo = loadGapi();

      assert.strictEqual(callOne, callTwo);
      assert.strictEqual(callOne, window.__gapiLoadPromise);
      assert.strictEqual(callTwo, window.__gapiLoadPromise);
      assert.instanceOf(callOne, Promise);
    });

    it('calls init and returns the current email if any', async () => {
      const response = await loadGapi();
      sinon.assert.calledWith(signinImpl.init, window.CS_env.gapi_client_id,
          ['client'], ['https://www.googleapis.com/auth/buganizer']);
      assert.equal(response, 'rutabaga@google.com');
    });
  });

  describe('fetchGapiEmail()', () => {
    it('returns a profile for allowed domains', async () => {
      getSigninInstance({
        getUserProfileAsync: () => Promise.resolve({
          getEmail: sinon.stub().returns('rutabaga@google.com'),
        }),
      }, true);
      assert.deepEqual(await fetchGapiEmail(), 'rutabaga@google.com');
    });

    it('returns nothing for non-allowed domains', async () => {
      getSigninInstance({
        getUserProfileAsync: () => Promise.resolve({
          getEmail: sinon.stub().returns('rutabaga@rutabaga.com'),
        }),
      }, true);
      assert.deepEqual(await fetchGapiEmail(), null);
    });
  });
});
