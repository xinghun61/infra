"use strict";

describe("User", function() {
    var assert = chai.assert;

    afterEach(function() {
        User.current = null;
    });

    it("should parse settings document into current user", function() {
        var html = ' \
            <!DOCTYPE html> \
            <html> \
                <head> \
                    <script type="text/javascript" async="" src="https://ssl.google-analytics.com/ga.js"></script> \
                </head> \
                <body> \
                <script type="text/javascript"><!-- \
                    var xsrfToken = \'cb66768b2ff3144abc700e12d88911e5\'; \
                    var helpDisplayed = false; \
                    document.onclick = M_clickCommon; \
                    var media_url = "/static/"; \
                    var base_url = "/"; \
                // --> \
                </script>\
                <div align=right> \
                <b>esprehn@test.org (esprehn (oo in dc))</b> \
        ';

        var doc = document.implementation.createHTMLDocument();
        doc.open();
        doc.write(html);
        doc.close();

        var user = User.parseCurrentUser(doc);
        assert.equal(user.email, "esprehn@test.org");
        assert.equal(user.name, "esprehn (oo in dc)");
        assert.equal(user.xsrfToken, "cb66768b2ff3144abc700e12d88911e5");
    });
});
