// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {arrayDifference, hasPrefix, objectToMap, equalsIgnoreCase,
  immutableSplice, userIsMember} from './helpers.js';


describe('arrayDifference', () => {
  it('empty array stays empty', () => {
    assert.deepEqual(arrayDifference([], []), []);
    assert.deepEqual(arrayDifference([], undefined), []);
    assert.deepEqual(arrayDifference([], ['a']), []);
  });

  it('subtracting empty array does nothing', () => {
    assert.deepEqual(arrayDifference(['a'], []), ['a']);
    assert.deepEqual(arrayDifference([1, 2, 3], []), [1, 2, 3]);
    assert.deepEqual(arrayDifference([1, 2, 'test'], []), [1, 2, 'test']);
    assert.deepEqual(arrayDifference([1, 2, 'test'], undefined),
        [1, 2, 'test']);
  });

  it('subtracts elements from array', () => {
    assert.deepEqual(arrayDifference(['a', 'b', 'c'], ['b', 'c']), ['a']);
    assert.deepEqual(arrayDifference(['a', 'b', 'c'], ['a']), ['b', 'c']);
    assert.deepEqual(arrayDifference(['a', 'b', 'c'], ['b']), ['a', 'c']);
    assert.deepEqual(arrayDifference([1, 2, 3], [2]), [1, 3]);
  });

  it('does not subtract missing elements from array', () => {
    assert.deepEqual(arrayDifference(['a', 'b', 'c'], ['d']), ['a', 'b', 'c']);
    assert.deepEqual(arrayDifference([1, 2, 3], [5]), [1, 2, 3]);
    assert.deepEqual(arrayDifference([1, 2, 3], [-1, 2]), [1, 3]);
  });

  it('custom equals function', () => {
    assert.deepEqual(arrayDifference(['a', 'b'], ['A']), ['a', 'b']);
    assert.deepEqual(arrayDifference(['a', 'b'], ['A'], equalsIgnoreCase),
        ['b']);
  });
});

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

describe('equalsIgnoreCase', () => {
  it('matches same case strings', () => {
    assert.isTrue(equalsIgnoreCase('', ''));
    assert.isTrue(equalsIgnoreCase('HelloWorld', 'HelloWorld'));
    assert.isTrue(equalsIgnoreCase('hmm', 'hmm'));
    assert.isTrue(equalsIgnoreCase('TEST', 'TEST'));
  });

  it('matches different case strings', () => {
    assert.isTrue(equalsIgnoreCase('a', 'A'));
    assert.isTrue(equalsIgnoreCase('HelloWorld', 'helloworld'));
    assert.isTrue(equalsIgnoreCase('hmm', 'HMM'));
    assert.isTrue(equalsIgnoreCase('TEST', 'teSt'));
  });

  it('does not match different strings', () => {
    assert.isFalse(equalsIgnoreCase('hello', 'hello '));
    assert.isFalse(equalsIgnoreCase('superstring', 'string'));
    assert.isFalse(equalsIgnoreCase('aaa', 'aa'));
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
