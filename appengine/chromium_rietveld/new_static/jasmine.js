// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

"use strict";

function asyncIt(name, fn)
{
    it(name, function() {
        var test = this;
        var done = false;
        function finish(error) {
            done = true;
            if (error)
                test.fail(error);
        }
        var result = fn.call(this, function(result) {
            finish(result);
        });
        if (result instanceof Promise) {
            result.then(function() {
                finish();
            }, function(error) {
                test.fail(error);
            });
        }
        waitsFor(function() {
            return done;
        }, 50);
    });
}
