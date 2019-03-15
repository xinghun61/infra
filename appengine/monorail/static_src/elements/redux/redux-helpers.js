
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
