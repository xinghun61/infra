// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

"use strict";

// Represents a set of issues for a user's inbox view displayed with
// <cr-issue-inbox>. Can optionally load from a cached set of issues
// first, but only has a single cache so it's only useful for the
// login user.
function IssueList(user, options)
{
    this.user = user; // User
    this.incoming = []; // Array<Issue>
    this.outgoing = []; // Array<Issue>
    this.unsent = []; // Array<Issue>
    this.cc = []; // Array<Issue>
    this.draft = []; // Array<Issue>
    this.closed = []; // Array<Issue>
    this.issues = {};
    this.cached = options && options.cached;
    Object.preventExtensions(this);
}

IssueList.ISSUE_LIST_URL = "/api/user_inbox/{1}";
IssueList.CACHE_KEY = "IssueList.cachedIssues";
IssueList.CACHE_JSON_KEY = "IssueList.cachedIssues.json";
IssueList.CACHE_AGE_KEY = "IssueList.cachedIssues.age";

IssueList.SECTION_TO_PROPERTY_MAP = {
    "outgoing_issues": "outgoing",
    "unsent_issues": "unsent",
    "review_issues": "incoming",
    "closed_issues": "closed",
    "cc_issues": "cc",
    "draft_issues": "draft",
};

IssueList.prototype.getIssueListUrl = function()
{
    var name = this.user.email || this.user.name;
    return IssueList.ISSUE_LIST_URL.assign(encodeURIComponent(name));
};

IssueList.prototype.getIssue = function(id)
{
    if (!this.issues[id])
        this.issues[id] = new Issue(id);
    return this.issues[id];
};

IssueList.prototype.loadIssues = function()
{
    // Clear the old document based cache.
    localStorage.setItem(IssueList.CACHE_KEY, "");

    if (this.cached)
        this.loadCachedIssues();

    var self = this;
    return loadText(this.getIssueListUrl()).then(function(text) {
        // Always parse first so if the parse fails we don't cache broken JSON.
        self.parseData(JSON.parse(text));
        if (self.cached) {
            localStorage.setItem(IssueList.CACHE_JSON_KEY, text);
            localStorage.setItem(IssueList.CACHE_AGE_KEY, Date.create());
        }
    });
};

IssueList.prototype.loadCachedIssues = function()
{
    var age = Date.create(localStorage.getItem(IssueList.CACHE_AGE_KEY) || "");
    if (age.isBefore(Date.create("yesterday")))
        localStorage.setItem(IssueList.CACHE_JSON_KEY, "");
    var text = localStorage.getItem(IssueList.CACHE_JSON_KEY);
    if (text)
        this.parseData(JSON.parse(text));
};

IssueList.prototype.parseData = function(data)
{
    for (var section in data) {
        var propertyName = IssueList.SECTION_TO_PROPERTY_MAP[section];
        if (!propertyName) {
            console.log("Unknown issue inbox section: " + section);
            continue;
        }
        var sectionData = data[section];
        var currentType = [];
        this[propertyName] = currentType;
        for (var i = 0; i < sectionData.length; ++i) {
            var issueData = sectionData[i];
            var issue = this.getIssue(issueData.issue);
            issue.parseInboxData(issueData);
            currentType.push(issue);
        }
    }
};
