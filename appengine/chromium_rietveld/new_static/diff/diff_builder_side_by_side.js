// Copyright (c) 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

"use strict";

function DiffBuilderSideBySide(file, output)
{
    DiffBuilderBase.call(this, file, output);
    Object.preventExtensions(this);
}
DiffBuilderSideBySide.extends(DiffBuilderBase);

DiffBuilderSideBySide.prototype.emitGroup = function(group, beforeSection)
{
    this.intralineContext.setGroup(group);
    var section = document.createElement("div");
    section.className = "section side-by-side " + group.type;
    var pairs = group.getSideBySidePairs();
    for (var i = 0; i < pairs.length; ++i) {
        var pair = this.createPair(section, pairs[i].left, pairs[i].right);
        section.appendChild(pair);
    }
    this.output.insertBefore(section, beforeSection);
};

DiffBuilderSideBySide.prototype.createPair = function(
    section, leftLine, rightLine)
{
    var left = document.createElement("div");
    left.className = "left";
    var right = document.createElement("div");
    right.className = "right";
    var pair = document.createElement("div");
    pair.className = "pair";
    pair.appendChild(left);
    pair.appendChild(right);
    left.appendChild(this.createRow(
        section, leftLine, leftLine.beforeNumber,
        this.intralineContext.left));
    if (leftLine.type != "both") {
        var leftMessages = this.createMessages(leftLine);
        if (leftMessages)
            left.appendChild(leftMessages);
    }
    right.appendChild(this.createRow(
        section, rightLine, rightLine.afterNumber,
        this.intralineContext.right));
    var rightMessages = this.createMessages(rightLine);
    if (rightMessages)
        right.appendChild(rightMessages);
    return pair;
};

DiffBuilderSideBySide.prototype.createRow = function(
    section, line, lineNumber, intralineSide)
{
    var row = document.createElement("div");
    row.className = "row " + line.type;

    if (line.type == "blank")
        return row;

    row.appendChild(this.createLineNumber(line, lineNumber, line.type));
    row.appendChild(this.createText(line, intralineSide));
    var action = this.createContextAction(section, line);
    if (action)
        row.appendChild(action);

    return row;
};
