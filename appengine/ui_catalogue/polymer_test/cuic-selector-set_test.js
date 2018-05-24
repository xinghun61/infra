// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * Unit tests of cuic-screenshot-view custom element
 */
suite('tag_set', () => {

  let tagSet;
  let server;

  setup(() => {
    server = sinon.fakeServer.create();
    server.respondImmediately = true;
  });

  test('Server response sets tagSet', async () => {
    server.respondWith(
        [200, {'Content-Type': 'application/json'}, '{"xxx":"yyy"}']);
    const tagSet = fixture('tag-set-test-fixture');
    await eventPromise(tagSet, 'tag-change');
    assert(tagSet.taglist);
    assert(tagSet.taglist.xxx);
    assert.equal(tagSet.taglist.xxx, 'yyy');
    assert(server.requests.length, 1);
    const request = server.requests[0];
    // For a GET iron-request leaves the method undefined.
    assert.equal(request.method, 'GET');
    const path = request.url.split('?')[0];
    assert.equal(path, '/service/selector_list');
  });

  teardown(() => {
    server.restore();
  });
});