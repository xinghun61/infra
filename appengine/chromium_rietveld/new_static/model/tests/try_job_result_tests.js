// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

"use strict";

describe("TryJobResult", function() {
    var assert = chai.assert;

    var BUILDER_URL = "http://build.chromium.org/p/tryserver.blink/builders/win_blink_rel/builds/12456";

    function createData() {
        return {
            parent_name: null,
            tests: [ ],
            slave: null,
            url: BUILDER_URL,
            timestamp: "2014-06-18 08:13:29.036400",
            builder: "win_blink_oilpan_rel",
            clobber: true,
            project: "project name",
            reason: "some reason",
            master: "tryserver.blink",
            result: 6, // Pending
            key: "xyz",
            requester: "esprehn@chromium.org",
            buildnumber: 123,
            revision: "HEAD",
            build_properties: '{"summary": "a summary"}'
        };
    }

    it("should parse basic daata", function() {
        var tryResult = new TryJobResult();
        var data = createData();
        tryResult.parseData(data);
        assert.deepEqual(tryResult.timestamp, Date.utc.create(data.timestamp));
        assert.equal(tryResult.builder, "win_blink_oilpan_rel");
        assert.isTrue(tryResult.clobber);
        assert.equal(tryResult.project, "project name");
        assert.equal(tryResult.reason, "some reason");
        assert.equal(tryResult.result, "pending");
        assert.equal(tryResult.revision, "HEAD");
        assert.equal(tryResult.buildnumber, 123);
        assert.equal(tryResult.master, "tryserver.blink");
        assert.equal(tryResult.url, BUILDER_URL);
        assert.equal(tryResult.summary, "a summary");
    });
    it("should convert results ids to names", function() {
        var data = createData();
        Object.keys(TryJobResult.RESULT, function(id, name) {
            var tryResult = new TryJobResult();
            data.result = parseInt(id, 10);
            tryResult.parseData(data);
            assert.equal(tryResult.result, name);
        });
    });
});
