// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrEditIssue} from './mr-edit-issue.js';
import sinon from 'sinon';

let element;

suite('mr-edit-issue', () => {
  setup(() => {
    element = document.createElement('mr-edit-issue');
    document.body.appendChild(element);
  });

  teardown(() => {
    document.body.removeChild(element);
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

  test('shows current status even if not defined for project', () => {
    const editMetadata = element.shadowRoot.querySelector('mr-edit-metadata');
    assert.deepEqual(editMetadata.statuses, []);

    element.projectConfig = {statusDefs: [
      {status: 'hello'},
      {status: 'world'},
    ]};

    assert.deepEqual(editMetadata.statuses, [
      {status: 'hello'},
      {status: 'world'},
    ]);

    element.issue = {
      statusRef: {status: 'hello'},
    };

    assert.deepEqual(editMetadata.statuses, [
      {status: 'hello'},
      {status: 'world'},
    ]);

    element.issue = {
      statusRef: {status: 'weirdStatus'},
    };

    assert.deepEqual(editMetadata.statuses, [
      {status: 'weirdStatus'},
      {status: 'hello'},
      {status: 'world'},
    ]);
  });
});
