// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * Unit tests of cuic-selector-view custom element
 */
suite('screenshot_view', () => {

  let server;

  setup(() => {
    server = sinon.fakeServer.create();
    server.respondImmediately = true;
    stub('cuic-screenshot-view', {screenshotSource_ : () => {
        return 'https://example.com/dummy';
      }});
    replace('iron-image').with('fake-iron-image')
  });

  test('Screenshot view creation', async () => {
    const data =
        { 'filters':
          { 'f1' : 'filter value 1',
            'f2' : 'filter value 2'},
          'userTags' : ['tag1', 'tag2', 'tag3'],
          'metadata':  {'m1': 'metadata'}};
    server.respondWith(
        [200, {'Content-Type': 'application/json'}, JSON.stringify(data)]);
    const screenshotView = fixture('screenshot-view-test-fixture');
    // Queue checking page until it is fully built.
    await zeroTimeout();
    assert.equal(server.requests.length, 1);
    const request = server.requests[0];
    assert(request);
    assert.equal(request.url,
        '/service/23/data?screenshot_source=' +
        encodeURIComponent('https://example.com/dummy'));
    assert.equal(request.method, 'GET');
    // Check the image
    assert.equal(screenshotView.$.image.src,
        '/service/23/image?screenshot_source=' +
        encodeURIComponent('https://example.com/dummy'));
    // Check that the fetched data has been added to the page
    const text = screenshotView.shadowRoot.textContent;
    lines = text.split(/\n/).map(s => s.trim());
    assert.includeMembers(lines,
        [ 'f1: filter value 1',
          'f2: filter value 2',
          'tag1',
          'tag2',
          'tag3',
          'm1: metadata']);
  });

  teardown(() => {
    server.restore();
  });
});