// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * Unit tests of cuic-single-screenshot custom element
 */

suite('single_screenshot', () => {

  setup(() => {
    replace('iron-location').with('empty-fake');
    replace('iron-image').with('empty-fake');
    stub('cuic-single-screenshot', {computeScreenshotUrl_ : (key) => {
      return 'DummyUrl/' + key;
    }});
  });

  test('image link', () => {
    const baseElement = fixture('single-screenshot-test-fixture');
    assert(baseElement);
    assert.equal(baseElement.computeLink_(23,
        {'screenshot_source':'http://xxx'}),
        '/cuic-screenshot-view?screenshot_source=http://xxx&key=23');
    baseElement.set('query_', 'screenshot_source=http://yyy');
    baseElement.set('key', 42);
    assert.equal(baseElement.$['screenshot-link'].getAttribute('href'),
        '/cuic-screenshot-view?screenshot_source=http://yyy&key=42');
    assert.equal(baseElement.$['screenshot-image'].src, 'DummyUrl/42');
  });
});