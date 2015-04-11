"use strict";

describe("Search", function() {
    var assert = chai.assert;

    it("should encode url parameters", function() {
        loadText.expect("/account?limit=10&q=sp%20%3Are", function() {
            return Promise.resolve("");
        });
        return Search.findUsers("sp :re", "not a number");
    });
    it("should pass a default limit", function() {
        loadText.expect("/account?limit=10&q=esprehn", function() {
            return Promise.resolve("");
        });
        return Search.findUsers("esprehn");
    });
    it("should sort users by email", function() {
        loadText.expect("/account?limit=10&q=ojan", function() {
            return Promise.resolve("ojan@chromium.org (Ojan)\nesprehn@chromium.org (Elliott)");
        });
        return Search.findUsers("ojan", 10).then(function(users) {
            assert.deepEqual(users, [
                new User("Elliott", "esprehn@chromium.org", "esprehn"),
                new User("Ojan", "ojan@chromium.org", "ojan"),
            ]);
        });
    });
    it("should search for issues", function() {
        loadJSON.expect("/search?format=json&closed=0&owner=esprehn%40chromium.org&reviewer=&cc=&order=&limit=10&cursor=", function() {
            return Promise.resolve({
                results: [{
                    issue: 10,
                }, {
                    issue: 20,
                }],
                cursor: "__cursor__",
            });
        });
        var query = {
            owner: "esprehn@chromium.org",
        };
        return Search.findIssues(query).then(function(result) {
            assert.lengthOf(result.issues, 2);
            assert.equal(result.issues[0].id, 10);
            assert.equal(result.issues[1].id, 20);
            assert.equal(result.query.cursor, "__cursor__");
            assert.equal(result.query.owner, "esprehn@chromium.org");
        });
    });
    it("should search for issues", function() {
        loadJSON.expect("/search?format=json&closed=0&owner=esprehn%40chromium.org&reviewer=&cc=&order=&limit=10&cursor=", function() {
            return Promise.resolve({
                results: [{
                    issue: 10,
                }],
                cursor: "a_cursor",
            });
        });
        loadJSON.expect("/search?format=json&closed=0&owner=esprehn%40chromium.org&reviewer=&cc=&order=&limit=10&cursor=a_cursor", function() {
            return Promise.resolve({
                results: [{
                    issue: 30,
                }],
                cursor: "b_cursor",
            });
        });
        var query = {
            owner: "esprehn@chromium.org",
        };
        return Search.findIssues(query).then(function(resultA) {
            resultA.findNext().then(function(resultB) {
                assert.lengthOf(resultB.issues, 1);
                assert.equal(resultB.issues[0].id, 30);
                assert.equal(resultB.query.cursor, "b_cursor");
                assert.equal(resultB.query.owner, "esprehn@chromium.org");
            });
        });
    });
});
