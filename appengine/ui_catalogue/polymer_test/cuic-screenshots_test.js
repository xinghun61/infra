// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * Unit tests of cuic-screenshot-set custom element
 */
suite('screenshot_set', () => {

  let screenshotSet;
  let server;

  setup(() => {
    server = sinon.fakeServer.create();
    server.respondImmediately = true;

    // Stub the ElementBaseWithUrls methods that this uses.
    stub('cuic-screenshots', {
      screenshotSource_: () => {
        return 'http://exmaple.com/screenshots';
      },
      screenshotLocationParam_ : () => {
        return {location: 'xxx'};
      }
    });
    screenshotSet = fixture('screenshot-set-test-fixture');
  });

  test('Screenshot set', (done) => {
    server.respondWith(
        [200, {'Content-Type': 'application/json'}, '{"xxx":"yyy"}']);
    screenshotSet.addEventListener('screenshots-received', (e) => {
      assert.deepEqual(e.detail, {xxx: 'yyy'})
      done();
    })
    const selector = {filters: {aaa: 'bbb'}, userTags:['ccc', 'ddd']};
    screenshotSet.requestScreenshotsForSelector(selector);
    assert.equal(server.requests.length, 1);
    const request = server.requests[0];
    // For a GET iron-request leaves the method undefined.
    assert.equal(request.method, 'GET');
    let path, query;
    [path, query] = request.url.split('?');
    assert.equal(path, '/service/screenshot_list');
    assert.equal(decodeURIComponent(query),
        'filters={"aaa":"bbb"}&userTags=ccc&userTags=ddd&location=xxx');
  });

  teardown(() => {
    server.restore();
  });
});