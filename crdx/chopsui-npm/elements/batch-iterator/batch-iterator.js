// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Wraps requestAnimationFrame() in a Promise to allow callers to await it in
// async functions.
export function animationFrame() {
  return new Promise((resolve) => requestAnimationFrame(resolve));
}

// Wraps setTimeout() in a Promise to allow callers to await it in async
// functions.
export function timeout(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function* asGenerator(promise) {
  yield await promise;
}

/**
  * BatchIterator reduces processing costs by batching results and errors
  * from an array of tasks. A task can either be a promise or an asynchronous
  * iterator. In other words, use this class when it is costly to iteratively
  * process the output of each task (e.g. when rendering to DOM).
  *
  * const tasks = urls.map(fetch);
  * for await (const {results, errors} of new BatchIterator(tasks)) {
  *   render(results, errors);
  * }
  *
  * Callers may await animationFrame() in their for-await loops to allow
  * BatchIterator to measure how long it takes to render the results so it can
  * batch results for that long for the next batch. Callers may instead pass a
  * getDelay callback for more explicit control of the batching schedule.
  */
export class BatchIterator {
  constructor(tasks = [], getDelay = timeout) {
    // `tasks` may include either simple Promises or async generators.
    this._results = [];
    this._errors = [];
    this._promises = new Set();

    for (const task of tasks) this.add(task);

    this._getDelay = (ms) => {
      const promise = getDelay(ms).then(() => {
        promise.resolved = true;
      });
      return promise;
    };
  }

  add(task) {
    if (task instanceof Promise) task = asGenerator(task);
    if (!task.next && task[Symbol.asyncIterator]) {
      // It's probably an instance of a class that implements this method like
      // ReportFetcher.
      task = task[Symbol.asyncIterator]();
    }
    this._generate(task);
  }

  // Adds a Promise to this._promises that resolves when the generator next
  // resolves, and deletes itself from this._promises.
  // If the generator is not done, the result is pushed to this._results or
  // the error is pushed to this._errors, and another Promise is added to
  // this._promises.
  _generate(generator) {
    const wrapped = (async () => {
      try {
        const {value, done} = await generator.next();
        if (done) return;
        this._results.push(value);
        this._generate(generator);
      } catch (error) {
        this._errors.push(error);
      } finally {
        this._promises.delete(wrapped);
      }
    })();
    this._promises.add(wrapped);
  }

  _batch() {
    const batch = {results: this._results, errors: this._errors};
    this._results = [];
    this._errors = [];
    return batch;
  }

  [Symbol.asyncIterator]() {
    return (async function* () {
      if (!this._promises.size) return;

      // Yield the first result immediately in order to allow the user to start
      // to understand it (c.f. First Contentful Paint), and also to measure how
      // long it takes the caller to render the data. Use that measurement as an
      // estimation of how long to wait before yielding the next batch of
      // results. This first batch may contain multiple results/errors if
      // multiple tasks resolve in the same tick, or if a generator yields
      // multiple results synchronously.
      await Promise.race(this._promises);
      let start = performance.now();
      yield this._batch();
      let processingMs = performance.now() - start;

      while (this._promises.size ||
              this._results.length || this._errors.length) {
        // Wait for a result or error to become available.
        // This may not be necessary if a promise resolved while the caller was
        // processing previous results.
        if (!this._results.length && !this._errors.length) {
          await Promise.race(this._promises);
        }

        // Wait for either the delay to resolve or all generators to be done.
        // This can't use Promise.all() because generators can add new promises.
        const delay = this._getDelay(processingMs);
        while (!delay.resolved && this._promises.size) {
          await Promise.race([delay, ...this._promises]);
        }

        start = performance.now();
        yield this._batch();
        processingMs = performance.now() - start;
      }
    }).call(this);
  }
}
