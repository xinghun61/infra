// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

"use strict";

function DiffBuilder(file, output)
{
    this.file = file;
    this.highlighter = new SyntaxHighlighter(file.language, file.containsEmbeddedLanguages);
    this.output = output;
}

DiffBuilder.prototype.emitDiff = function(diff)
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
    for (var i = 0; i < groups.length; ++i)
        this.emitGroup(groups[i]);
};

// Moves and copies need a header at the start of the file.
DiffBuilder.prototype.emitMoveHeader = function(text)
{
    var section = document.createElement("div");
    this.output.appendChild(section);
    var line = new DiffLine("header");
    line.text = text;
    this.emitLine(section, line);
};

DiffBuilder.prototype.emitGroup = function(group, beforeSection)
{
    var section = document.createElement("div");
    for (var i = 0; i < group.length; ++i)
        this.emitLine(section, group[i]);
    this.output.insertBefore(section, beforeSection);
};

DiffBuilder.prototype.emitLine = function(section, line)
{
    var file = this.file;

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

    // TODO(esprehn): Editing a multi line comment can end up making an entire file
    // look like a comment. For now we reset the syntax highlighter between
    // sections to avoid this in the common case. This will break headers
    // in the middle of multi line comments, but that's very rare.
    if (line.type == "header")
        this.highlighter.resetSyntaxState();
};

DiffBuilder.prototype.createContextAction = function(section, line)
{
    if (!line.context)
        return null;
    var action = document.createElement("cr-action");
    action.textContent = "Show context";
    action.className = "show-context";
    action.line = line;
    action.section = section;
    return action;
};

DiffBuilder.prototype.createLineNumber = function(line, number, type)
{
    var div = document.createElement("div");
    div.className = "line-number";
    if (line.type == "both" || line.type == type)
        div.setAttribute("value", number);
    else if (line.type == "header")
        div.setAttribute("value", "@@");
    return div;
};

DiffBuilder.prototype.createText = function(line)
{
    var div = document.createElement("div");
    div.className = "text";
    if (!line.text)
        return div;
    var html = this.highlighter.parseText(line.text);
    // If the html is just the text then it didn't get highlighted so we can
    // use textContent which is faster than innerHTML.
    if (!html || html == line.text) {
        div.textContent = line.text;
    } else {
        div.innerHTML = html;
    }
    return div;
};

DiffBuilder.prototype.messagesForLine = function(line, number, type)
{
    if (line.type == "both" || line.type == type)
        return this.file.messages[number];
    return null;
};

DiffBuilder.prototype.createMessages = function(line)
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

    var messages = document.createElement("cr-patch-file-messages");
    messages.beforeMessages = beforeMessages;
    messages.afterMessages = afterMessages;
    messages.file = this.file;

    return messages;
};
