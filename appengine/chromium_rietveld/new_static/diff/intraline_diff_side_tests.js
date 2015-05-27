// Copyright (c) 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

"use strict";

describe("IntralineDiffSide", function() {
    var assert = chai.assert;
    var side = null;

    beforeEach(function() {
        side = new IntralineDiffSide("ins");
    });

    it("starts off empty", function() {
        assert.deepEqual(side.ranges, []);
        assert.deepEqual(side.position, 0);
    });

    it("starts resets to empty", function() {
        side.ranges = [[1, 100]];
        side.position = 12;
        side.reset();
        assert.deepEqual(side.ranges, []);
        assert.deepEqual(side.position, 0);
    });

    it("detects when the current line is within the first range", function() {
        side.ranges = [{start: 0, end: 10}];
        side.position = 12;
        assert.isFalse(side.isWholeLine("bubblesort()"));

        side.ranges = [{start: 0, end: 18}];
        side.position = 12;
        assert.isFalse(side.isWholeLine("bubblesort()"));

        side.ranges = [{start: 0, end: 100}];
        side.position = 12;
        assert.isTrue(side.isWholeLine("bubblesort()"));
                       
        side.ranges = [{start: 18, end: 100}];
        side.position = 12;
        assert.isFalse(side.isWholeLine("bubblesort()"));
    });

    it("inserts tags at the boundaries of ranges", function() {
        side.ranges = [{start: 6, end: 10}];
        var src = "bubblesort()";
        var html = "bubblesort()";  // no syntax highlighting in this case.
        var newHtml = side.insertTags(src, html);
        assert.equal(newHtml, "bubble<ins>sort</ins>()");

        var html = "<span class=ident>bubblesort</span>()";  // w/ highlighting.
        newHtml = side.insertTags(src, html);
        assert.equal(newHtml, "<span class=ident>bubble<ins>sort</ins></span>()");        
    });

    it("processes lines with intraline diffs by inserting tags", function() {
        side.ranges = [{start: 6, end: 10}];
        var src = "bubblesort()";
        var html = "<span class=ident>bubblesort</span>()";
        var div = {className: "text"};
        var newHtml = side.processLine(div, src, html);
        assert.equal(newHtml, "<span class=ident>bubble<ins>sort</ins></span>()");
        assert.equal(div.className, "text");
    });

    it("processes completely changed lines by adding whole-line", function() {
        side.ranges = [{start: 0, end: 100}];
        var src = "bubblesort()";
        var html = "<span class=ident>bubblesort</span>()";
        var div = {className: "text"};
        var newHtml = side.processLine(div, src, html);
        assert.equal(newHtml, html);
        assert.equal(div.className, "text whole-line");
    });

    it("converts ranges to local ranges", function() {
        side.position = 100;
        side.ranges = [
            {start: 20, end: 50},
            {start: 112, end: 115},
            {start: 200, end: 250},
        ];
        var localRanges = side.makeLocalRangesForCurrentLine(20);
        assert.deepEqual(
            localRanges,
            [{start: 12, end: 15}]);
    });

    it("inserts tags inside a range to avoid mismatched tags", function() {
        var html = "bubble(<i>arr</i>)";
        var newHtml = side.insertTagsInsideRange(html);
        assert.equal(
            newHtml,
            "bubble(</ins><i><ins>arr</ins></i><ins>)");
    });

    it("slices html counting entities as 1 and tags as 0 chars", function() {
        var result = side.slice("abcdefghij", 0, 10);
        assert.equal(result.text, "abcdefghij");
        assert.equal(result.index, 10);

        result = side.slice("abcdefghij", 0, 5);
        assert.equal(result.text, "abcde");
        assert.equal(result.index, 5);

        result = side.slice("ab<span>cd&nbsp;</span>fghij", 0, 10);
        assert.equal(result.text, "ab<span>cd&nbsp;</span>fghij");
        assert.equal(result.index, 28);
        
        result = side.slice("ab<span>cd&nbsp;</span>fghij", 0, 5);
        assert.equal(result.text, "ab<span>cd&nbsp;");
        assert.equal(result.index, 16);
    });

});
