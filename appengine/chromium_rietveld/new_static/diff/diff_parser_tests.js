// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

"use strict";

describe("DiffParser", function() {
    var assert = chai.assert;

    it("should detect image file names", function() {
        assert.isTrue(DiffParser.isImageFile("foo.png"));
        assert.isTrue(DiffParser.isImageFile("foo.bar.jpeg"));
        assert.isTrue(DiffParser.isImageFile("foo(baz).jpg"));
        assert.isTrue(DiffParser.isImageFile("_foo_.webp"));
        assert.isTrue(DiffParser.isImageFile("example-file-name.bmp"));
        assert.isTrue(DiffParser.isImageFile("is a. gif.gif"));
        assert.isFalse(DiffParser.isImageFile(".gif"));
        assert.isFalse(DiffParser.isImageFile("not a gif.gif.txt"));
    });
    it("should not show context link for file deletes", function() {
        var text =
            "Index: example.cc\n" +
            "diff --git a/example.cc b/example.cc\n" +
            "index aaf..def 100644\n" +
            "--- a/example.cc\n" +
            "+++ b/example.cc\n" +
            "@@ -1,1 +0,0 @@ File deleted\n" +
            "- This was a line\n";
        var parser = new DiffParser(text);
        var result = parser.parse()[0];
        assert.equal(result.name, "example.cc");
        assert.equal(result.groups.length, 3);
        assert.equal(result.groups[0].type, "header");
        assert.equal(result.groups[0].lines.length, 1);
        assert.equal(result.groups[0].lines[0].type, "header");
        assert.isFalse(result.groups[0].lines[0].context);
        assert.equal(result.groups[0].lines[0].text, "File deleted");
    });
    it("should show context for one line headers", function() {
        var text =
            "Index: example.cc\n" +
            "diff --git a/example.cc b/example.cc\n" +
            "index aaf..def 100644\n" +
            "--- a/example.cc\n" +
            "+++ b/example.cc\n" +
            "@@ -1,2 +1,1 @@ Context 1\n" +
            " A line of text\n" +
            "- Example line 1\n" +
            "@@ -4,2 +3,1 @@ Context 2\n" +
            " A line of text\n" +
            "- Example line 1\n";
        var parser = new DiffParser(text);
        var result = parser.parse()[0];
        assert.equal(result.name, "example.cc");
        assert.equal(result.groups.length, 7);
        assert.equal(result.groups[0].type, "header");
        assert.equal(result.groups[0].lines.length, 1);
        assert.equal(result.groups[0].lines[0].type, "header");
        assert.isFalse(result.groups[0].lines[0].context);
        assert.equal(result.groups[0].lines[0].text, "Context 1");
        assert.equal(result.groups[3].type, "header");
        assert.equal(result.groups[3].lines.length, 1);
        assert.equal(result.groups[3].lines[0].type, "header");
        assert.isTrue(result.groups[3].lines[0].context);
        assert.equal(result.groups[3].lines[0].text, "Context 2");
    });
    it("should parse both one-number and two-number line ranges", function() {
        var text =
            "Index: example.cc\n" +
            "diff --git a/example.cc b/example.cc\n" +
            "index aaf..def 100644\n" +
            "--- a/example.cc\n" +
            "+++ b/example.cc\n" +
            "@@ -1 +1,1 @@ Context 1\n" +
            " A line of text\n" +
            "- Example line 1\n" +
            "@@ -4,2 +3,1 @@ Context 2\n" +
            " A line of text\n" +
            "- Example line 1\n";
        var parser = new DiffParser(text);
        var result = parser.parse()[0];
        assert.equal(result.name, "example.cc");
        assert.equal(result.groups.length, 7);
        assert.equal(result.groups[0].type, "header");
        assert.equal(result.groups[0].lines.length, 1);
        assert.equal(result.groups[0].lines[0].type, "header");
        assert.isFalse(result.groups[0].lines[0].context);
        assert.equal(result.groups[0].lines[0].text, "Context 1");
        assert.equal(result.groups[3].type, "header");
        assert.equal(result.groups[3].lines.length, 1);
        assert.equal(result.groups[3].lines[0].type, "header");
        assert.isTrue(result.groups[3].lines[0].context);
        assert.equal(result.groups[3].lines[0].text, "Context 2");
    });
    it("should skip lines with backslash prefixes", function() {
        var text =
            "Index: example.cc\n" +
            "diff --git a/example.cc b/example.cc\n" +
            "index aaf..def 100644\n" +
            "--- a/example.cc\n" +
            "+++ b/example.cc\n" +
            "@@ -1,2 +1,2 @@ Context 1\n" +
            " A line of text\n" +
            "-Example line 1\n" +
            "\\ No newline at end of file\n" +
            "+Example line 2\n";
        var parser = new DiffParser(text);
        var result = parser.parse()[0];
        assert.equal(result.name, "example.cc");
        assert.equal(result.groups.length, 4);
        assert.equal(result.groups[0].type, "header");
        assert.equal(result.groups[0].lines.length, 1);
        assert.equal(result.groups[0].lines[0].type, "header");
        assert.isFalse(result.groups[0].lines[0].context, false);
        assert.equal(result.groups[0].lines[0].text, "Context 1");
        assert.equal(result.groups[2].type, "delta");
        assert.equal(result.groups[2].lines.length, 2);
        assert.equal(result.groups[2].lines[0].type, "remove");
        assert.equal(result.groups[2].lines[0].text, "Example line 1");
        assert.equal(result.groups[2].lines[1].type, "add");
        assert.equal(result.groups[2].lines[1].text, "Example line 2");
    });
});
