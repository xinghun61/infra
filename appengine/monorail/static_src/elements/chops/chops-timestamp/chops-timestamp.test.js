// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert, expect} from 'chai';
import {ChopsTimestamp} from './chops-timestamp.js';
import {FORMATTER, SHORT_FORMATTER} from './chops-timestamp-helpers.js';
import sinon from 'sinon';

// The formatted date strings differ based on time zone and browser, so we can't
// use static strings for testing. We can't stub out the format method because
// it's native code and can't be modified. So just use the FORMATTER object.

let element;
let clock;

describe('chops-timestamp', () => {
  beforeEach(() => {
    element = document.createElement('chops-timestamp');
    document.body.appendChild(element);

    // Set clock to the Epoch.
    clock = sinon.useFakeTimers({
      now: new Date(0),
      shouldAdvanceTime: false,
    });
  });

  afterEach(() => {
    document.body.removeChild(element);
    clock.restore();
  });

  it('initializes', () => {
    assert.instanceOf(element, ChopsTimestamp);
  });

  it('changing timestamp changes date', async () => {
    const timestamp = 1548808276;
    element.timestamp = String(timestamp);

    await element.updateComplete;

    assert.include(element.shadowRoot.textContent,
      FORMATTER.format(new Date(timestamp * 1000)));
  });

  it('parses ISO dates', async () => {
    const timestamp = '2016-11-11';
    element.timestamp = timestamp;

    await element.updateComplete;

    assert.include(element.shadowRoot.textContent,
      FORMATTER.format(new Date(timestamp)));
  });

  it('invalid timestamp format', () => {
    expect(() => {
      element._parseTimestamp('random string');
    }).to.throw('Timestamp is in an invalid format.');
  });

  it('short time renders shorter time', async () => {
    element.short = true;
    element.timestamp = '5';

    await element.updateComplete;

    assert.include(element.shadowRoot.textContent,
      `just now`);

    element.timestamp = '60';

    await element.updateComplete;

    assert.include(element.shadowRoot.textContent,
      `a minute from now`);

    const timestamp = 1548808276;
    element.timestamp = String(timestamp);

    await element.updateComplete;

    assert.include(element.shadowRoot.textContent,
      SHORT_FORMATTER.format(timestamp * 1000));
  });
});
