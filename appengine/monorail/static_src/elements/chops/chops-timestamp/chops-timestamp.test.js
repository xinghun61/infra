// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert, expect} from 'chai';
import {ChopsTimestamp} from './chops-timestamp.js';
import {flush} from '@polymer/polymer/lib/utils/flush.js';
import sinon from 'sinon';

let element;
let clock;

suite('chops-timestamp', () => {
  setup(() => {
    element = document.createElement('chops-timestamp');
    document.body.appendChild(element);

    // Set clock to the Epoch.
    clock = sinon.useFakeTimers({
        now: new Date(0),
        shouldAdvanceTime: false,
    });

    // Explicitly set timezone because we can't depend on
    // the timezone of the local testing environment to be the same.
    element.timezone = 'UTC';
  });

  teardown(() => {
    document.body.removeChild(element);
    clock.restore();
  });

  test('initializes', () => {
    assert.instanceOf(element, ChopsTimestamp);
  });

  test('changing timestamp changes date', () => {
    element.timestamp = '1548808276';

    assert.include(element.shadowRoot.textContent,
      `Wed, Jan 30, 2019, 12:31 AM UTC`);
  });

  test('parses ISO dates', () => {
    element.timestamp = '2016-11-11';

    assert.include(element.shadowRoot.textContent,
      `Fri, Nov 11, 2016, 12:00 AM UTC`);
  });

  test('invalid timestamp format', () => {
    expect(() => {
      element.timestamp = 'random string';
    }).to.throw('Timestamp is in an invalid format.');
  });

  test('short time renders shorter time', () => {
    element.short = true;
    element.timestamp = '5';

    assert.include(element.shadowRoot.textContent,
      `just now`);

    element.timestamp = '60';

    assert.include(element.shadowRoot.textContent,
      `a minute from now`);

    element.timestamp = '1548808276';

    assert.include(element.shadowRoot.textContent,
      `Jan 30, 2019`);
  });
});
