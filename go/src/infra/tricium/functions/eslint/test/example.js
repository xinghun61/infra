// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// This function is formatted weirdly and
// also has the wrong indentation.
var func_var = function (){
    console.log('printed text');
}

func_var()  // Missing semicolon.

var unused_var = 0;

customElements.define(SomeError.is, SomeError);
