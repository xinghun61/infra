// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

"use strict";

function SearchResult(issues, cursor)
{
    this.cursor = cursor || "";
    this.issues = issues || []; // Array<Issue>
}

SearchResult.prototype.findNext = function()
{
    return Search.findIssues({cursor: this.cursor});
};
