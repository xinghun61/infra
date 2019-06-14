// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {connect} from 'pwa-helpers/connect-mixin.js';
import {applyMiddleware, combineReducers, compose, createStore} from 'redux';
import thunk from 'redux-thunk';
import * as issue from './issue.js';
import * as project from './project.js';
import * as sitewide from './sitewide.js';
import * as user from './user.js';
import * as ui from './ui.js';

// Actions
const RESET_STATE = 'RESET_STATE';

/* State Shape
{
  issue: Object,
  project: Object,
  sitewide: Object,
  user: Object,

  ui: Object,
}
*/

// Reducers
const reducer = combineReducers({
  issue: issue.reducer,
  project: project.reducer,
  user: user.reducer,
  sitewide: sitewide.reducer,

  ui: ui.reducer,
});

function rootReducer(state, action) {
  if (action.type == RESET_STATE) {
    state = undefined;
  }
  return reducer(state, action);
}

// Selectors

// Action Creators
export const resetState = () => ({type: RESET_STATE});

// Store

// For debugging with the Redux Devtools extension:
// https://chrome.google.com/webstore/detail/redux-devtools/lmhkpmbekcpmknklioeibfkpmmfibljd/
const composeEnhancers = window.__REDUX_DEVTOOLS_EXTENSION_COMPOSE__ || compose;
export const store = createStore(rootReducer, composeEnhancers(
  applyMiddleware(thunk)
));

export const connectStore = connect(store);
