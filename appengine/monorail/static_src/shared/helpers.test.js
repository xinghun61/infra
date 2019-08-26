// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {hasPrefix, objectToMap, immutableSplice,
  userIsMember} from './helpers.js';

describe('hasPrefix', () => {
  it('only true when has prefix', () => {
    assert.isFalse(hasPrefix('teststring', 'test-'));
    assert.isFalse(hasPrefix('stringtest-', 'test-'));
    assert.isFalse(hasPrefix('^test-$', 'test-'));
    assert.isTrue(hasPrefix('test-', 'test-'));
    assert.isTrue(hasPrefix('test-fsdfsdf', 'test-'));
  });

  it('ignores case when checking prefix', () => {
    assert.isTrue(hasPrefix('TEST-string', 'test-'));
    assert.isTrue(hasPrefix('test-string', 'test-'));
    assert.isTrue(hasPrefix('tEsT-string', 'test-'));
  });
});

describe('objectToMap', () => {
  it('converts Object to Map with the same keys', () => {
    assert.deepEqual(objectToMap({}), new Map());
    assert.deepEqual(objectToMap({test: 'value'}),
        new Map([['test', 'value']]));
    assert.deepEqual(objectToMap({['weird:key']: 'value',
      ['what is this key']: 'v2'}), new Map([['weird:key', 'value'],
      ['what is this key', 'v2']]));
  });
});

describe('immutableSplice', () => {
  it('does not edit original array', () => {
    const arr = ['apples', 'pears', 'oranges'];

    assert.deepEqual(immutableSplice(arr, 1, 1),
        ['apples', 'oranges']);

    assert.deepEqual(arr, ['apples', 'pears', 'oranges']);
  });

  it('removes multiple items', () => {
    const arr = [1, 2, 3, 4, 5, 6];

    assert.deepEqual(immutableSplice(arr, 1, 0), [1, 2, 3, 4, 5, 6]);
    assert.deepEqual(immutableSplice(arr, 1, 4), [1, 6]);
    assert.deepEqual(immutableSplice(arr, 0, 6), []);
  });

  it('adds items', () => {
    const arr = [1, 2, 3];

    assert.deepEqual(immutableSplice(arr, 1, 1, 4, 5, 6), [1, 4, 5, 6, 3]);
    assert.deepEqual(immutableSplice(arr, 2, 1, 4, 5, 6), [1, 2, 4, 5, 6]);
    assert.deepEqual(immutableSplice(arr, 0, 0, -3, -2, -1, 0),
        [-3, -2, -1, 0, 1, 2, 3]);
  });
});


describe('userIsMember', () => {
  it('false when no user', () => {
    assert.isFalse(userIsMember(undefined));
    assert.isFalse(userIsMember({}));
    assert.isFalse(userIsMember({}, 'chromium',
        new Map([['123', {ownerOf: ['chromium']}]])));
  });

  it('true when user is member of project', () => {
    assert.isTrue(userIsMember({userId: '123'}, 'chromium',
        new Map([['123', {contributorTo: ['chromium']}]])));

    assert.isTrue(userIsMember({userId: '123'}, 'chromium',
        new Map([['123', {ownerOf: ['chromium']}]])));

    assert.isTrue(userIsMember({userId: '123'}, 'chromium',
        new Map([['123', {memberOf: ['chromium']}]])));
  });

  it('true when user is member of multiple projects', () => {
    assert.isTrue(userIsMember({userId: '123'}, 'chromium', new Map([
      ['123', {contributorTo: ['test', 'chromium', 'fakeproject']}],
    ])));

    assert.isTrue(userIsMember({userId: '123'}, 'chromium', new Map([
      ['123', {ownerOf: ['test', 'chromium', 'fakeproject']}],
    ])));

    assert.isTrue(userIsMember({userId: '123'}, 'chromium', new Map([
      ['123', {memberOf: ['test', 'chromium', 'fakeproject']}],
    ])));
  });

  it('false when user is member of different project', () => {
    assert.isFalse(userIsMember({userId: '123'}, 'chromium', new Map([
      ['123', {contributorTo: ['test', 'fakeproject']}],
    ])));

    assert.isFalse(userIsMember({userId: '123'}, 'chromium', new Map([
      ['123', {ownerOf: ['test', 'fakeproject']}],
    ])));

    assert.isFalse(userIsMember({userId: '123'}, 'chromium', new Map([
      ['123', {memberOf: ['test', 'fakeproject']}],
    ])));
  });

  it('false when no project data for user', () => {
    assert.isFalse(userIsMember({userId: '123'}, 'chromium'));
    assert.isFalse(userIsMember({userId: '123'}, 'chromium', new Map()));
    assert.isFalse(userIsMember({userId: '123'}, 'chromium', new Map([
      ['543', {ownerOf: ['chromium']}],
    ])));
  });
});
