// Copyright (c) 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

"use strict";

function DiffBuilderUnified(file, output)
{
    DiffBuilderBase.call(this, file, output);
    Object.preventExtensions(this);
}
DiffBuilderUnified.extends(DiffBuilderBase);

DiffBuilderUnified.prototype.emitGroup = function(group, beforeSection)
{
    var section = document.createElement("div");
    section.className = "section " + group.type;
    for (var i = 0; i < group.lines.length; ++i)
        this.emitLine(section, group.lines[i]);
    this.output.insertBefore(section, beforeSection);
};

DiffBuilderUnified.prototype.emitLine = function(section, line)
{
    var row = document.createElement("div");
    row.className = "row " + line.type;

    row.appendChild(this.createLineNumber(line, line.beforeNumber, "remove"));
    row.appendChild(this.createLineNumber(line, line.afterNumber, "add"));
    row.appendChild(this.createText(line));

    var contextAction = this.createContextAction(section, line);
    if (contextAction)
        row.appendChild(contextAction);

    section.appendChild(row);

    var messages = this.createMessages(line);
    if (messages)
        section.appendChild(messages);
};
