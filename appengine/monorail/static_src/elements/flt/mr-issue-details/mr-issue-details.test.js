// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrIssueDetails} from './mr-issue-details.js';
import sinon from 'sinon';
import {actionType} from '../../redux/redux-mixin.js';
import * as issue from '../../redux/issue.js';


let element;

suite('mr-issue-details', () => {
  setup(() => {
    element = document.createElement('mr-issue-details');
    document.body.appendChild(element);

    sinon.stub(window.prpcClient, 'call').callsFake(
      () => Promise.resolve({}));
    sinon.spy(issue.update);

    // Disable Redux state mapping for testing.
    MrIssueDetails.mapStateToProps = () => {};
  });

  teardown(() => {
    document.body.removeChild(element);
    window.prpcClient.call.restore();
    element.dispatchAction({type: actionType.RESET_STATE});
  });

  test('initializes', () => {
    assert.instanceOf(element, MrIssueDetails);
  });
});
