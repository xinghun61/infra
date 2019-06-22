// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {MrAutocomplete} from './mr-autocomplete.js';

let element;

describe('mr-autocomplete', () => {
  beforeEach(() => {
    element = document.createElement('mr-autocomplete');
    document.body.appendChild(element);
  });

  afterEach(() => {
    document.body.removeChild(element);
  });

  it('initializes', () => {
    assert.instanceOf(element, MrAutocomplete);
  });

  it('sets properties based on vocabularies', async () => {
    assert.deepEqual(element.strings, []);
    assert.deepEqual(element.docDict, {});

    element.vocabularies = {
      'project': {
        'strings': ['chromium', 'v8'],
        'docDict': {'chromium': 'move the web forward'},
      },
    };

    element.vocabularyName = 'project';

    await element.updateComplete;

    assert.deepEqual(element.strings, ['chromium', 'v8']);
    assert.deepEqual(element.docDict, {'chromium': 'move the web forward'});
  });
});
