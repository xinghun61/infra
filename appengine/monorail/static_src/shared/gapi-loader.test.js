// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import sinon from 'sinon';
import loadGapi from './gapi-loader.js';

describe('loadGapi', () => {
  beforeEach(() => {
    sinon.stub(document, 'createElement');
    window.__gapiLoadStarted = false;
    window.CS_env = {
      gapi_client_id: 'rutabaga.id',
    };
  });

  it('only loads gapi once when called multiple times', () => {
    loadGapi();
    sinon.assert.calledOnce(document.createElement);

    loadGapi();
    loadGapi();
    sinon.assert.calledOnce(document.createElement);
  });
});
