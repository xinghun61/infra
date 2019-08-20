
// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

export const createReducer = (initialState, handlers) => {
  return function reducer(state = initialState, action) {
    if (handlers.hasOwnProperty(action.type)) {
      return handlers[action.type](state, action);
    } else {
      return state;
    }
  };
};

const DEFAULT_REQUEST_KEY = '*';

export const createKeyedRequestReducer = (start, success, failure) => {
  return createReducer({}, {
    [start]: (state, action) => {
      const requestKey = action.requestKey || DEFAULT_REQUEST_KEY;

      return {
        ...state,
        [requestKey]: {
          requesting: true,
          error: null,
        },
      };
    },
    [success]: (state, action) =>{
      const requestKey = action.requestKey || DEFAULT_REQUEST_KEY;

      return {
        ...state,
        [requestKey]: {
          requesting: false,
          error: null,
        },
      };
    },
    [failure]: (state, action) => {
      const requestKey = action.requestKey || DEFAULT_REQUEST_KEY;

      return {
        ...state,
        [requestKey]: {
          requesting: false,
          error: action.error,
        },
      };
    },
  });
};

export const createRequestReducer = (start, success, failure) => {
  return createReducer({requesting: false, error: null}, {
    [start]: (_state, _action) => ({
      requesting: true,
      error: null,
    }),
    [success]: (_state, _action) =>({
      requesting: false,
      error: null,
    }),
    [failure]: (_state, action) => ({
      requesting: false,
      error: action.error,
    }),
  });
};
