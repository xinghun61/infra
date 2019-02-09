// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrApp} from './mr-app.js';
import {dom} from '@polymer/polymer/lib/legacy/polymer.dom.js';
import {flush} from '@polymer/polymer/lib/utils/flush.js';
import {actionType} from '../redux/redux-mixin.js';


let element;

suite('mr-app', () => {
  setup(() => {
    element = document.createElement('mr-app');
    document.body.appendChild(element);
    element.formsToCheck = [];
  });

  teardown(() => {
    document.body.removeChild(element);
    element.dispatchAction({type: actionType.RESET_STATE});
  });

  test('initializes', () => {
    assert.instanceOf(element, MrApp);
  });

  test('_loadApprovalPage loads approval page', () => {
    element._loadApprovalPage({
      query: {id: '234'},
      params: {project: 'chromium'},
    });

    const approvalElement = dom(element.root).querySelector('mr-approval-page');
    assert.isDefined(approvalElement, 'approval element is defined');
    assert.equal(approvalElement.projectName, 'chromium');
    assert.equal(approvalElement.issueId, 234);
  });
});
