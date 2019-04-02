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

  test('_loadApprovalPage loads approval page', () => {
    element._loadApprovalPage({
      query: {id: '234'},
      params: {project: 'chromium'},
    });

    const approvalElement = element.shadowRoot.querySelector('mr-issue-page');
    assert.isDefined(approvalElement, 'approval element is defined');
    assert.equal(approvalElement.issueRef.projectName, 'chromium');
    assert.equal(approvalElement.issueRef.localId, 234);
  });
});
