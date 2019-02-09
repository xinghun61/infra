// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrIssueDetails} from './mr-issue-details.js';
import sinon from 'sinon';
import {flush} from '@polymer/polymer/lib/utils/flush.js';
import {actionCreator, actionType} from '../../redux/redux-mixin.js';


let element;

suite('mr-issue-details', () => {
  setup(() => {
    element = document.createElement('mr-issue-details');
    document.body.appendChild(element);

    window.prpcClient = {
      call: () => Promise.resolve({}),
    };
    sinon.spy(window.prpcClient, 'call');
    sinon.spy(actionCreator, 'updateIssue');

    // Disable Redux state mapping for testing.
    MrIssueDetails.mapStateToProps = () => {};
  });

  teardown(() => {
    document.body.removeChild(element);
    window.prpcClient.call.restore();
    actionCreator.updateIssue.restore();
    element.dispatchAction({type: actionType.RESET_STATE});
  });

  test('initializes', () => {
    assert.instanceOf(element, MrIssueDetails);
  });

  test('_updateDescriptionHandler generates description change', () => {
    element.token = '1234';
    element.issueId = 5;
    element.projectName = 'chromium';
    element._updateDescriptionHandler({detail: {
        commentContent: 'comment data',
        sendEmail: true,
      }
    });

    flush();

    assert.deepEqual(actionCreator.updateIssue.getCall(0).args[1], {
      trace: {token: '1234'},
      issueRef: {
        projectName: 'chromium',
        localId: 5,
      },
      commentContent: 'comment data',
      isDescription: true,
      sendEmail: true,
    });
    assert.isTrue(actionCreator.updateIssue.calledOnce);
  });

  test('sendEmail toggles email sending for description changes', () => {
    element.token = 'abcd';
    element.issueId = 10;
    element.projectName = 'chromium';

    const editor = element.shadowRoot.querySelector('#editDescription');

    editor.sendEmail = false;
    editor.save();

    assert.deepEqual(actionCreator.updateIssue.getCall(0).args[1], {
      trace: {token: 'abcd'},
      issueRef: {
        projectName: 'chromium',
        localId: 10,
      },
      commentContent: '',
      isDescription: true,
      sendEmail: false,
    });
    assert.isTrue(actionCreator.updateIssue.calledOnce);

    editor.sendEmail = true;
    editor.save();

    assert.deepEqual(actionCreator.updateIssue.getCall(1).args[1], {
      trace: {token: 'abcd'},
      issueRef: {
        projectName: 'chromium',
        localId: 10,
      },
      commentContent: '',
      isDescription: true,
      sendEmail: true,
    });
    assert.isTrue(actionCreator.updateIssue.calledTwice);
  });
});
