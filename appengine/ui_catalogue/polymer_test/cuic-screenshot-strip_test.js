// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * Unit tests of cuic-screenshot-strip custom element
 */

suite('screenshot_strip', () => {

  let lastFilters;
  let screenshotStrip;

  class FakeScreenshots  extends Polymer.Element {
    static get is() {
      return 'fake-cuic-screenshots';
    }

    requestScreenshotsForSelector(filters) {
      lastFilters = filters;
    }
  }

  window.customElements.define(FakeScreenshots.is, FakeScreenshots);

  setup(() => {
    replace('cuic-screenshots').with('fake-cuic-screenshots');
    replace('cuic-single-screenshot').with('fake-cuic-single-screenshot');
    screenshotStrip = fixture('screenshot-strip-test-fixture');
  });

  test('Initial state', async () => {
    // Queue checking page until it is fully built.
    await zeroTimeout();
    assert(!screenshotStrip.$['has-screenshots'].if);
    assert(screenshotStrip.$['no-screenshots'].if);
  });

  test('Filter change', async () => {
    screenshotStrip.set('selection', {a: 'a', b: 'b'} );
    await zeroTimeout();
    assert.deepEqual(lastFilters, {a: 'a', b: 'b'});
  });

  test('Selection change', async () => {
    screenshotStrip.$.screenshots.dispatchEvent(
        new CustomEvent('screenshots-received', {detail: [
            {label: 'a', key: 1},
            {label: 'c', key: 2},
            {label: 'b', key: 3}]} ));
    // Queue checking page until it is fully built.
    await zeroTimeout();
    assert(screenshotStrip.$['has-screenshots'].if);
    assert(!screenshotStrip.$['no-screenshots'].if);
    const singleScreenshots = screenshotStrip.shadowRoot.querySelectorAll(
        'fake-cuic-single-screenshot');
    // For some unknown reason iron-list creates some extra hidden elements.
    // Ignore these.
    const screenshotArray = Array.from(singleScreenshots).filter(
        s => !s.hidden
    );
    assert.deepEqual(screenshotArray.map(s => s.label), ['a', 'b', 'c']);
    assert.deepEqual(screenshotArray.map(s => s.key), [1, 3, 2]);
  });

});