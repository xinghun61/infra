// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Import statements are accepted by eslint
// only if it is parsing with "module" source type.
// this is here to check that eslint will continue
// checking the rest of the file in JS modules.
import 'foo.js';

// Use strict is not necessary in JS modules.
// This is here to check whether warnings about
// use strict are enabled.
'use strict';

// Functions marked as async should not result in parser errors.
async function foo() {
    return Promise.resolve('yes');
}

// This function is formatted weirdly and
// also has the wrong indentation.
var func_var = function (){
    console.log('printed text');
}
func_var()  // Missing semicolon.
const unusedVar = 0;
