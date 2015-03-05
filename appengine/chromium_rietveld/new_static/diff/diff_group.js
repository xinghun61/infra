// Copyright (c) 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

"use strict";

function DiffGroup(type, lines)
{
    this.type = type;
    this.lines = [];
    this.adds = [];
    this.removes = [];
    Object.preventExtensions(this);
    if (lines)
        lines.forEach(this.addLine, this);
}

DiffGroup.prototype.addLine = function(line)
{
    this.lines.push(line);
    if (line.type == "add")
        this.adds.push(line);
    else if (line.type == "remove")
        this.removes.push(line);
};

DiffGroup.prototype.getSideBySidePairs = function()
{
    if (this.type == "both" || this.type == "header") {
        return this.lines.map(function(line) {
            return {
                left: line,
                right: line,
            };
        });
    }
    var pairs = new Array(Math.max(this.adds.length, this.removes.length));
    var i = 0;
    var j = 0;
    for ( ; i < this.removes.length || j < this.adds.length; ++i, ++j) {
        pairs[i] = {
            left: this.removes[i] || DiffLine.BLANK_LINE,
            right: this.adds[j] || DiffLine.BLANK_LINE,
        };
    }
    return pairs;
};
