// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * Unit tests of cuic-comments custom element
 */
suite('comments', () => {

  let server;

  setup(() => {
    server = sinon.fakeServer.create();
    server.respondImmediately = true;
    stub('cuic-comments', {screenshotSource_ : () => {
        return 'https://example.com/dummy';
      }});
    replace('cuic-single-comment').with('fake-single-comment')
  });

  test('Initial comment fetch', async () => {
    server.respondWith(
        [200, {'Content-Type': 'application/json'},
          '["comment 1", "comment 2", "comment 3"]']);
    const comments = fixture('comments-test-fixture');
    // Queue checking page until it is fully built.
    await zeroTimeout();
    assert.equal(server.requests.length, 1);
    const request = server.requests[0];
    assert(request);
    assert.equal(request.url,
        '/service/23/comments?screenshot_source=' +
        encodeURIComponent('https://example.com/dummy'));
    assert.equal(request.method, 'GET');
    // Note that the single-comment elements don't end up as children of the
    // dom-repeat element
    const commentSet =
        comments.shadowRoot.querySelectorAll('fake-single-comment');
    assert.equal(commentSet.length, 3);
    assert.equal(commentSet[0].comment, 'comment 1');
    assert.equal(commentSet[2].comment, 'comment 3');
    assert.equal(commentSet[1].screenshotkey, 23);
  });

  test('Add comment', async () => {
    server.respondWith(
        [200, {'Content-Type': 'application/json'},
          '["comment 1", "comment 2", "comment 3"]']);
    const comments = fixture('comments-test-fixture');
    // Wait for page to be fully built
    await zeroTimeout();
    server.respondWith([200,
      {'Content-Type': 'application/json'},
      '["comment 1", "comment 2", "comment 3","comment 4", "New Comment"]'])
    comments.$['new-comment-text'].set('value', 'New Comment');
    comments.$['add-comment'].dispatchEvent(new Event('click'));
    await zeroTimeout();
    assert.equal(server.requests.length, 3);
    const putRequest = server.requests[1];
    assert.equal(putRequest.url,
        '/service/23/comments?screenshot_source=' +
        encodeURIComponent('https://example.com/dummy'));
    assert.equal(putRequest.method, 'POST');
    assert.equal(putRequest.requestBody, 'New Comment');
    const getRequest = server.requests[2];
    assert.equal(getRequest.url,
        '/service/23/comments?screenshot_source=' +
        encodeURIComponent('https://example.com/dummy'));
    assert.equal(getRequest.method, 'GET');
    const  commentSet =
        comments.shadowRoot.querySelectorAll('fake-single-comment');
    assert.equal(commentSet.length, 5);
    assert.equal(commentSet[4].comment, 'New Comment');
  });

  test('Comment changed', async () => {
    server.respondWith(
        [200, {'Content-Type': 'application/json'},
          '["comment 1", "comment 2", "comment 3"]']);
    const comments = fixture('comments-test-fixture');
    // Wait for page to be fully built
    await zeroTimeout();
    const  commentSet =
        comments.shadowRoot.querySelectorAll('fake-single-comment');
    commentSet[0].dispatchEvent(new Event('comments-changed'))
    await zeroTimeout();
    assert.equal(server.requests.length, 2);
    const getRequest = server.requests[1];
    assert.equal(getRequest.url,
        '/service/23/comments?screenshot_source=' +
        encodeURIComponent('https://example.com/dummy'));
    assert.equal(getRequest.method, 'GET');
  });

  teardown(() => {
    server.restore();
  });
});