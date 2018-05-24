// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * Unit tests of cuic-single-comment custom element
 */
suite('single_comment', () => {

  let server;
  let single_comment;

  setup(() => {
    server = sinon.fakeServer.create();
    server.respondImmediately = true;
    stub('cuic-single-comment', {screenshotSource_ : () => {
        return 'https://example.com/dummy';
      }});
    single_comment=fixture('single-comment-test-fixture');
  });

  test('Initial state not editable', async () => {
    single_comment.set('comment', {text: 'Text', email: 'email'});
    // Queue checking page until it is fully built.
    await zeroTimeout();
    const shadowRoot = single_comment.shadowRoot;
    assert(!shadowRoot.getElementById('editing').if);
    assert(shadowRoot.getElementById('not-editing').if);
    assert(!shadowRoot.getElementById('editable').if);
  });

  test('Initial state editable', async () => {
    single_comment.set('comment',
        {text: 'Text', email: 'email', editable: true});
    // Queue checking page until it is fully built.
    await zeroTimeout();
    const shadowRoot = single_comment.shadowRoot;
    assert(!shadowRoot.getElementById('editing').if);
    assert(shadowRoot.getElementById('not-editing').if);
    assert(shadowRoot.getElementById('editable').if);
  });

  test('Tap edit button', async () => {
    single_comment.set('comment',
        {text: 'Text', email: 'email', editable: true});
    // Queue checking page until it is fully built.
    await zeroTimeout();
    const shadowRoot = single_comment.shadowRoot;
    const edit_button = shadowRoot.getElementById('edit-button');
    edit_button.dispatchEvent(new Event('click'));
    await zeroTimeout();
    assert(shadowRoot.getElementById('editing').if);
    assert(!shadowRoot.getElementById('not-editing').if);
  });

  test('Save edit', async () => {
    single_comment.set('comment',
        {text: 'Text', email: 'email', editable: true, key:42});
    // Queue checking page until it is fully built.
    await zeroTimeout();
    const shadowRoot = single_comment.shadowRoot;
    const edit_button = shadowRoot.getElementById('edit-button');
    edit_button.dispatchEvent(new Event('click'));
    await zeroTimeout();
    const edit_input = shadowRoot.getElementById('edit-input');
    edit_input.set('value', 'New Text');
    const save_edit = shadowRoot.getElementById('save-edit');
    server.respondWith([200, {}, '']);
    const commentsChanged =
        eventPromise(single_comment, 'comments-changed');
    save_edit.dispatchEvent(new Event('click'));
    await commentsChanged;
    // Check correct message sent
    assert.equal(server.requests.length, 1);
    const request = server.requests[0];
    assert.equal(request.url,
        '/service/23/comment/42?screenshot_source=' +
        encodeURIComponent('https://example.com/dummy'));
    assert.equal(request.method, 'PUT');
    assert.equal(request.requestBody, 'New Text');
    // Check element in correct state
    assert(!shadowRoot.getElementById('editing').if);
    assert(shadowRoot.getElementById('not-editing').if);
    assert(shadowRoot.getElementById('editable').if);
  });

  test('Cancel edit', async () => {
    single_comment.set('comment',
        {text: 'Text', email: 'email', editable: true, key:42});
    // Queue checking page until it is fully built.
    await zeroTimeout();
    const shadowRoot = single_comment.shadowRoot;
    const edit_button = shadowRoot.getElementById('edit-button');
    edit_button.dispatchEvent(new Event('click'));
    await zeroTimeout();
    const edit_input = shadowRoot.getElementById('edit-input');
    edit_input.set('value', 'New Text');
    const cancel_edit = shadowRoot.getElementById('cancel-edit');
    cancel_edit.dispatchEvent(new Event('click'));
    await zeroTimeout();
    // Check nothing sent
    assert.equal(server.requests.length, 0);
    // Check element in correct state
    assert(!shadowRoot.getElementById('editing').if);
    assert(shadowRoot.getElementById('not-editing').if);
    assert(shadowRoot.getElementById('editable').if);
  });

  test('Delete comment', async () => {
    single_comment.set('comment',
        {text: 'Text', email: 'email', editable: true, key:42});
    // Queue checking page until it is fully built.
    await zeroTimeout();
    const shadowRoot = single_comment.shadowRoot;
    const delete_button = shadowRoot.getElementById('delete-button');
    server.respondWith([200, {}, '']);
    const commentsChanged =
        eventPromise(single_comment, 'comments-changed');
    delete_button.dispatchEvent(new Event('click'));
    await commentsChanged;
    // Check delete message sent
    assert.equal(server.requests.length, 1);
    const request = server.requests[0];
    assert.equal(request.url,
        '/service/23/comment/42?screenshot_source=' +
        encodeURIComponent('https://example.com/dummy'));
    assert.equal(request.method, 'DELETE');
  });

  teardown(() => {
    server.restore();
  });
});