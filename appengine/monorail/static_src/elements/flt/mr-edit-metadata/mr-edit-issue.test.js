// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrEditIssue} from './mr-edit-issue.js';
import {actionType} from '../../redux/redux-mixin.js';
import sinon from 'sinon';

let element;

suite('mr-edit-issue', () => {
  setup(() => {
    element = document.createElement('mr-edit-issue');
    document.body.appendChild(element);
  });

  teardown(() => {
    document.body.removeChild(element);
    element.dispatchAction({type: actionType.RESET_STATE});
  });

  test('initializes', () => {
    assert.instanceOf(element, MrEditIssue);
  });

  test('scrolls into view', () => {
    const header = element.shadowRoot.querySelector('#makechanges');
    sinon.stub(header, 'scrollIntoView');

    element.focusId = 'makechanges';

    assert.isTrue(header.scrollIntoView.calledOnce);

    header.scrollIntoView.restore();
  });
});
