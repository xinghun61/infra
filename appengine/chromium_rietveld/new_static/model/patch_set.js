// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

"use strict";

// https://codereview.chromium.org/api/148223004/70001/?comments=true
function PatchSet(issue, id, sequence)
{
    this.files = []; // Array<PatchFile>
    this.sourceFiles = []; // Array<PatchFile>
    this.testFiles = []; // Array<PatchFile>
    this.created = ""; // Date
    this.messageCount = 0;
    this.draftCount = 0;
    this.lastModified = ""; // Date
    this.issue = issue || null;
    this.owner = null // User
    this.title = "";
    this.id = id || 0;
    this.sequence = sequence || 0;
    this.commit = false;
    this.cqDryRun = false;
    this.mostRecent = false;
    this.active = false;
    this.dependsOnPatchset = null;
    this.dependentPatchsets = null; // Array<PatchSet>
    Object.preventExtensions(this);
}

PatchSet.DETAIL_URL = "/api/{1}/{2}/?comments=true&try_jobs=false";
PatchSet.PATCHSET_URL = "/{1}/#ps{2}";

PatchSet.prototype.getPatchsetUrl = function()
{
    return PatchSet.PATCHSET_URL.assign(
        encodeURIComponent(this.issue.id),
        encodeURIComponent(this.id));
};

PatchSet.prototype.getDetailUrl = function()
{
    return PatchSet.DETAIL_URL.assign(
        encodeURIComponent(this.issue.id),
        encodeURIComponent(this.id));
};

PatchSet.prototype.loadDetails = function()
{
    var patchset = this;
    return loadJSON(this.getDetailUrl()).then(function(data) {
        patchset.parseData(data);
    });
};

PatchSet.prototype.findFileById = function(id)
{
    return this.files.find({id: id});
};

PatchSet.prototype.findFileByName = function(name)
{
    return this.files.find({name: name});
};

PatchSet.prototype.parseData = function(data)
{
    var patchset = this;

    if (!this.issue || data.issue != this.issue.id || data.patchset != this.id) {
        throw new Error("Invalid patchset loaded " + data.issue + " != " + this.issue.id
            + " or " + data.patchset + " != " + this.id);
    }

    this.owner = new User(data.owner);
    // TODO(esprehn): The server calls it a message sometimes and a title others,
    // lets always call it a title.
    this.title = data.message || "";
    this.lastModified = Date.utc.create(data.modified);
    this.created = Date.utc.create(data.created);
    if (data.depends_on_patchset) {
      var tokens = data.depends_on_patchset.split(":");
      var dependsOnIssue = new Issue(parseInt(tokens[0]));
      dependsOnIssue.loadDetails();
      this.dependsOnPatchset = new PatchSet(dependsOnIssue, parseInt(tokens[1]), 0);
    }
    if (data.dependent_patchsets && data.dependent_patchsets.length != 0) {
      this.dependentPatchsets = [];
      data.dependent_patchsets.forEach(function(dependent_patchset, i) {
          var tokens = dependent_patchset.split(":");
          var dependentIssue = new Issue(parseInt(tokens[0]));
          dependentIssue.loadDetails();
          var dependentPatchset = new PatchSet(dependentIssue, parseInt(tokens[1]), i + 1);
          this.dependentPatchsets.push(dependentPatchset);
      }, this);
    }

    Object.keys(data.files || {}, function(name, value) {
        var file = new PatchFile(patchset, name);
        file.parseData(value);
        patchset.files.push(file);
    });

    this.files.sort(PatchFile.compare);
    // Make a doubly linked list of files
    if (this.files.length > 1) {
        for (var i = 0; i < this.files.length; ++i) {
            this.files[i].nextFile = this.files[i + 1];
            this.files[i].previousFile = this.files[i - 1];
        }
    }

    this.files.forEach(function(file) {
        if (file.isLayoutTest)
            this.testFiles.push(file);
        else
            this.sourceFiles.push(file);
    }, this);
};
