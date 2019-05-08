// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {flush} from '@polymer/polymer/lib/utils/flush.js';
import {assert} from 'chai';
import {MrIssueDetails} from './mr-issue-details.js';
import sinon from 'sinon';
import * as issue from 'elements/reducers/issue.js';
import AutoRefreshPrpcClient from 'prpc.js';

let element;

describe('mr-issue-details', () => {
  beforeEach(() => {
    element = document.createElement('mr-issue-details');
    document.body.appendChild(element);

    window.prpcClient = new AutoRefreshPrpcClient(
      'token', 1234);

    sinon.stub(window.prpcClient, 'call').callsFake(
      () => Promise.resolve({}));
    sinon.spy(issue.update);
  });

  afterEach(() => {
    document.body.removeChild(element);
    window.prpcClient.call.restore();
  });

  it('initializes', () => {
    assert.instanceOf(element, MrIssueDetails);
  });
});
