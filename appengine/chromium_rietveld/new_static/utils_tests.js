// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

"use strict";

describe("Utils", function() {
describe("emailQuote", function() {
    var assert = chai.assert;

    it("should quote in email format", function() {
        var date = Date.create("2011-07-05 12:24:55.528Z");
        var text = emailQuote("This is a\n> quoted message", "Elliott Sprehn", date);
        assert.equal(text, "On 2011/07/05 at 12:24:55, Elliott Sprehn wrote:\n> This is a\n> > quoted message\n\n");
    });
});
});
