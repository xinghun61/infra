// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

"use strict";

describe("LinkTextParser", function() {
    var assert = chai.assert;

    function expectTokens(text, tokens) {
        var parser = new LinkTextParser(function(text, href) {
            if (!tokens.length)
                throw new Error("Not enough tokens");
            var expected = tokens.shift();
            if (typeof expected == "string") {
                assert.isUndefined(href);
                assert.equal(text, expected);
            } else {
                assert.equal(href, expected.href);
                assert.equal(text, expected.text);
            }
        });
        parser.parse(text);
    }

    it("should parse plain text", function() {
        expectTokens("This is an issue\nFoo", [
            "This is an issue\nFoo"
        ]);
    });
    it("should parse links", function() {
        expectTokens("abc\n baz http://crbug.com/123 \nfoo bar", [
            "abc\n baz ",
            {href:"http://crbug.com/123", text:"http://crbug.com/123"},
            " \nfoo bar",
        ]);
    });
    it("should parse BUG= lines", function() {
        expectTokens("abc\n baz \nBUG=123 \nfoo bar", [
            "abc\n baz \n",
            "BUG=",
            {href:"https://code.google.com/p/chromium/issues/detail?id=123", text:"123"},
            " ",
            "\nfoo bar",
        ]);
    });
    it("should parse links and BUG= lines", function() {
        expectTokens("abc\n http://www.google.com/ baz \nBUG=456 \nfoo bar", [
            "abc\n ",
            {href:"http://www.google.com/", text:"http://www.google.com/"},
            " baz \n",
            "BUG=",
            {href:"https://code.google.com/p/chromium/issues/detail?id=456", text:"456"},
            " ",
            "\nfoo bar",
        ]);
    });
    it("should parse multiple bugs in a BUG= line", function() {
        expectTokens("abc\nBUG=456, 678", [
            "abc\n",
            "BUG=",
            {href:"https://code.google.com/p/chromium/issues/detail?id=456", text:"456"},
            ", ",
            {href:"https://code.google.com/p/chromium/issues/detail?id=678", text:"678"},
        ]);
    });
    it("should parse tracker prefix in a BUG= line", function() {
        expectTokens("abc\nBUG=456,   v8:678,chromium-os:123456", [
            "abc\n",
            "BUG=",
            {href:"https://code.google.com/p/chromium/issues/detail?id=456", text:"456"},
            ",   ",
            {href:"https://code.google.com/p/v8/issues/detail?id=678", text:"v8:678"},
            ",",
            {href:"https://code.google.com/p/chromium-os/issues/detail?id=123456", text:"chromium-os:123456"},
        ]);
    });
    it("should parse both codesite and monorail trackers in a BUG= line", function() {
        expectTokens("abc\nBUG=chromium:123456,monorail:789", [
            "abc\n",
            "BUG=",
            {href:"https://code.google.com/p/chromium/issues/detail?id=123456", text:"chromium:123456"},
            ",",
            {href:"https://bugs.chromium.org/p/monorail/issues/detail?id=789", text:"monorail:789"},
        ]);
    });
    it("should ignore invalid trackers in a BUG= line", function() {
        expectTokens("abc\nBUG=foo:678\nbar", [
            "abc\n",
            "BUG=",
            "foo:678",
            "\nbar",
        ]);
    });
});
