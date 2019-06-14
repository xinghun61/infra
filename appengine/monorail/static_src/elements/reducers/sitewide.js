// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {combineReducers} from 'redux';
import {createReducer, createRequestReducer} from './redux-helpers.js';
import {prpcClient} from 'prpc-client-instance.js';

// Actions
const GET_SERVER_STATUS_START = 'GET_SERVER_STATUS_START';
const GET_SERVER_STATUS_SUCCESS = 'GET_SERVER_STATUS_SUCCESS';
const GET_SERVER_STATUS_FAILURE = 'GET_SERVER_STATUS_FAILURE';

/* State Shape
{
  bannerMessage: String,
  bannerTime: Number,
  readOnly: Boolean,
  requests: {
    serverStatus: Object,
  },
}
*/

// Reducers
const bannerMessageReducer = createReducer('', {
  [GET_SERVER_STATUS_SUCCESS]:
    (_state, action) => action.serverStatus.bannerMessage || '',
});

const bannerTimeReducer = createReducer(0, {
  [GET_SERVER_STATUS_SUCCESS]:
    (state, action) => action.serverStatus.bannerTime || 0,
});

const readOnlyReducer = createReducer(false, {
  [GET_SERVER_STATUS_SUCCESS]:
    (state, action) => action.serverStatus.readOnly || false,
});

const requestsReducer = combineReducers({
  serverStatus: createRequestReducer(
    GET_SERVER_STATUS_START,
    GET_SERVER_STATUS_SUCCESS,
    GET_SERVER_STATUS_FAILURE),
});

export const reducer = combineReducers({
  bannerMessage: bannerMessageReducer,
  bannerTime: bannerTimeReducer,
  readOnly: readOnlyReducer,

  requests: requestsReducer,
});

// Selectors
export const bannerMessage = (state) => state.sitewide.bannerMessage;
export const bannerTime = (state) => state.sitewide.bannerTime;
export const readOnly = (state) => state.sitewide.readOnly;
export const requests = (state) => state.sitewide.requests;

// Action Creators
export const getServerStatus = () => async (dispatch) => {
  dispatch({type: GET_SERVER_STATUS_START});

  try {
    const serverStatus = await prpcClient.call(
      'monorail.Sitewide', 'GetServerStatus', {});

    dispatch({type: GET_SERVER_STATUS_SUCCESS, serverStatus});
  } catch (error) {
    dispatch({type: GET_SERVER_STATUS_FAILURE, error});
  }
};
