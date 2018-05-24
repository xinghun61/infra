// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * Unit tests of cuic-selector-set custom element
 */

suite('selector', () => {

  const WIDE_DOC_WIDTH = 10000;
  const NARROW_DOC_WIDTH = 50;
  let selector;

  setup(() => {
    replace('cuic-selector-set').with('fake-cuic-selector-set');
    selector = fixture('selector-test-fixture');
    selector.$['tag-set'].taglist = {
      'filters' : {
        'Filter 2' : ['v1', 'v2'],
        'Filter 1' : ['v 3']
      },
      'userTags' : ['t1', 't3', 't2']
    };
    selector.$['tag-set'].dispatchEvent(new CustomEvent('tag-change'));
  });

  function getSelection_(menu) {
    return menu.querySelector('paper-listbox').selected
  }

  function getMenuItems_(menu) {
    return Array.from(menu.querySelectorAll('paper-item')).map(i =>
        i.textContent);
  }

  test('Default selection', async () => {
    await zeroTimeout();
    const dropdownMenus =
        selector.$['filter-toolbar'].querySelectorAll('paper-dropdown-menu');
    const menuArray = Array.from(dropdownMenus);
    // Check the titles, including checking they have been sorted
    assert.deepEqual(menuArray.map(m => m.label), ['Filter 1', 'Filter 2']);
    assert.deepEqual(menuArray.map(m => getSelection_(m)), [0, 0]);
    assert.deepEqual(menuArray.map(m => getMenuItems_(m)),
        [['Any', 'v 3'], ['Any', 'v1', 'v2']]);
    assert.equal(selector.$['selected-tags'].items.length, 0);
    assert(selector.$['unselected-tags'].if);
    const addTagMenu =
        selector.$['tags-list'].querySelector('paper-dropdown-menu');
    assert.deepEqual(getMenuItems_(addTagMenu), ['t1', 't2', 't3']);
  });

  test('Non Default selection', async () => {
    selector.set('selection', {
      'filters': {'Filter 2' : 'v2'},
      'userTags' : ['t3']
    });
    await zeroTimeout();
    const dropdownMenus =
        selector.$['filter-toolbar'].querySelectorAll('paper-dropdown-menu');
    const menuArray = Array.from(dropdownMenus);
    // Check the titles, including checking they have been sorted
    assert.deepEqual(menuArray.map(m => m.label), ['Filter 1', 'Filter 2']);
    assert.deepEqual(menuArray.map(m => getSelection_(m)), [0, 2]);
    assert.deepEqual(menuArray.map(m => getMenuItems_(m)),
        [['Any', 'v 3'], ['Any', 'v1', 'v2']]);
    assert.equal(selector.$['selected-tags'].items.length, 1);
    assert(selector.$['unselected-tags'].if);
    const addTagMenu =
        selector.$['tags-list'].querySelector('paper-dropdown-menu');
    assert.deepEqual(getMenuItems_(addTagMenu), ['t1', 't2']);
  });

  test("Select item from menu", async () => {
    await zeroTimeout();
    const dropdownMenus =
        selector.$['filter-toolbar'].querySelectorAll('paper-dropdown-menu');
    dropdownMenus[1].querySelector('paper-listbox').set('selected', 2);
    await zeroTimeout();
    assert.equal(selector.selection.filters['Filter 2'], 'v2');
  });

  test("Add required tag", async () => {
    await zeroTimeout();
    const addTagMenu =
        selector.$['tags-list'].querySelector('paper-dropdown-menu');
    selector.set('userTagMenuFocused_', true);
    addTagMenu.querySelector('paper-listbox').set('selected', 2);
    await zeroTimeout();
    assert.deepEqual(selector.selection.userTags, ['t3']);
  });

  test("Remove tag", async () => {
    selector.set('selection', {
      'filters': {'Filter 2' : 'v2'},
      'userTags' : ['t3']
    });
    await zeroTimeout();
    requiredTag = selector.shadowRoot.querySelector('.requiredTag');
    removeButton = requiredTag.querySelector('paper-button');
    removeButton.dispatchEvent(new Event('tap'));
    await zeroTimeout();
    assert.deepEqual(selector.selection.userTags, []);
    assert.equal(selector.$['selected-tags'].items.length, 0);
    const addTagMenu =
        selector.$['tags-list'].querySelector('paper-dropdown-menu');
    assert.deepEqual(getMenuItems_(addTagMenu), ['t1', 't2', 't3']);
  });

  test("All tags", async () => {
    selector.set('selection', {
      'filters': {},
      'userTags' : ['t1', 't2', 't3']
    });
    await zeroTimeout();
    // Add tag menu should be hidden
    assert(!selector.$['unselected-tags'].if);
  });

  // Test buttons for scrolling tags sideways
  test('Wide page', async () => {
    stub('cuic-shot-selector', {
      documentWidth_ : () => {
        return WIDE_DOC_WIDTH; }
    })
    selector.set('selection', {
      'filters': {'Filter 2' : 'v2'},
      'userTags' : ['t3']
    });
    await zeroTimeout();
    assert(!selector.$['left-button-if'].if);
    assert(!selector.$['right-button-if'].if);
  });

  suite('Narrow page tests', () => {

    setup(() => {
      stub('cuic-shot-selector', {
        documentWidth_: () => {
          return NARROW_DOC_WIDTH;
        }
      });
      selector.dispatchEvent(new Event('resize'));
      selector.set('selection', {
        'filters': {'Filter 2': 'v2'},
        'userTags': ['t3']
      });

    });

    test('Narrow page', async () => {
      await zeroTimeout();
      assert(!selector.$['left-button-if'].if);
      assert(selector.$['right-button-if'].if);
      const leftPos = selector.$['tags-list'].getBoundingClientRect().left;
      assert.equal(leftPos, 0);
    });

    test('Scroll right', async () => {
      await domChanged(selector.$['right-button-if']);
      const rightButton = selector.shadowRoot.querySelector('#right-button');
      rightButton.dispatchEvent(new Event('tap'));
      await domChanged(selector.$['left-button-if']);
      assert(selector.$['left-button-if'].if);
      const leftPos = selector.$['tags-list'].getBoundingClientRect().left;
      assert.isBelow(leftPos, 0);
    });

    test('Full scroll right', async () => {
      let count = 0;
      await domChanged(selector.$['right-button-if']);
      while (selector.$['right-button-if'].if) {
        assert.isBelow(count, 10);
        count++;
        const rightButton = selector.shadowRoot.querySelector(
            '#right-button');
        rightButton.dispatchEvent(new Event('tap'));
        await zeroTimeout();
      }
      const rightPos = selector.$['tags-list'].getBoundingClientRect().right;
      assert.isBelow(rightPos, NARROW_DOC_WIDTH);
    });

    test('Scroll right then left', async () => {
      await domChanged(selector.$['right-button-if']);
      const rightButton = selector.shadowRoot.querySelector('#right-button');
      rightButton.dispatchEvent(new Event('tap'));
      await domChanged(selector.$['left-button-if']);
      const leftButton = selector.shadowRoot.querySelector('#left-button');
      leftButton.dispatchEvent(new Event('tap'));
      await domChanged(selector.$['left-button-if']);
      assert(!selector.$['left-button-if'].if);
      const leftPos = selector.$['tags-list'].getBoundingClientRect().left;
      assert.equal(leftPos, 0);
    });
  });
});