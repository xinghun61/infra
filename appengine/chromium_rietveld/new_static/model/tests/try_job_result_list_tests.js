// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

"use strict";

describe("TryJobResultList", function() {
    var assert = chai.assert;

    function createData() {
        return [
            {
                parent_name: null,
                tests: [ ],
                slave: null,
                timestamp: "2014-06-18 08:13:29.036400",
                builder: "builder_a",
                build_properties: '{"summary": "first"}'
            },
            {
                parent_name: null,
                tests: [ ],
                slave: null,
                timestamp: "2014-06-18 18:00:29.036400",
                builder: "builder_a",
                build_properties: '{"summary": "third"}'
            },
            {
                parent_name: null,
                tests: [ ],
                slave: null,
                timestamp: "2014-06-18 08:30:29.036400",
                builder: "builder_a",
                build_properties: '{"summary": "second"}'
            },
            {
                parent_name: null,
                tests: [ ],
                slave: null,
                timestamp: "2014-06-18 08:13:29.036400",
                builder: "builder_b",
                build_properties: '{"summary": "different builder"}'
            },
        ];
    }

    it("should parse and sort basic data", function() {
        var tryResultList = new TryJobResultList();
        var data = createData();
        tryResultList.parseData(data);
        var set_a = tryResultList.results[0];
        var set_b = tryResultList.results[1];
        assert.equal(set_a.builder, "builder_a");
        assert.equal(set_a.results.length, 3);
        assert.equal(set_a.results.length, 3);
        assert.equal(set_a.results[0].summary, "first");
        assert.equal(set_a.results[1].summary, "second");
        assert.equal(set_a.results[2].summary, "third");
        assert.equal(set_b.builder, "builder_b");
        assert.equal(set_b.results.length, 1);
    });
});
