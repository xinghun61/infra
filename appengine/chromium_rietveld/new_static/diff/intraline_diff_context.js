// Copyright (c) 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

"use strict";

function IntralineDiffContext()
{
    this.left = new IntralineDiffSide("del");
    this.right = new IntralineDiffSide("ins");
    Object.preventExtensions(this);
}

// Keep the same max size as the old UI.  Groups larger than this
// will be shown as all different lines.
IntralineDiffContext.MAX_DIFF_INPUT_SIZE = 10 * 1024;

IntralineDiffContext.prototype.setGroup = function(group)
{
    this.left.reset();
    this.right.reset();
    if (group.type == "delta") {
        var diffOps = this.computeOps(group);
        this.assignLeftAndRightRanges(diffOps);
    }
};

IntralineDiffContext.prototype.computeOps = function(group)
{
    var totalChars = 0;
    for (var i = 0; i < group.lines.length; ++i) {
        var line = group.lines[i];
        totalChars += line.text.length;
    }
    if (totalChars > IntralineDiffContext.MAX_DIFF_INPUT_SIZE) {
        return [["replace", 0, totalChars, 0, totalChars]];
    }
    var leftText = this.filterAndJoinLines(group.lines, "remove");
    var rightText = this.filterAndJoinLines(group.lines, "add");
 
    // Do the diffs by tokens (whole words or individual non-word chars),
    // but then convert back to character indexes.
    var leftTokens = leftText.match(/[^\W_]+|[\W_]/g) || [];
    var rightTokens = rightText.match(/[^\W_]+|[\W_]/g) || [];
    var tokenMatcher = new difflib.SequenceMatcher(null, leftTokens, rightTokens);
    var charOpCodes = this.convertTokenOpsToCharOps(
        tokenMatcher.getOpcodes(), leftTokens, rightTokens);
    return charOpCodes;
};

IntralineDiffContext.prototype.convertTokenOpsToCharOps = function(
    tokenOpCodes, leftTokens, rightTokens)
{
    var leftTokenStarts = this.accumulateLengths(leftTokens);
    var rightTokenStarts = this.accumulateLengths(rightTokens);
    var charOpCodes = tokenOpCodes.map(function(op) {
        return [op[0],
                leftTokenStarts[op[1]],
                leftTokenStarts[op[2]],
                rightTokenStarts[op[3]],
                rightTokenStarts[op[4]]];
    });
    return charOpCodes;
};

IntralineDiffContext.prototype.accumulateLengths = function(tokens)
{
    if (!tokens.length) return [];
    var result = [];
    var sum = 0;
    for (var i = 0; i < tokens.length; ++i) {
        result.push(sum);
        sum += tokens[i].length;
    }
    result.push(sum);
    return result;    
};

IntralineDiffContext.prototype.filterAndJoinLines = function(lines, op)
{
    var sideLines = [];
    for (var i = 0; i < lines.length; ++i) {
        var line = lines[i];
        if (line.type == op || line.type == "both")
            sideLines.push(line.text);
    }
    var sideText = sideLines.join("\n");
    if (sideLines.length)
        sideText += "\n";
    return sideText;
};

IntralineDiffContext.prototype.assignLeftAndRightRanges = function(diffOps)
{
    for (var i = 0; i < diffOps.length; ++i) {
        var op = diffOps[i];
        if (op[0] == "delete" || op[0] == "replace") {
            this.left.ranges.push({start: op[1], end: op[2]});
        }
        if (op[0] == "insert" || op[0] == "replace") {
            this.right.ranges.push({start: op[3], end: op[4]});
        }
    }
};
