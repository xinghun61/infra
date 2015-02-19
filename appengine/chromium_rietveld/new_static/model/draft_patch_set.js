// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

"use strict";

function DraftPatchSet(patchset)
{
    this.patchset = patchset;
    this.files = []; // Array<PatchFile>
    Object.preventExtensions(this);
}

DraftPatchSet.prototype.updateFiles = function()
{
    this.files = this.patchset.files.findAll(function(file) {
        return file.draftCount;
    });
};
