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

  it('_setupProjectVocabulary', () => {
    assert.deepEqual(element._setupProjectVocabulary({}), {strings: []});

    assert.deepEqual(element._setupProjectVocabulary({
      ownerOf: ['chromium'],
      memberOf: ['skia'],
      contributorTo: ['v8'],
    }), {strings: ['chromium', 'skia', 'v8']});
  });

  it('_setupMemberVocabulary', () => {
    assert.deepEqual(element._setupMemberVocabulary({}), {strings: []});

    assert.deepEqual(element._setupMemberVocabulary({
      userRefs: [
        {displayName: 'group@example.com', userId: '100'},
        {displayName: 'test@example.com', userId: '123'},
        {displayName: 'test2@example.com', userId: '543'},
      ],
      groupRefs: [
        {displayName: 'group@example.com', userId: '100'},
      ],
    }), {strings:
      ['group@example.com', 'test@example.com', 'test2@example.com'],
    });
  });

  it('_setupOwnerVocabulary', () => {
    assert.deepEqual(element._setupOwnerVocabulary({}), {strings: []});

    assert.deepEqual(element._setupOwnerVocabulary({
      userRefs: [
        {displayName: 'group@example.com', userId: '100'},
        {displayName: 'test@example.com', userId: '123'},
        {displayName: 'test2@example.com', userId: '543'},
      ],
      groupRefs: [
        {displayName: 'group@example.com', userId: '100'},
      ],
    }), {strings:
      ['test@example.com', 'test2@example.com'],
    });
  });
});
