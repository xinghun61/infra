// Copyright (c) 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

"use strict";

describe("SyntaxHighlighter", function() {
    it("should highlight basic code", function() {
        var highlighter = new SyntaxHighlighter("cpp", false);
        expect(highlighter.parseText("void main(const char* argv, int argc) {")).toBe('<span class="hljs-keyword">void</span> main(<span class="hljs-keyword">const</span> <span class="hljs-keyword">char</span>* argv, <span class="hljs-keyword">int</span> argc) {');
        expect(highlighter.parseText('return printf("%d arg count", argc);')).toBe('<span class="hljs-keyword">return</span> <span class="hljs-built_in">printf</span>(<span class="hljs-string">"%d arg count"</span>, argc);');
        expect(highlighter.parseText("}")).toBe('}');
    });

    it("should return null when no language", function() {
        var highlighter = new SyntaxHighlighter("", false);
        expect(highlighter.parseText("void main(const char* argv, int argc) {")).toBe(null);
    });

    it("should highlight multi line comments", function() {
        var highlighter = new SyntaxHighlighter("javascript", false);
        expect(highlighter.parseText("/*")).toBe('<span class="hljs-comment">/*</span>');
        expect(highlighter.parseText("still a comment")).toBe('<span class="hljs-comment">still a comment</span>');
        expect(highlighter.parseText("end */")).toBe('<span class="hljs-comment">end */</span>');
        expect(highlighter.parseText("not a comment")).toBe('not a comment');
    });

    it("should allow highlighter resetting", function() {
        var highlighter = new SyntaxHighlighter("javascript", false);
        expect(highlighter.parseText("not a comment")).toBe('not a comment');
        expect(highlighter.parseText("/*")).toBe('<span class="hljs-comment">/*</span>');
        highlighter.resetSyntaxState();
        expect(highlighter.parseText("not a comment")).toBe('not a comment');
    });

    it("should support embedded script", function() {
        var highlighter = new SyntaxHighlighter("html", true);
        expect(highlighter.parseText('<script type="test">')).toBe('<span class="hljs-tag">&lt;<span class="hljs-title">script</span> <span class="hljs-attribute">type</span>=<span class="hljs-value">"test"</span>&gt;</span><span class="javascript"></span>');
        expect(highlighter.parseText('new F(); document')).toBe('<span class="hljs-keyword">new</span> F(); <span class="hljs-built_in">document</span>');
        expect(highlighter.parseText("</script>")).toBe('<span class="hljs-tag">&lt;/<span class="hljs-title">script</span>&gt;</span>');
    });

    it("should support embedded style", function() {
        var highlighter = new SyntaxHighlighter("html", true);
        expect(highlighter.parseText('<style type="test">')).toBe('<span class="hljs-tag">&lt;<span class="hljs-title">style</span> <span class="hljs-attribute">type</span>=<span class="hljs-value">"test"</span>&gt;</span><span class="css"></span>');
        expect(highlighter.parseText('.foo { color: "<style>"; }')).toBe('<span class="hljs-class">.foo</span> <span class="hljs-rules">{ <span class="hljs-rule"><span class="hljs-attribute">color</span>:<span class="hljs-value"> <span class="hljs-string">"&lt;style&gt;"</span></span></span>; <span class="hljs-rule">}</span></span>');
        expect(highlighter.parseText("</style>")).toBe('<span class="hljs-tag">&lt;/<span class="hljs-title">style</span>&gt;</span>');
    });
});
