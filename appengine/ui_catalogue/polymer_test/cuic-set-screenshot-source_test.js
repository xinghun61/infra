// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * Unit tests of cuic-set-screenshot-source custom element
 */
suite('set_screenshot_source', () => {

  test('Entering text sets the query string', async () => {
    const element = fixture('basic-test-fixture');
    const form = element.$.url_form;
    const input = element.$.url_input;
    input.value = 'file:///Testing';
    const submitReceived = eventPromise(form, 'submit');
    form.dispatchEvent(new Event('submit'));
    await submitReceived;
    assert.equal(element.queryParams_.screenshot_source, 'file:///Testing');
  })
})