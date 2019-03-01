// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {standardTime, standardTimeShort,
  relativeTime} from './chops-timestamp-helpers.js';
import sinon from 'sinon';

let clock;

suite('chops-timestamp-helpers', () => {
  setup(() => {
    // Set clock to the Epoch.
    clock = sinon.useFakeTimers({
      now: new Date(0),
      shouldAdvanceTime: false,
    });
  });

  teardown(() => {
    clock.restore();
  });

  test('standardTime', () => {
    assert.equal(standardTime(new Date(), 'en-US', 'UTC'),
      `Thu, Jan 1, 1970, 12:00 AM UTC (just now)`);

    assert.equal(standardTime(new Date(1548808276 * 1000), 'en-US', 'UTC'),
      `Wed, Jan 30, 2019, 12:31 AM UTC`);
  });

  test('standardTimeShort', () => {
    assert.equal(standardTimeShort(new Date(),
      'en-US', 'UTC'), `just now`);

    assert.equal(standardTimeShort(new Date(1548808276 * 1000),
      'en-US', 'UTC'), `Jan 30, 2019`);
  });

  test('relativeTime future', () => {
    assert.equal(relativeTime(new Date()), `just now`);

    assert.equal(relativeTime(new Date(59 * 1000)), `just now`);

    assert.equal(relativeTime(new Date(60 * 1000)), `a minute from now`);
    assert.equal(relativeTime(new Date(2 * 60 * 1000)),
      `2 minutes from now`);
    assert.equal(relativeTime(new Date(59 * 60 * 1000)),
      `59 minutes from now`);

    assert.equal(relativeTime(new Date(60 * 60 * 1000)), `an hour from now`);
    assert.equal(relativeTime(new Date(2 * 60 * 60 * 1000)),
      `2 hours from now`);
    assert.equal(relativeTime(new Date(23 * 60 * 60 * 1000)),
      `23 hours from now`);

    assert.equal(relativeTime(new Date(24 * 60 * 60 * 1000)),
      `a day from now`);
    assert.equal(relativeTime(new Date(2 * 24 * 60 * 60 * 1000)),
      `2 days from now`);
    assert.equal(relativeTime(new Date(29 * 24 * 60 * 60 * 1000)),
      `29 days from now`);

    assert.equal(relativeTime(new Date(30 * 24 * 60 * 60 * 1000)), '');
  });

  test('relativeTime past', () => {
    const baseTime = 234234 * 1000;

    clock.tick(baseTime);

    assert.equal(relativeTime(new Date()), `just now`);

    assert.equal(relativeTime(new Date(baseTime - 59 * 1000)),
      `just now`);

    assert.equal(relativeTime(new Date(baseTime - 60 * 1000)),
      `a minute ago`);
    assert.equal(relativeTime(new Date(baseTime - 2 * 60 * 1000)),
      `2 minutes ago`);
    assert.equal(relativeTime(new Date(baseTime - 59 * 60 * 1000)),
      `59 minutes ago`);

    assert.equal(relativeTime(new Date(baseTime - 60 * 60 * 1000)),
      `an hour ago`);
    assert.equal(relativeTime(new Date(baseTime - 2 * 60 * 60 * 1000)),
      `2 hours ago`);
    assert.equal(relativeTime(new Date(baseTime - 23 * 60 * 60 * 1000)),
      `23 hours ago`);

    assert.equal(relativeTime(new Date(
      baseTime - 24 * 60 * 60 * 1000)), `a day ago`);
    assert.equal(relativeTime(new Date(
      baseTime - 2 * 24 * 60 * 60 * 1000)), `2 days ago`);
    assert.equal(relativeTime(new Date(
      baseTime - 29 * 24 * 60 * 60 * 1000)), `29 days ago`);

    assert.equal(relativeTime(new Date(
      baseTime - 30 * 24 * 60 * 60 * 1000)), '');
  });
});
