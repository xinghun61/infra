// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

"use strict";

function TryJobResultSet(builder)
{
    this.builder = builder;
    this.results = [];
    Object.preventExtensions(this);
}


TryJobResultSet.prototype.latestSummaryAndMoreInfo = function()
{
    for (var i = this.results.length - 1; i >= 0; --i)
        if (this.results[i].summary)
            return {
                summary: this.results[i].summary,
                moreInfoUrl: this.results[i].moreInfoUrl,
            };

    return false;
};
