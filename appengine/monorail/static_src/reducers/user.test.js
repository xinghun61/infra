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

    it('FETCH_PROJECTS_SUCCESS overrides existing entry in usersById', () => {
      const state = {
        ['123']: {
          projects: {
            ownerOf: [],
            memberOf: [],
            contributorTo: [],
            starredProjects: [],
          },
        },
      };

      const usersProjects = [
        {
          userRef: {userId: '123'},
          ownerOf: ['chromium'],
        },
      ];

      const newState = user.usersByIdReducer(state,
          {type: user.FETCH_PROJECTS_SUCCESS, usersProjects});

      assert.deepEqual(newState, {
        ['123']: {
          projects: {
            ownerOf: ['chromium'],
            memberOf: [],
            contributorTo: [],
            starredProjects: [],
          },
        },
      });
    });

    it('FETCH_PROJECTS_SUCCESS adds new entry to usersById', () => {
      const state = {
        ['123']: {
          projects: {
            ownerOf: [],
            memberOf: [],
            contributorTo: [],
            starredProjects: [],
          },
        },
      };

      const usersProjects = [
        {
          userRef: {userId: '543'},
          ownerOf: ['chromium'],
        },
        {
          userRef: {userId: '789'},
          memberOf: ['v8'],
        },
      ];

      const newState = user.usersByIdReducer(state,
          {type: user.FETCH_PROJECTS_SUCCESS, usersProjects});

      assert.deepEqual(newState, {
        ['123']: {
          projects: {
            ownerOf: [],
            memberOf: [],
            contributorTo: [],
            starredProjects: [],
          },
        },
        ['543']: {
          projects: {
            ownerOf: ['chromium'],
            memberOf: [],
            contributorTo: [],
            starredProjects: [],
          },
        },
        ['789']: {
          projects: {
            ownerOf: [],
            memberOf: ['v8'],
            contributorTo: [],
            starredProjects: [],
          },
        },
      });
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

    it('projects', () => {
      assert.deepEqual(user.projects(wrapUser({})), {});

      const state = wrapUser({
        currentUser: {userId: '123'},
        usersById: {
          ['123']: {
            projects: {
              ownerOf: ['chromium'],
              memberOf: ['v8'],
              contributorTo: [],
              starredProjects: [],
            },
          },
        },
      });

      assert.deepEqual(user.projects(state), {
        ownerOf: ['chromium'],
        memberOf: ['v8'],
        contributorTo: [],
        starredProjects: [],
      });
    });

    it('projectPerUser', () => {
      assert.deepEqual(user.projectsPerUser(wrapUser({})), new Map());

      const state = wrapUser({
        usersById: {
          ['123']: {
            projects: {
              ownerOf: ['chromium'],
              memberOf: ['v8'],
              contributorTo: [],
              starredProjects: [],
            },
          },
        },
      });

      assert.deepEqual(user.projects(state), new Map([
        ['123', {
          ownerOf: ['chromium'],
          memberOf: ['v8'],
          contributorTo: [],
          starredProjects: [],
        }],
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

    it('fetchProjects succeeds', async () => {
      const action = user.fetchProjects([{userId: '123'}]);

      prpcClient.call.returns(Promise.resolve({
        usersProjects: [
          {
            userRef: {
              userId: '123',
            },
            ownerOf: ['chromium'],
          },
        ],
      }));

      await action(dispatch);

      sinon.assert.calledWith(dispatch, {type: user.FETCH_PROJECTS_START});

      sinon.assert.calledWith(
          prpcClient.call,
          'monorail.Users',
          'GetUsersProjects',
          {userRefs: [{userId: '123'}]});

      sinon.assert.calledWith(dispatch, {
        type: user.FETCH_PROJECTS_SUCCESS,
        usersProjects: [
          {
            userRef: {
              userId: '123',
            },
            ownerOf: ['chromium'],
          },
        ],
      });
    });

    it('fetchProjects fails', async () => {
      const action = user.fetchProjects([{userId: '123'}]);

      const error = new Error('mistakes were made');
      prpcClient.call.returns(Promise.reject(error));

      await action(dispatch);

      sinon.assert.calledWith(dispatch, {type: user.FETCH_PROJECTS_START});

      sinon.assert.calledWith(
          prpcClient.call,
          'monorail.Users',
          'GetUsersProjects',
          {userRefs: [{userId: '123'}]});

      sinon.assert.calledWith(dispatch, {
        type: user.FETCH_PROJECTS_FAILURE,
        error,
      });
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
const wrapUser = (user) => ({user});
