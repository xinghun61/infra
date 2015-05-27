// Copyright (c) 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

"use strict";


function IntralineDiffSide(tagName)
{
    this.startTag = "<" + tagName + ">";
    this.endTag = "</" + tagName + ">";
    // list of {start: int, end: int} ranges of source chars.
    this.ranges = [];
    // Current character position in the group source text.
    this.position = 0;
    Object.preventExtensions(this);
};

IntralineDiffSide.prototype.reset = function()
{
    this.ranges = [];
    this.position = 0;
};

IntralineDiffSide.prototype.isWholeLine = function(src)
{
    var range = this.ranges[0];
    // Check end >= pos + len so that we count a change to all the
    // text on a line as a whole line, regardless of the \n.
    return (range.start <= this.position &&
            range.end >= this.position + src.length);
};

IntralineDiffSide.prototype.insertTags = function(src, html)
{
    var parts = [];
    var localRanges = this.makeLocalRangesForCurrentLine(src.length);
    var srcIndex = 0;  // Logical char index of src characers in the html string.
    var htmlIndex = 0;  // Primitive char index in html string.
    for (var i = 0; i < localRanges.length; ++i) {
        var range = localRanges[i];
        // Output the part of the line that is before the range.
        var sliceAndIndex = this.slice(html, srcIndex, range.start);
        parts.push(sliceAndIndex.text);
        htmlIndex = sliceAndIndex.index;
        srcIndex = range.start;
        // Output a modified range
        parts.push(this.startTag);
        sliceAndIndex = this.slice(html, range.start, range.end);
        parts.push(this.insertTagsInsideRange(sliceAndIndex.text));
        htmlIndex = sliceAndIndex.index;
        srcIndex = range.end;
        parts.push(this.endTag);
    }
    // Output any part of the html that is after the last range on this line
    parts.push(html.slice(htmlIndex));
    return parts.join("");
};

IntralineDiffSide.prototype.processLine = function(div, src, html) {
    if (!this.ranges.length)
        return html;
    if (this.isWholeLine(src))
        div.classList.add("whole-line");
    else
        html = this.insertTags(src, html);
    this.position += src.length;
    this.position++;  // For the newline char.
    return html;
};

IntralineDiffSide.prototype.makeLocalRangesForCurrentLine = function(sourceLength)
{
    // Discard any ranges that we have already passed.
    var index = 0;
    while (index < this.ranges.length && this.ranges[index].end <= this.position)
        ++index;
    this.ranges = this.ranges.from(index);

    var endOfLinePosition = this.position + sourceLength + 1;
    var localRanges = [];
    for (var i = 0; i < this.ranges.length; ++i) {
        var range = this.ranges[i];
        if (range.start > endOfLinePosition)
            return localRanges;
        var localRange = {
            start: Math.max(range.start - this.position, 0),
            end: Math.min(range.end - this.position, endOfLinePosition)
        };
        localRanges.push(localRange);
    }
    return localRanges;
};

IntralineDiffSide.prototype.insertTagsInsideRange = function(html)
{
    return html.replace(/<[^>]+>/g, this.endTag + "$&" + this.startTag);
};

// sourceStart and sourceEnd are source character indexes, whereas
// startIndex and endIndex are primitive chatacter indexes in the HTML.
// E.g., if the source code was "a && b", the logical-and operator would
// be in a range of source characters (2, 4), whereas the HTML would be
// "a &amp;&amp; b" and the startIndex and endIndex would be 2 and 12.
IntralineDiffSide.prototype.slice = function(html, sourceStart, sourceEnd)
{
    var startIndex = 0;
    for (var i = 0; i < sourceStart; ++i)
        startIndex = this.advanceChar(html, startIndex);
    var endIndex = startIndex; 
    for (var i = sourceStart; i < sourceEnd; ++i)
        endIndex = this.advanceChar(html, endIndex);
    
    return {
        text: html.slice(startIndex, endIndex),
        index: endIndex,
    };
};


IntralineDiffSide.LESS_THAN_CODE = "<".charCodeAt(0);
IntralineDiffSide.GREATER_THAN_CODE = ">".charCodeAt(0);
IntralineDiffSide.AMPERSAND_CODE = "&".charCodeAt(0);
IntralineDiffSide.SEMICOLON_CODE = ";".charCodeAt(0);

IntralineDiffSide.prototype.advanceChar = function(html, index)
{
    // Any tags don't count as characters
    while (index < html.length && html.charCodeAt(index) == IntralineDiffSide.LESS_THAN_CODE) {
        while (index < html.length && html.charCodeAt(index) != IntralineDiffSide.GREATER_THAN_CODE)
            index++;
        index++;  // skip the ">" itself
    }
    // An HTML entity (e.g., &lt;) counts as one char
    if (index < html.length && html.charCodeAt(index) == IntralineDiffSide.AMPERSAND_CODE) {
        while (index < html.length && html.charCodeAt(index) != IntralineDiffSide.SEMICOLON_CODE)
            index++;
    }
    return index + 1;
};

