// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

"use strict";

function PatchFile(patchset, name)
{
    this.name = name || "";
    this.prefix = name || "";
    this.extension = "";
    this.language = "";
    this.status = "";
    this.chunks = 0;
    this.missingBaseFile = false;
    this.propertyChanges = "";
    this.added = 0;
    this.removed = 0;
    this.id = 0;
    this.patchset = patchset || null; // PatchSet
    this.isBinary = false;
    this.messages = {}; // Map<line number, Array<PatchFileMessage>>
    this.messageCount = 0;
    this.drafts = []; // Array<PatchFileMessage>
    this.draftCount = 0;
    this.diff = null;
    this.isLayoutTest = this.name.startsWith("LayoutTests/");
    this.isHeader = false;
    this.previousFile = null;
    this.nextFile = null;
    Object.preventExtensions(this);

    var dotIndex = this.name.lastIndexOf(".");
    if (dotIndex != -1) {
        this.extension = this.name.from(dotIndex + 1);
        this.isHeader = PatchFile.HEADER_EXTENSIONS[this.extension] || false;
        this.prefix = this.name.to(dotIndex);
        this.language = PatchFile.SYNTAX_LANGUAGES[this.extension] || "";
    }
}

PatchFile.DIFF_URL = "/download/issue{1}_{2}_{3}.diff";
PatchFile.CONTEXT_URL = "/{1}/diff_skipped_lines/{2}/{3}/{4}/{5}/a/2000";
PatchFile.DRAFT_URL = "/api/{1}/{2}/{3}/draft_message";
PatchFile.IMAGE_URL = "/{1}/image/{2}/{3}/{4}";
PatchFile.SINGLE_VIEW_URL = "/{1}/diff/{2}/{3}";

PatchFile.SYNTAX_LANGUAGES = {
    "cc": "cpp",
    "cgi": "perl",
    "coffee": "coffeescript",
    "cpp": "cpp",
    "css": "css",
    "dart": "dart",
    "go": "go",
    "h": "cpp",
    "html": "html",
    // TODO(esprehn): We should create a proper language definition for idl.
    // For now we use ActionScript since they're actually quite similar.
    "idl": "actionscript",
    "ini": "ini",
    "js": "javascript",
    "json": "json",
    "md": "markdown",
    "mm": "objectivec",
    "m": "objectivec",
    "pl": "perl",
    "pm": "perl",
    "py": "python",
    "rb": "ruby",
    "sh": "bash",
    "svg": "xml",
    "xhtml": "html",
    "xml": "xml",
};

PatchFile.HEADER_EXTENSIONS = {
    "h": true,
    "hxx": true,
    "hpp": true,
};

PatchFile.compare = function(a, b)
{
    if (a.isLayoutTest != b.isLayoutTest)
        return b.isLayoutTest ? -1 : 1;
    if (a.prefix != b.prefix)
        return a.prefix.localeCompare(b.prefix);
    if (a.isHeader != b.isHeader)
        return a.isHeader ? -1 : 1;
    return a.extension.localeCompare(b.extension);
};

PatchFile.prototype.addMessage = function(message)
{
    if (!this.messages[message.line])
        this.messages[message.line] = [];
    if (this.messages[message.line].find(message))
        return;
    this.messages[message.line].push(message);
    this.messageCount++;
    this.patchset.messageCount++;
    if (message.draft) {
        this.drafts.push(message);
        this.drafts.sort(function(a, b) {
            return a.line - b.line;
        });
        this.draftCount++;
        this.patchset.draftCount++;
        this.patchset.issue.draftCount++;
    }
};

PatchFile.prototype.removeMessage = function(message)
{
    var messages = this.messages[message.line];
    if (!messages || !messages.find(message))
        return;
    messages.remove(message);
    this.messageCount--;
    this.patchset.messageCount--;
    if (message.draft) {
        this.drafts.remove(message);
        this.draftCount--;
        this.patchset.draftCount--;
        this.patchset.issue.draftCount--;
    }
};

PatchFile.prototype.parseData = function(data)
{
    this.status = data.status || "";
    this.chunks = data.num_chunks || 0;
    this.missingBaseFile = data.no_base_file || false;
    this.propertyChanges = data.property_changes || "";
    this.added = Math.max(0, data.num_added || 0);
    this.removed = Math.max(0, data.num_removed || 0);
    this.id = data.id || 0;
    this.isBinary = data.is_binary || false;

    var self = this;
    (data.messages || []).forEach(function(messageData) {
        var message = new PatchFileMessage(self);
        message.parseData(messageData);
        self.addMessage(message);
    });

    Object.each(this.messages, function(line, messages) {
        messages.sort(function(messageA, messageB) {
            return messageA.date - messageB.date;
        });
    });
};

PatchFile.prototype.getDiffUrl = function()
{
    return PatchFile.DIFF_URL.assign(
        encodeURIComponent(this.patchset.issue.id),
        encodeURIComponent(this.patchset.id),
        encodeURIComponent(this.id));
};

PatchFile.prototype.getSingleViewUrl = function()
{
    return PatchFile.SINGLE_VIEW_URL.assign(
        encodeURIComponent(this.patchset.issue.id),
        encodeURIComponent(this.patchset.id),
        this.name);
};

PatchFile.prototype.getOldImageUrl = function()
{
    return PatchFile.IMAGE_URL.assign(
        encodeURIComponent(this.patchset.issue.id),
        encodeURIComponent(this.patchset.id),
        encodeURIComponent(this.id),
        0);
};

PatchFile.prototype.getNewImageUrl = function()
{
    return PatchFile.IMAGE_URL.assign(
        encodeURIComponent(this.patchset.issue.id),
        encodeURIComponent(this.patchset.id),
        encodeURIComponent(this.id),
        1);
};

PatchFile.prototype.getContextUrl = function(start, end)
{
    return PatchFile.CONTEXT_URL.assign(
        encodeURIComponent(this.patchset.issue.id),
        encodeURIComponent(this.patchset.id),
        encodeURIComponent(this.id),
        encodeURIComponent(start),
        encodeURIComponent(end));
};

PatchFile.prototype.getDraftUrl = function()
{
    return PatchFile.DRAFT_URL.assign(
        encodeURIComponent(this.patchset.issue.id),
        encodeURIComponent(this.patchset.id),
        encodeURIComponent(this.id));
};

PatchFile.prototype.saveDraft = function(message, newText)
{
    var self = this;
    var data = this.createDraftData(message);
    data.text = newText;
    return sendFormData(this.getDraftUrl(), data, {
        responseType: "json",
    }).then(function(xhr) {
        if (!(xhr.response instanceof Object))
            throw new Error("Server error.");
        message.parseData(xhr.response);
        self.addMessage(message);
        return true;
    });
};

PatchFile.prototype.discardDraft = function(message)
{
    if (!message.messageId) {
        this.removeMessage(message);
        return;
    }
    var self = this;
    var data = this.createDraftData(message)
    data.text = "";
    return sendFormData(this.getDraftUrl(), data, {
        responseType: "json",
    }).then(function() {
        self.removeMessage(message);
        return true;
    });
};

PatchFile.prototype.createDraftData = function(message)
{
    return {
        lineno: message.line,
        left: message.left,
        text: message.text,
        message_id: message.messageId,
    };
};

PatchFile.prototype.loadDiff = function()
{
    var self = this;
    var diff = this.diff;
    if (diff) {
        return new Promise(function(resolve, reject) {
            setTimeout(function() {
                resolve(diff);
            });
        });
    }
    return loadText(this.getDiffUrl()).then(function(text) {
        return self.parseDiff(text);
    });
};

PatchFile.prototype.parseDiff = function(text)
{
    var self = this;
    var parser = new DiffParser(text);
    var result = parser.parse();
    if (!result || !result[0] || result[0].name != this.name)
        return Promise.reject(new Error("No diff available"));
    var diff = result[0];
    if (!diff.external || diff.isImage) {
        self.diff = diff;
        return Promise.resolve(diff);
    }
    return this.loadContext(0, Number.MAX_SAFE_INTEGER).then(function(group) {
        diff.groups = [group];
        self.diff = diff;
        return diff;
    });
};

PatchFile.prototype.loadContext = function(start, end)
{
    return loadJSON(this.getContextUrl(start, end)).then(function(data) {
        var group = new DiffGroup("both");
        group.parseContextData(data);
        return group;
    });
};
