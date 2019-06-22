// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import {BatchIterator} from './batch-iterator.js';

suite('BatchIterator');

test('BatchIterator empty', async function() {
  const batches = [];
  for await (const batch of new BatchIterator()) {
    batches.push(batch);
  }
  assert.lengthOf(batches, 0);
});

test('BatchIterator 1 Promise success', async function() {
  let complete;
  const batches = new BatchIterator([new Promise((resolve) => {
    complete = resolve;
  })]);
  const iterations = [];
  const done = (async () => {
    for await (const {results, errors} of batches) {
      iterations.push({results, errors});
    }
  })();
  assert.lengthOf(iterations, 0);
  complete('hello');
  await done;
  assert.lengthOf(iterations, 1);
  assert.lengthOf(iterations[0].errors, 0);
  assert.lengthOf(iterations[0].results, 1);
  assert.strictEqual('hello', iterations[0].results[0]);
});

test('BatchIterator 1 Promise error', async function() {
  let complete;
  const batches = new BatchIterator([new Promise((resolve, reject) => {
    complete = reject;
  })]);
  const iterations = [];
  const done = (async () => {
    for await (const {results, errors} of batches) {
      iterations.push({results, errors});
    }
  })();
  assert.lengthOf(iterations, 0);
  complete('hello');
  await done;
  assert.lengthOf(iterations, 1);
  assert.lengthOf(iterations[0].errors, 1);
  assert.lengthOf(iterations[0].results, 0);
  assert.strictEqual('hello', iterations[0].errors[0]);
});

test('BatchIterator 1 generator-1 success', async function() {
  const batches = new BatchIterator([(async function* () {
    yield 'hello';
  })()]);
  const iterations = [];
  for await (const {results, errors} of batches) {
    iterations.push({results, errors: errors.map((e) => e.message)});
  }
  assert.lengthOf(iterations, 1);
  assert.lengthOf(iterations[0].errors, 0);
  assert.lengthOf(iterations[0].results, 1);
  assert.strictEqual('hello', iterations[0].results[0]);
});

test('BatchIterator 1 generator-1 error', async function() {
  const batches = new BatchIterator([(async function* () {
    throw new Error('hello');
  })()]);
  const iterations = [];
  for await (const {results, errors} of batches) {
    iterations.push({results, errors});
  }
  assert.lengthOf(iterations, 1);
  assert.lengthOf(iterations[0].errors, 1);
  assert.lengthOf(iterations[0].results, 0);
  assert.strictEqual('hello', iterations[0].errors[0].message);
});

test('BatchIterator 1 generator, 2 batches', async function() {
  const resolves = [];
  const promiseA = new Promise((resolve) => resolves.push(resolve));
  const batches = new BatchIterator([(async function* () {
    yield 'a';
    yield 'b';
    await promiseA;
    yield 'c';
  })()]);
  const iterations = [];
  for await (const {results, errors} of batches) {
    iterations.push({results, errors: errors.map((e) => e.message)});
    const resolve = resolves.shift();
    if (resolve) resolve();
  }
  assert.lengthOf(iterations, 2, JSON.stringify(iterations));
  assert.deepEqual([], iterations[0].errors);
  assert.deepEqual(['a', 'b'], iterations[0].results);
  assert.deepEqual([], iterations[1].errors);
  assert.deepEqual(['c'], iterations[1].results);
});

test('BatchIterator 1 generator, 3 batches', async function() {
  const resolves = [];
  const promiseA = new Promise((resolve) => resolves.push(resolve));
  const promiseB = new Promise((resolve) => resolves.push(resolve));
  const batches = new BatchIterator([(async function* () {
    yield 'a';
    await promiseA;
    yield 'b';
    await promiseB;
    yield 'c';
  })()]);
  const iterations = [];
  for await (const {results, errors} of batches) {
    iterations.push({results, errors: errors.map((e) => e.message)});
    const resolve = resolves.shift();
    if (resolve) resolve();
  }
  assert.lengthOf(iterations, 3, JSON.stringify(iterations));
  assert.deepEqual([], iterations[0].errors);
  assert.deepEqual(['a'], iterations[0].results);
  assert.deepEqual([], iterations[1].errors);
  assert.deepEqual(['b'], iterations[1].results);
  assert.deepEqual([], iterations[2].errors);
  assert.deepEqual(['c'], iterations[2].results);
});

test('BatchIterator 3 generators, 3 batches', async function() {
  const resolves = [];
  const promiseA = new Promise((resolve) => resolves.push(resolve));
  const promiseB = new Promise((resolve) => resolves.push(resolve));
  const batches = new BatchIterator([
    (async function* () {
      yield 'a0';
      await promiseA;
      yield 'a1';
    })(),
    (async function* () {
      yield 'b0';
      await promiseA;
      yield 'b1';
      throw new Error('bbb');
    })(),
    (async function* () {
      await promiseA;
      yield 'c0';
      await promiseB;
      yield 'c1';
    })(),
  ]);
  const iterations = [];
  for await (const {results, errors} of batches) {
    iterations.push({results, errors: errors.map((e) => e.message)});
    const resolve = resolves.shift();
    if (resolve) resolve();
  }
  assert.lengthOf(iterations, 3, JSON.stringify(iterations));
  assert.deepEqual([], iterations[0].errors);
  assert.deepEqual(['a0', 'b0'], iterations[0].results);
  assert.deepEqual(['c0', 'a1', 'b1'], iterations[1].results);
  assert.deepEqual(['bbb'], iterations[1].errors);
  assert.deepEqual([], iterations[2].errors);
  assert.deepEqual(['c1'], iterations[2].results);
});
