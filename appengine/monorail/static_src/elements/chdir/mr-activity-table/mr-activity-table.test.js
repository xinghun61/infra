// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrActivityTable} from './mr-activity-table.js';
import sinon from 'sinon';

const SECONDS_PER_DAY = 24 * 60 * 60;

let element;

describe('mr-activity-table', () => {
  beforeEach(() => {
    element = document.createElement('mr-activity-table');
    document.body.appendChild(element);
  });

  afterEach(() => {
    document.body.removeChild(element);
  });

  it('initializes', () => {
    assert.instanceOf(element, MrActivityTable);
  });

  it('no comments makes empty activity array', () => {
    element.comments = [];

    for (let i = 0; i < 93; i++) {
      assert.equal(0, element._activityArray[i].commentCount);
    }
  });

  it('activity array handles old comments', () => {
    // 94 days since EPOCH.
    sinon.stub(element, '_todayUnixTime').get(() => 94 * SECONDS_PER_DAY);

    element.comments = [
      {content: 'blah', timestamp: 0}, // too old.
      {content: 'ignore', timestamp: 100}, // too old.
      {
        content: 'comment',
        timestamp: SECONDS_PER_DAY + 1, // barely young enough.
      },
      {content: 'hello', timestamp: SECONDS_PER_DAY + 10}, // same day as above.
      {content: 'world', timestamp: SECONDS_PER_DAY * 94}, // today
    ];

    assert.equal(93, element._activityArray.length);
    assert.equal(2, element._activityArray[0].commentCount);
    for (let i = 1; i < 92; i++) {
      assert.equal(0, element._activityArray[i].commentCount);
    }
    assert.equal(1, element._activityArray[92].commentCount);
  });
});
