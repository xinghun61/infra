// Copyright (c) 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

"use strict";

function DiffGroup(type, lines)
{
    this.type = type;
    this.lines = lines || [];
    Object.preventExtensions(this);
}

DiffGroup.prototype.addLine = function(line)
{
    this.lines.push(line);
};
