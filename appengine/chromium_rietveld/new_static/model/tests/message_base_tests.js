// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

"use strict";

describe("MessageBase", function() {
    var assert = chai.assert;

    function Message() { }
    Message.extends(MessageBase);

    it("should quote in email format", function() {
        var message = new Message();
        message.text = "This is a\n> quoted message";
        message.author = User.forName("Elliott Sprehn", "esprehn@chromium.org");
        message.date = Date.create("2011-07-05 12:24:55.528Z");
        var quotedText = message.emailQuote();
        assert.equal(quotedText, "On 2011/07/05 at 12:24:55, Elliott Sprehn wrote:\n> This is a\n> > quoted message\n\n");
    });
});
