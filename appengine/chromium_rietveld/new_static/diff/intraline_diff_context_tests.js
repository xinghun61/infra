// Copyright (c) 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

"use strict";

describe("IntralineDiffContext", function() {
    var assert = chai.assert;
    var context = new IntralineDiffContext();

    function makeGroup(lineStrings) {
        var lines = [];
        for (var i = 0; i < lineStrings.length; i++) {
            var type = "both";
            if (lineStrings[i].charAt(0) == "+") type = "add";
            else if (lineStrings[i].charAt(0) == "-") type = "remove";
            var line = new DiffLine(type);
            line.text = lineStrings[i].slice(1);
            lines.push(line);
        }
        return new DiffGroup("delta", lines);
    };
    
    it("handles an empty diff", function() {
        var diffLines = [];
        context.setGroup(makeGroup(diffLines));
        assert.deepEqual(context.left.ranges, []);
        assert.deepEqual(context.right.ranges, []);
    });

    it("computes diff ops", function() {
        var diffLines = [
            " # Sort the data",
            "-bubblesort(arr)",
            "+quicksort(arr)",
            " return arr",
        ];
        var group = makeGroup(diffLines);
        var charOps = context.computeOps(group);
        assert.equal(charOps.length, 3);
        assert.deepEqual(charOps[0], ["equal", 0, 16, 0, 16]);
        assert.deepEqual(charOps[1], ["replace", 16, 26, 16, 25]);
        assert.deepEqual(charOps[2], ["equal", 26, 43, 25, 42]);
    });

    it("converts token diff ops into character diff ops", function() {
        var tokenOps = [
            ["equal", 0, 8, 0, 8],
            ["replace", 8, 9, 8, 9],
            ["equal", 9, 17, 9, 17],
        ];
        var leftTokens = [
            "#", " ", "Sort", " ", "the", " ", "data", "\n",
            "bubblesort", "(", "arr", ")", "\n",
            "return", " ", "arr", "\n",
        ];
        var rightTokens = [
            "#", " ", "Sort", " ", "the", " ", "data", "\n",
            "quicksort", "(", "arr", ")", "\n",
            "return", " ", "arr", "\n",
        ];
        var charOps = context.convertTokenOpsToCharOps(tokenOps, leftTokens, rightTokens);
        assert.equal(charOps.length, 3);
        assert.deepEqual(charOps[0], ["equal", 0, 16, 0, 16]);
        assert.deepEqual(charOps[1], ["replace", 16, 26, 16, 25]);
        assert.deepEqual(charOps[2], ["equal", 26, 43, 25, 42]);
    });

    it("determines the start position of each token, plus EOS", function() {
        var tokens = [
            "#", " ", "Sort", " ", "the", " ", "data", "\n",
        ];
        var tokenStarts = context.accumulateLengths(tokens);
        assert.deepEqual(
            tokenStarts,
            [0, 1, 2, 6, 7, 10, 11, 15, 16]);
    });

    it("filters lines by side and joins them into complete text", function() {
        var diffLines = [
            " # Sort the data",
            "-# read stdin",
            "-bubblesort(arr)",
            "+# parse request",
            "+quicksort(arr)",
            " return arr",
        ];
        var group = makeGroup(diffLines);
        var leftText = context.filterAndJoinLines(group.lines, "remove");
        assert.equal(leftText, "# Sort the data\n# read stdin\nbubblesort(arr)\nreturn arr\n");
        var rightText = context.filterAndJoinLines(group.lines, "add");
        assert.equal(rightText, "# Sort the data\n# parse request\nquicksort(arr)\nreturn arr\n");
    });

    it("assigns diff ops to the left and right sides", function() {
        var diffOps = [
            ["equal", 0, 10, 0, 10],
            ["delete", 10, 12, 0, 0],
            ["insert", 0, 0, 10, 14],
            ["replace", 12, 15, 14, 16],
        ];
        context.assignLeftAndRightRanges(diffOps);
        assert.deepEqual(context.left.ranges[0], {start: 10, end: 12});
        assert.deepEqual(context.left.ranges[1], {start: 12, end: 15});
        assert.deepEqual(context.right.ranges[0], {start: 10, end: 14});
        assert.deepEqual(context.right.ranges[1], {start: 14, end: 16});
    });

});
