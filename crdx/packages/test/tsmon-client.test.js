// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {assert} from 'chai';
import sinon from 'sinon';
import '@chopsui/tsmon-client';

const TSMonClient = window.chops.tsmon.TSMonClient;
const ValueType = window.chops.tsmon.ValueType;
const FieldType = window.chops.tsmon.FieldType;

let tsm;

setup(() => {
  tsm = new TSMonClient();
  tsm._name = 'testname';
  tsm._jobName = 'testJobName';
  sinon.stub(window, 'fetch');
  let res = new window.Response('Ok.', {
    status: 200,
    headers: {
      'Content-type': 'application/json',
    },
  });
  window.fetch.returns(Promise.resolve(res));
});

teardown(() => {
  window.fetch.restore();
});

function assertLowerBounds(b, expected) {
  const expectedTotal = expected.length;

  assert.equal(expectedTotal - 2, b.numFiniteBuckets);
  assert.equal(expectedTotal, b.totalBuckets);
  assert.equal(0, b.underflowBucket);
  assert.equal(expectedTotal - 1, b.overflowBucket);
  assert.deepEqual(expected, b._lowerBounds);

  expected.forEach((lowerBound, i) => {
    if (i > expected.length - 2) {
      return;
    }
    const upperBound = expected[i + 1];

    assert.isTrue(lowerBound < upperBound);
    assert.deepEqual([lowerBound, upperBound], b.bucketBoundaries(i));
    assert.equal(i, b.bucketForValue(lowerBound));
    assert.equal(i, b.bucketForValue(lowerBound + 0.5));
    assert.equal(i, b.bucketForValue(upperBound - 0.5));

    assert.throws(() => {
      b.bucketBoundaries(-1);
    });
    assert.throws(() => {
      b.bucketBoundaries(expected.length);
    });
  });
}

function assertMapEqual(a ,b) {
  assert.equal(a.size, b.size, 'map sizes');
  for (const [k, v] of a) {
    assert.isTrue(b.has(k), 'other map has key ' + k);
    if (v instanceof Map) {
      assertMapEqual(v, b.get(k));
    } else {
      assert.equal(v, b.get(k), 'value for key ' + k);
    }
  }
}

suite('fixed width bucketer', () => {
  test('equaltiy', () => {
    const b = TSMonClient.fixedWidthBucketer(10, 8);
    assert.equal(b, b)
  });

  test('negative size', () => {
    assert.throws(() => {
      TSMonClient.fixedWidthBucketer(10, -1);
    }, Error);
  });

  test('negative width', () => {
    assert.throws(() => {
      TSMonClient.fixedWidthBucketer(-1, 1);
    }, Error);
  });

  test('zero size', () => {
    const b = TSMonClient.fixedWidthBucketer(10, 0);
    assertLowerBounds(b, [-Infinity, 0]);
  });

  test('one size', () => {
    const b = TSMonClient.fixedWidthBucketer(10, 1);
    assertLowerBounds(b, [-Infinity, 0, 10]);
  });

  test('bucket for value', () => {
    const b = TSMonClient.fixedWidthBucketer(10, 5);
    assert.equal(0, b.bucketForValue(-Infinity));
    assert.equal(0, b.bucketForValue(-100));
    assert.equal(0, b.bucketForValue(-1));
    assert.equal(1, b.bucketForValue(0));
    assert.equal(5, b.bucketForValue(45));
    assert.equal(6, b.bucketForValue(51));
    assert.equal(6, b.bucketForValue(100000));
    assert.equal(6, b.bucketForValue(Infinity));
  });
});

suite('geometric bucketer', () => {
  test('equaltiy', () => {
    const b = TSMonClient.geometricBucketer(4, 4, 0.1);
    assert.equal(b, b);
  });

  test('negative size', () => {
    assert.throws(() => {
      TSMonClient.geometricBucketer(0, -1);
    }, Error);
  });

  test('bad growth factors', () => {
    assert.throws(() => {
      TSMonClient.geometricBucketer(-1);
    }, Error);
    assert.throws(() => {
      TSMonClient.geometricBucketer(1);
    }, Error);
  });

  test('zero size', () => {
    const b = TSMonClient.geometricBucketer(0, 0);
    assertLowerBounds(b, [-Infinity, 1]);
  });

  test('large size', () => {
    const b = TSMonClient.geometricBucketer(4, 4);
    assertLowerBounds(b, [-Infinity, 1, 4, 16, 64, 256]);
  });

  test('scale', () => {
    const b = TSMonClient.geometricBucketer(4, 4, 0.1);
    assert.equal(0, b.bucketForValue(-Infinity));
    assert.equal(0, b.bucketForValue(0.05));
    assert.equal(1, b.bucketForValue(0.2));
    assert.equal(5, b.bucketForValue(Infinity));
  });

  test('bucket for value', () => {
    const b = TSMonClient.geometricBucketer(2, 5);
    assert.equal(0, b.bucketForValue(-Infinity));
    assert.equal(0, b.bucketForValue(-100));
    assert.equal(0, b.bucketForValue(-1));
    assert.equal(0, b.bucketForValue(0));
    assert.equal(1, b.bucketForValue(1));
    assert.equal(5, b.bucketForValue(31));
    assert.equal(6, b.bucketForValue(32));
    assert.equal(6, b.bucketForValue(100000));
    assert.equal(6, b.bucketForValue(Infinity));

  });
});

suite('distribution', () => {
  test('add', () => {
    const d = new chops.tsmon.Distribution(TSMonClient.geometricBucketer());
    assert.equal(0, d.sum);
    assert.equal(0, d.count);
    assert.deepEqual(new Map(), d.buckets);

    d.add(1);
    d.add(10);
    d.add(100);

    assert.equal(111, d.sum);
    assert.equal(3, d.count);
    assertMapEqual(new Map([[1, 1], [5, 1], [10, 1]]), d.buckets);

    d.add(50);

    assert.equal(161, d.sum);
    assert.equal(4, d.count);
    assert.deepEqual(new Map([[1, 1], [5, 1], [9, 1], [10, 1]]), d.buckets);
  });

  test('add on bucket boundary', () => {
    const d = new chops.tsmon.Distribution(TSMonClient.fixedWidthBucketer(10));
    d.add(10);

    assert.equal(10, d.sum);
    assert.equal(1, d.count);
    assert.deepEqual(new Map([[1, 1], [2, 1]]), d.buckets);
  });

  test('underflow bucket', () => {
    const d = new chops.tsmon.Distribution(TSMonClient.fixedWidthBucketer(10));
    d.add(-1);

    assert.equal(-1, d.sum);
    assert.equal(1, d.count);
    assert.deepEqual(new Map([[0, 1]]), d.buckets);

    d.add(-1000000);
    assert.equal(-1000001, d.sum);
    assert.equal(2, d.count);
    assert.deepEqual(new Map([[0, 2]]), d.buckets);
  });

  test('overflow bucket', () => {
    const d = new chops.tsmon.Distribution(TSMonClient.fixedWidthBucketer(10, 10));
    d.add(100);

    assert.equal(100, d.sum);
    assert.equal(1, d.count);
    assert.deepEqual(new Map([[11, 1]]), d.buckets);

    d.add(1000000);
    assert.equal(1000100, d.sum);
    assert.equal(2, d.count);
    assert.deepEqual(new Map([[11, 2]]), d.buckets);
  });
});

suite('flush', () => {
 test('disableAfterNextFlush stops sending metrics', () => {
   assert.isTrue(tsm._continueSendingMetrics);
   assert.isOk(tsm._flushTimer);

    tsm.disableAfterNextFlush();
    tsm._onFlush();

    assert.isFalse(tsm._continueSendingMetrics);
    assert.isNull(tsm._flushTimer);
    assert.isTrue(window.fetch.called);
  });

  test('cumulative distribution', () => {
    let fields = new Map(Object.entries({
      "foo_field": TSMonClient.stringField('foo_field'),
    }));
    let c = tsm.cumulativeDistribution('frontend/cumulativedistribution_test',
        'cumulative distribution test', undefined, fields);
    let ts = 1;
    tsm.now = () => { return ts; }

    fields = new Map(Object.entries({"foo_field": "bar_value"}));
    c.add(1, fields);
    tsm.flush();

    // First call immediately flushes.
    sinon.assert.calledWith(window.fetch,
      sinon.match(tsm._reportPath), sinon.match({
        method: 'POST',
        credentials: 'same-origin',
        body: JSON.stringify({
          "metrics":[{
            "MetricInfo": {
              "Name": c.info.Name,
              "Desription": c.info.Description,
              "Fields": {
                "foo_field": {
                  "Name": "foo_field",
                  "Type": FieldType.STRING,
                }
              },
              "ValueType": c.info.ValueType,
            },
            "Cells": [{
              "value": {
                "sum": 1,
                "count": 1,
                "buckets": [[1,1]],
              },
              "fields": {
                "foo_field": "bar_value"
              },
              "start_time": tsm._initTimeSeconds,
            }]
          }],
          "token": null,
        }),
      }
    ));

    ts = 2;
    const firstTimestamp = ts;
    c.add(2, fields);
    c.add(2, fields);
    ts = 3;
    c.add(5, fields);
    c.add(5, fields);
    c.add(5, fields);
    c.add(10, fields);

    tsm.flush();
    sinon.assert.calledWith(window.fetch,
      sinon.match(tsm._reportPath), sinon.match({
        method: 'POST',
        credentials: 'same-origin',
        body: JSON.stringify({
          "metrics":[{
            "MetricInfo": {
              "Name": c.info.Name,
              "Desription": c.info.Description,
              "Fields": {
                "foo_field": {
                  "Name": "foo_field",
                  "Type": FieldType.STRING,
                }
              },
              "ValueType": c.info.ValueType,
            },
            "Cells": [{
              "value": {
                "sum": 29,
                "count": 6,
                "buckets": [[2, 2], [4, 3], [5, 1]]
              },
              "fields": {
                "foo_field": "bar_value"
              },
              "start_time": tsm._initTimeSeconds,
            }]
          }],
          "token": null,
        }),
      }
    ));
  });
});
