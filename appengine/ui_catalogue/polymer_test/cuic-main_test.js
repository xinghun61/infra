// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * Unit tests of cuic-main custom element
 */
suite('main', () => {

  let main;

  setup(() => {
    replace('cuic-summary-view').with('empty-fake');
    replace('cuic-screenshot-view').with('empty-fake');
    replace('cuic-set-screenshot-source').with('empty-fake');
    replace('cuic-view404').with('empty-fake');
    replace('app-route').with('empty-fake');
    main = fixture('main-test-fixture');
  });

  test('No screenshot source', async () => {
    main.routeData = {page: ''};
    main.set('queryParams',{'screenshot_source' : ''});
    await zeroTimeout();
    assert.equal(main.$['pages'].selected, 'cuic-set-screenshot-source');
  });

  test('Default page', async () => {
    main.routeData = {page: ''};
    main.set('queryParams',{'screenshot_source' : 'aaa'});
    await zeroTimeout();
    assert.equal(main.$['pages'].selected, 'cuic-summary-view');
  })

  test('Screenshot view page', async () => {
    main.routeData = {page: 'cuic-screenshot-view'};
    main.set('queryParams',{'screenshot_source' : 'aaa', 'key': 'bbb'});
    await zeroTimeout();
    assert.equal(main.$['pages'].selected, 'cuic-screenshot-view');
    assert.equal(main.$['cuic-screenshot-view'].key, 'bbb');
  })

  test('Bad page', async () => {
    main.routeData = {page: 'Bad'};
    main.set('queryParams',{'screenshot_source' : 'aaa'});
    await zeroTimeout();
    assert.equal(main.$['pages'].selected, 'cuic-view404');
  })

});