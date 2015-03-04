"use strict";

describe("User", function() {
    var assert = chai.assert;

    afterEach(function() {
        User.current = null;
    });

    it("should parse settings JSON into current user", function() {
       var data = {
	   email: 'esprehn@test.org',
	   nickname: 'esprehn (oo in dc)',
	   xsrf_token: 'cb66768b2ff3144abc700e12d88911e5',
       };

        var user = User.parseCurrentUser(data);
        assert.equal(user.email, "esprehn@test.org");
        assert.equal(user.name, "esprehn (oo in dc)");
        assert.equal(user.xsrfToken, "cb66768b2ff3144abc700e12d88911e5");
    });
});
