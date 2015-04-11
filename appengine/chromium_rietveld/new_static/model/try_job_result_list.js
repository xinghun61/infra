// Copyright (c) 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

"use strict";

function TryJobResultList(patchset)
{
    this.patchset = patchset;
    this.results = [];
    Object.preventExtensions(this);
}

TryJobResultList.TRY_JOBS_URL = "/api/{1}/{2}/try_job_results";

TryJobResultList.prototype.getTryJobsUrl = function()
{
    return TryJobResultList.TRY_JOBS_URL.assign(
        encodeURIComponent(this.patchset.issue.id),
        encodeURIComponent(this.patchset.id));
};

TryJobResultList.prototype.loadResults = function()
{
    var self = this;
    return loadJSON(this.getTryJobsUrl()).then(function(data) {
        self.parseData(data);
        return self.results;
    });
};

TryJobResultList.prototype.parseData = function(data)
{
    var tryResults = (data || []).groupBy("builder");
    this.results = Object.keys(tryResults)
        .sort()
        .map(function(builder) {
            var jobSet = new TryJobResultSet(builder);
            // TODO(esprehn): TryJobResultSet should probaby have a parseData.
            jobSet.results = tryResults[builder].map(function(resultData) {
                var result = new TryJobResult();
                result.parseData(resultData);
                return result;
            }).reverse();
            return jobSet;
        });
};
