"use strict";

describe("PatchFile", function() {
    var assert = chai.assert;

    it("should parse file extensions into syntax highlighting languages", function() {
        assert.equal(new PatchFile(null, "").language, "");
        assert.equal(new PatchFile(null, "Document.h").language, "cpp");
        assert.equal(new PatchFile(null, "Document.cpp").language, "cpp");
        assert.equal(new PatchFile(null, "path/test.html").language, "html");
        assert.equal(new PatchFile(null, "dir/test.xhtml").language, "html");
        assert.equal(new PatchFile(null, "example.js").language, "javascript");
        assert.equal(new PatchFile(null, "this_is.file.css").language, "css");
        assert.equal(new PatchFile(null, "image.xml").language, "xml");
        assert.equal(new PatchFile(null, "image.svg").language, "xml");
        assert.equal(new PatchFile(null, "horror.pl").language, "perl");
        assert.equal(new PatchFile(null, "horror2.pm").language, "perl");
        assert.equal(new PatchFile(null, "//./.py/horror1.cgi").language, "perl");
        assert.equal(new PatchFile(null, "snakesonaplane.py").language, "python");
        assert.equal(new PatchFile(null, "gems.rb").language, "ruby");
        assert.equal(new PatchFile(null, "cocoa.mm").language, "objectivec");
        assert.equal(new PatchFile(null, "../.file/data.json").language, "json");
        assert.equal(new PatchFile(null, "Document.idl").language, "actionscript");
        assert.equal(new PatchFile(null, "Document.map").language, "");
        assert.equal(new PatchFile(null, "Document.h.").language, "");
        assert.equal(new PatchFile(null, "Document.cpp/").language, "");
        assert.equal(new PatchFile(null, "prefetch_messages.cc").language, "cpp");
    });
    it("should handle embedded language selection", function() {
        var html = new PatchFile(null, "example.html");
        assert.equal(html.selectEmbeddedLanguage("<script type=\"foo\"></script>"), "html");
        assert.equal(html.selectEmbeddedLanguage("<script></script>"), "html");
        assert.equal(html.selectEmbeddedLanguage("<script>function() { return 1/script>2; }</script>"), "html");
        assert.equal(html.selectEmbeddedLanguage("<script>"), "javascript");
        assert.equal(html.selectEmbeddedLanguage("<script type=\"foo\">"), "javascript");
        assert.equal(html.selectEmbeddedLanguage("</script>"), "html");
        assert.equal(html.selectEmbeddedLanguage("<style>"), "css");
        assert.equal(html.selectEmbeddedLanguage("<style type=example>"), "css");
        assert.equal(html.selectEmbeddedLanguage("<style type=example>.foo { }</style>"), "html");
        assert.equal(html.selectEmbeddedLanguage("<style type=example></style>"), "html");
        var text = new PatchFile(null, "example.cpp");
        assert.equal(text.selectEmbeddedLanguage("<script></script>"), "cpp");
        assert.equal(text.selectEmbeddedLanguage("<style></style>"), "cpp");
    });
    it("should maintain message counts", function() {
        var issue = new Issue(1);
        var file = new PatchFile(new PatchSet(issue, 2));

        assert.equal(file.messageCount, 0);
        assert.equal(file.draftCount, 0);

        var message = new PatchFileMessage();
        message.line = 10;
        file.addMessage(message);
        assert.deepEqual(file.messages[10], [message]);
        assert.equal(file.messageCount, 1);
        assert.equal(file.draftCount, 0);

        var draft = new PatchFileMessage();
        draft.line = 10;
        draft.draft = true;
        file.addMessage(draft);
        assert.deepEqual(file.messages[10], [message, draft]);
        assert.equal(file.messageCount, 2);
        assert.equal(file.draftCount, 1);
        assert.equal(issue.draftCount, 1);

        file.removeMessage(message);
        assert.deepEqual(file.messages[10], [draft]);
        assert.equal(file.messageCount, 1);
        assert.equal(file.draftCount, 1);
        assert.equal(issue.draftCount, 1);

        file.removeMessage(draft);
        assert.lengthOf(file.messages[10], 0);
        assert.equal(file.messageCount, 0);
        assert.equal(file.draftCount, 0);
        assert.equal(issue.draftCount, 0);
    });
    it("should only parse positive or zero delta numbers", function() {
        var file = new PatchFile();

        assert.equal(file.added, 0);
        assert.equal(file.removed, 0);

        file.added = 10;
        file.removed = 5;
        assert.equal(file.added, 10);
        assert.equal(file.removed, 5);

        file.parseData({
                num_added: -1,
                num_removed: -10,
        });
        assert.equal(file.added, 0);
        assert.equal(file.removed, 0);

        file.parseData({
                num_added: 8,
                num_removed: 4,
        });
        assert.equal(file.added, 8);
        assert.equal(file.removed, 4);
    });
});
