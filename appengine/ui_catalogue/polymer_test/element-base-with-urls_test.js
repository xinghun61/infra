// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * Unit tests of cuic-comms-base custom element
 */
class CommsBaseTest extends ElementBaseWithUrls {
  static get is() {
    return 'cuic-comms-base-test'
  }

  constructor() {
    super();
  }

  get locationUrl_() {
    return new URL('file:///Dummy?screenshot_source=Test');
  }
}

window.customElements.define(CommsBaseTest.is, CommsBaseTest)

suite('comms_base', () => {

  test('screenshot location parameter', () => {
    element = fixture('basic-test-fixture');
    assert.deepEqual(element.screenshotLocationParam_(),
        {'screenshot_source' : 'Test'});
  });

  test('computeScreenshotUrl', () => {
    element = fixture('basic-test-fixture');
    assert.equal(element.computeScreenshotUrl_(23),
        '/service/23/image?screenshot_source=Test');
  });

  test('computeDataUrl', () => {
    element = fixture('basic-test-fixture');
    assert.equal(element.computeDataUrl_(23), '/service/23/data');
  });
});