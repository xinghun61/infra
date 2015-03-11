// Copyright (c) 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

"use strict";

describe("SyntaxHighlighter", function() {
    var assert = chai.assert;

    it("should highlight basic code", function() {
        var highlighter = new SyntaxHighlighter("cpp");
        assert.equal(highlighter.parseText("void main(const char* argv, int argc) {"), '<span class="hljs-keyword">void</span> main(<span class="hljs-keyword">const</span> <span class="hljs-keyword">char</span>* argv, <span class="hljs-keyword">int</span> argc) {');
        assert.equal(highlighter.parseText('return printf("%d arg count", argc);'), '<span class="hljs-keyword">return</span> <span class="hljs-built_in">printf</span>(<span class="hljs-string">"%d arg count"</span>, argc);');
        assert.equal(highlighter.parseText("}"), '}');
    });

    it("should return null when no language", function() {
        var highlighter = new SyntaxHighlighter("");
        assert.isNull(highlighter.parseText("void main(const char* argv, int argc) {"));
    });

    it("should highlight multi line comments", function() {
        var highlighter = new SyntaxHighlighter("javascript");
        assert.equal(highlighter.parseText("/*"), '<span class="hljs-comment">/*</span>');
        assert.equal(highlighter.parseText("still a comment"), '<span class="hljs-comment">still a comment</span>');
        assert.equal(highlighter.parseText("end */"), '<span class="hljs-comment">end */</span>');
        assert.equal(highlighter.parseText("not a comment"), 'not a comment');
    });

    it("should allow highlighter resetting", function() {
        var highlighter = new SyntaxHighlighter("javascript");
        assert.equal(highlighter.parseText("not a comment"), 'not a comment');
        assert.equal(highlighter.parseText("/*"), '<span class="hljs-comment">/*</span>');
        highlighter.resetSyntaxState();
        assert.equal(highlighter.parseText("not a comment"), 'not a comment');
    });

    it("should support embedded script", function() {
        var highlighter = new SyntaxHighlighter("html");
        assert.equal(highlighter.parseText('<script type="test">'), '<span class="hljs-tag">&lt;<span class="hljs-title">script</span> <span class="hljs-attribute">type</span>=<span class="hljs-value">"test"</span>&gt;</span><span class="javascript"></span>');
        assert.equal(highlighter.parseText('new F(); document'), '<span class="javascript"><span class="hljs-keyword">new</span> F(); <span class="hljs-built_in">document</span></span>');
        assert.equal(highlighter.parseText("</script>"), '<span class="javascript"></span><span class="hljs-tag">&lt;/<span class="hljs-title">script</span>&gt;</span>');
    });

    it("should support embedded style", function() {
        var highlighter = new SyntaxHighlighter("html");
        assert.equal(highlighter.parseText('<style type="test">'), '<span class="hljs-tag">&lt;<span class="hljs-title">style</span> <span class="hljs-attribute">type</span>=<span class="hljs-value">"test"</span>&gt;</span><span class="css"></span>');
        assert.equal(highlighter.parseText('.foo { color: "<style>"; }'), '<span class="css"><span class="hljs-class">.foo</span> <span class="hljs-rules">{ <span class="hljs-rule"><span class="hljs-attribute">color</span>:<span class="hljs-value"> <span class="hljs-string">"&lt;style&gt;"</span></span></span>; <span class="hljs-rule">}</span></span></span>');
        assert.equal(highlighter.parseText("</style>"), '<span class="css"></span><span class="hljs-tag">&lt;/<span class="hljs-title">style</span>&gt;</span>');
    });
});
