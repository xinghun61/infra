// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import sinon from 'sinon';
import * as user from './user.js';
import {prpcClient} from 'prpc-client-instance.js';


let dispatch;

describe('user', () => {
  describe('reducers', () => {
    it('SET_PREFS_SUCCESS updates existing prefs with new prefs', () => {
      const state = {prefs: {
        testPref: 'true',
        anotherPref: 'hello-world',
      }};

      const newPrefs = [
        {name: 'anotherPref', value: 'override'},
        {name: 'newPref', value: 'test-me'},
      ];

      const newState = user.currentUserReducer(state,
          {type: user.SET_PREFS_SUCCESS, newPrefs});

      assert.deepEqual(newState, {prefs: {
        testPref: 'true',
        anotherPref: 'override',
        newPref: 'test-me',
      }});
    });
  });

  describe('selectors', () => {
    it('prefs', () => {
      const state = wrapCurrentUser({prefs: {
        testPref: 'true',
        anotherPref: 'hello-world',
      }});

      assert.deepEqual(user.prefs(state), new Map([
        ['testPref', 'true'],
        ['anotherPref', 'hello-world'],
      ]));
    });
  });

  describe('action creators', () => {
    beforeEach(() => {
      sinon.stub(prpcClient, 'call');

      dispatch = sinon.stub();
    });

    afterEach(() => {
      prpcClient.call.restore();
    });

    it('setPrefs', async () => {
      const action = user.setPrefs([{name: 'pref_name', value: 'true'}]);

      prpcClient.call.returns(Promise.resolve({}));

      await action(dispatch);

      sinon.assert.calledWith(dispatch, {type: user.SET_PREFS_START});

      sinon.assert.calledWith(
          prpcClient.call,
          'monorail.Users',
          'SetUserPrefs',
          {prefs: [{name: 'pref_name', value: 'true'}]});

      sinon.assert.calledWith(dispatch, {
        type: user.SET_PREFS_SUCCESS,
        newPrefs: [{name: 'pref_name', value: 'true'}],
      });
    });
  });
});

const wrapCurrentUser = (currentUser = {}) => ({user: {currentUser}});
