// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {FORMATTER}
  from 'elements/chops/chops-timestamp/chops-timestamp-helpers.js';
import {MrSiteBanner} from './mr-site-banner.js';


let element;

describe('mr-site-banner', () => {
  beforeEach(() => {
    element = document.createElement('mr-site-banner');
    document.body.appendChild(element);
  });

  afterEach(() => {
    document.body.removeChild(element);
  });

  it('initializes', () => {
    assert.instanceOf(element, MrSiteBanner);
  });

  it('displays a banner message', async () => {
    element.bannerMessage = 'Message';
    await element.updateComplete;
    assert.equal(element.shadowRoot.textContent.trim(), 'Message');
    assert.isNull(element.shadowRoot.querySelector('chops-timestamp'));
  });

  it('displays the banner timestamp', async () => {
    const timestamp = 1560450600;

    element.bannerMessage = 'Message';
    element.bannerTime = timestamp;
    await element.updateComplete;

    const chopsTimestamp = element.shadowRoot.querySelector('chops-timestamp');

    // The formatted date strings differ based on time zone and browser, so we
    // can't use static strings for testing. We can't stub out the format method
    // because it's native code and can't be modified. So just use the FORMATTER
    // object.
    assert.include(
      chopsTimestamp.shadowRoot.textContent,
      FORMATTER.format(new Date(timestamp * 1000)));
  });

  it('hides when there is no banner message', async () => {
    await element.updateComplete;
    assert.isTrue(element.hidden);
  });
});
