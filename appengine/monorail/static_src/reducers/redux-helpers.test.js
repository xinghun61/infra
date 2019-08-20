// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {createRequestReducer,
  createKeyedRequestReducer} from './redux-helpers.js';

let keyedRequestReducer;
let requestReducer;

describe('redux-helpers', () => {
  describe('createKeyedRequestReducer', () => {
    beforeEach(() => {
      keyedRequestReducer = createKeyedRequestReducer(
          'REQUEST_START', 'REQUEST_SUCCESS', 'REQUEST_FAILURE');
    });

    it('sets requesting to true on start', () => {
      assert.deepEqual(keyedRequestReducer({}, {type: 'REQUEST_START'}),
          {['*']: {requesting: true, error: null}});
    });

    it('sets requesting to false on success', () => {
      assert.deepEqual(keyedRequestReducer({}, {type: 'REQUEST_SUCCESS'}),
          {['*']: {requesting: false, error: null}});
    });

    it('sets error message on failure', () => {
      assert.deepEqual(keyedRequestReducer({}, {
        type: 'REQUEST_FAILURE',
        error: 'hello',
      }), {['*']: {requesting: false, error: 'hello'}});
    });

    it('preserves previous request state on start', () => {
      const initialState = {
        ['*']: {requesting: false, error: 'hello'},
      };
      assert.deepEqual(keyedRequestReducer(initialState, {
        type: 'REQUEST_START',
        requestKey: 'chromium:11',
      }), {
        ['*']: {requesting: false, error: 'hello'},
        ['chromium:11']: {requesting: true, error: null},
      });
    });

    it('preserves previous request state on success', () => {
      const initialState = {
        ['*']: {requesting: false, error: 'hello'},
        ['chromium:11']: {requesting: true, error: null},
      };
      assert.deepEqual(keyedRequestReducer(initialState, {
        type: 'REQUEST_SUCCESS',
        requestKey: 'chromium:11',
      }), {
        ['*']: {requesting: false, error: 'hello'},
        ['chromium:11']: {requesting: false, error: null},
      });
    });

    it('preserves previous request state on failure', () => {
      const initialState = {
        ['*']: {requesting: false, error: 'hello'},
        ['chromium:11']: {requesting: false, error: null},
      };
      assert.deepEqual(keyedRequestReducer(initialState, {
        type: 'REQUEST_FAILURE',
        requestKey: 'chromium:11',
        error: 'something went wrong',
      }), {
        ['*']: {requesting: false, error: 'hello'},
        ['chromium:11']: {requesting: false, error: 'something went wrong'},
      });
    });
  });

  describe('createRequestReducer', () => {
    beforeEach(() => {
      requestReducer = createRequestReducer(
          'REQUEST_START', 'REQUEST_SUCCESS', 'REQUEST_FAILURE');
    });

    it('sets requesting to true on start', () => {
      assert.deepEqual(requestReducer({}, {type: 'REQUEST_START'}),
          {requesting: true, error: null});
    });

    it('sets requesting to false on success', () => {
      assert.deepEqual(requestReducer({}, {type: 'REQUEST_SUCCESS'}),
          {requesting: false, error: null});
    });

    it('sets error message on failure', () => {
      assert.deepEqual(requestReducer({}, {
        type: 'REQUEST_FAILURE',
        error: 'hello',
      }), {requesting: false, error: 'hello'});
    });
  });
});
