// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

"use strict";

function emailQuote(text, author, date)
{
    var date = date.utc(true).format("On {yyyy}/{MM}/{dd} at {HH}:{mm}:{ss}");
    var value = date + ", " + author + " wrote:\n";
    text.split("\n").forEach(function(line) {
        value += "> " + line + "\n";
    });
    value += "\n";
    return value;
}
