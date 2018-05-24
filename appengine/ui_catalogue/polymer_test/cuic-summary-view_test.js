// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * Unit tests of cuic-summary-view custom element
 */
suite('summary_view', () => {

  class FakeShotSelector extends Polymer.Element {

    static get is() {
      return 'fake-cuic-shot-selector';
    };

    static get properties() {
      return {
        selection: {
          type: Object,
          notify: true
        }
      };
    }
  }

  window.customElements.define(FakeShotSelector.is, FakeShotSelector);

  let summaryView;
  const selection = {'x': ['y', 'z'], 'a':'b', 'c':'d'};

  setup(() => {
    replace('cuic-screenshot-strip').with('fake-cuic-screenshot-strip');
    replace('cuic-shot-selector').with('fake-cuic-shot-selector');
    replace('iron-query-params').with('fake-iron-query-params');
    summaryView = fixture('summary-view-test-fixture');
    summaryView.set('queryParams_',
        {
          junk: 'xxxx',
          selection: JSON.stringify(selection)
        }
    );
  });

  test('Initial state', async () => {
    await zeroTimeout();
    assert.deepEqual(summaryView.$['shot-selector'].selection, selection);
    assert.deepEqual(summaryView.$['screenshot-strip'].selection, selection);
  });

  test('Selection change', async () => {
    await zeroTimeout();
    const selection2 = {'d1' : ['d2', 'd3']};
    summaryView.$['shot-selector'].set('selection', selection2);
    await zeroTimeout();
    assert.deepEqual(summaryView.$['screenshot-strip'].selection, selection2);
    assert.equal(summaryView.queryParams_.selection,
        JSON.stringify(selection2));
  });
});