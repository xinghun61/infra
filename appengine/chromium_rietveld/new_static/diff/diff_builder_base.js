// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

"use strict";

function DiffBuilderBase(file, output)
{
    this.file = file;
    this.highlighter = new SyntaxHighlighter(file.language);
    this.output = output;
    this.intralineContext = new IntralineDiffContext();
}

DiffBuilderBase.prototype.emitDiff = function(diff)
{
    if (diff.isImage) {
        var image = document.createElement("cr-diff-image");
        image.file = this.file;
        this.output.appendChild(image);
        return;
    }
    if (diff.from)
        this.emitMoveHeader(diff.from);
    var groups = diff.groups;
    for (var i = 0; i < groups.length; ++i) {
        this.emitGroup(groups[i]);
        // TODO(esprehn): Editing a multi line comment can end up making an
        // entire file look like a comment. For now we reset the syntax
        // highlighter between sections to avoid this in the common case. This
        // will break headers in the middle of multi line comments, but that's
        // very rare.
        if (groups[i].type == "header")
            this.highlighter.resetSyntaxState();
    }
};

// Moves and copies need a header at the start of the file.
DiffBuilderBase.prototype.emitMoveHeader = function(text)
{
    var line = new DiffLine("header");
    line.text = text;
    this.emitGroup(new DiffGroup("header", [line]));
};

DiffBuilderBase.prototype.emitGroup = function(group, beforeSection)
{
    throw new Error("Subclasses must implement emitLine.");
};

DiffBuilderBase.prototype.createContextAction = function(section, line)
{
    if (!line.context)
        return null;
    var action = document.createElement("a", "cr-action");
    action.textContent = "Show context";
    action.className = "show-context";
    action.line = line;
    action.section = section;
    return action;
};

DiffBuilderBase.prototype.createLineNumber = function(line, number, type)
{
    var div = document.createElement("div");
    div.className = "line-number";
    if (line.type == "header")
        div.setAttribute("value", "@@");
    else if (line.type == "both" || line.type == type)
        div.setAttribute("value", number);
    return div;
};

DiffBuilderBase.prototype.createText = function(line, intralineSide)
{
    var div = document.createElement("div");
    div.className = "text";
    var text = line.text || "";
    var html = this.highlighter.parseText(text) || text.escapeHTML();
    if (intralineSide)
        html = intralineSide.processLine(div, text, html);

    // If the html is just the text then it didn't get highlighted so we can
    // use textContent which is faster than innerHTML.
    if (html == text) {
        div.textContent = text;
    } else {
        div.innerHTML = html;
    }
    return div;
};

DiffBuilderBase.prototype.messagesForLine = function(line, number, type)
{
    if (line.type == "both" || line.type == type)
        return this.file.messages[number];
    return null;
};

DiffBuilderBase.prototype.createMessages = function(line)
{
    var beforeMessages = this.messagesForLine(line, line.beforeNumber, "remove");
    var afterMessages = this.messagesForLine(line, line.afterNumber, "add");

    if (!beforeMessages && !afterMessages)
        return null;

    beforeMessages = (beforeMessages || []).filter(function(message) {
        return message.left;
    });

    afterMessages = (afterMessages || []).filter(function(message) {
        return !message.left;
    });

    if (!beforeMessages.length && !afterMessages.length)
        return null;

    var messages = document.createElement("cr-diff-messages");
    messages.beforeMessages = beforeMessages;
    messages.afterMessages = afterMessages;
    messages.file = this.file;

    return messages;
};
