// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrApp} from './mr-app.js';
import {resetState} from '../redux/redux-mixin.js';


let element;

window.CS_env = {
  token: 'foo-token',
};

suite('mr-app', () => {
  setup(() => {
    element = document.createElement('mr-app');
    document.body.appendChild(element);
    element.formsToCheck = [];
  });

  teardown(() => {
    document.body.removeChild(element);
    element.dispatchAction(resetState());
  });

  test('initializes', () => {
    assert.instanceOf(element, MrApp);
  });

  test('_loadIssuePage loads issue page', async () => {
    await element._loadIssuePage({
      query: {id: '234'},
      params: {project: 'chromium'},
    });

    const issuePage = element.shadowRoot.querySelector('mr-issue-page');
    assert.isDefined(issuePage, 'issue page is defined');
    assert.equal(issuePage.issueRef.projectName, 'chromium');
    assert.equal(issuePage.issueRef.localId, 234);
  });
});
