// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

"use strict";

function User(name, email, displayName)
{
    this.name = name || "";
    this.email = email || "";
    this.openIssues = 0;
    this.reviewedIssues = 0;
    this.xsrfToken = "";
    this.displayName = displayName || this.email.split("@")[0] || this.name;
    this.isCurrentUser = User.current && this.name === User.current.name;
    Object.preventExtensions(this);
}

// TODO: Eventually we need to handle the case where the user is not signed in.
User.CURRENT_USER_URL = "/api/settings";
User.DETAIL_URL = "/scrape/user_popup/{1}";

User.EMAIL_PATTERN = /^([^@]+@[^ ]+) \((.+?)\)$/;
User.EMAIL_SUFFIX_PATTERN = /(\+[^@]+)?@.*/;
User.ISSUES_OPEN_PATTERN = /issues created: (\d+)/;
User.ISSUES_REVIEW_PATTERN = /issues reviewed: (\d+)/;
User.XSRF_TOKEN_PATTERN = /xsrfToken = '([^']+)';/;
User.LOGIN_REDIRECT_URL = "https://www.google.com/accounts/ServiceLogin?service=ah&passive=true&continue=https://appengine.google.com/_ah/conflogin%3Fcontinue%3D{1}&ltmpl=gm";
User.LOGOUT_REDIRECT_URL = "{1}/_ah/logout?continue=https://www.google.com/accounts/Logout%3Fcontinue%3Dhttps://appengine.google.com/_ah/logout%253Fcontinue%253D{2}";

User.current = null;
User.currentPromise = null;

(function() {
    // Take the user information provided by the server in the initial request
    // if it's available.
    if (window.INITIAL_USER_DATA) {
        var data = window.INITIAL_USER_DATA;
        User.current = new User(data.name, data.email, "me");
        User.current.isCurrentUser = true;
    }
})();

User.parseCurrentUser = function(data)
{
    if (!data)
        return null;
    var user = new User(data.nickname, data.email, "me");
    user.xsrfToken = data.xsrf_token;
    user.isCurrentUser = true;
    User.current = user;
    return user;
};

User.loadCurrentUser = function(options)
{
    if (User.currentPromise)
        return User.currentPromise;
    if (options && options.cached)
        return Promise.resolve(User.current);
    User.currentPromise = loadJSON(User.CURRENT_USER_URL).then(function(data) {
        return User.parseCurrentUser(data);
    }).either(function(e) {
        User.currentPromise = null;
    });
    return User.currentPromise;
};

User.getLoginUrl = function()
{
    return User.LOGIN_REDIRECT_URL.assign(encodeURIComponent(location.href));
};

User.getLogoutUrl = function()
{
    return User.LOGOUT_REDIRECT_URL.assign(
        location.origin,
        encodeURIComponent(location.href));
};

User.forName = function(name, email)
{
    if (User.current && (name === "me" || name === User.current.name))
        return User.current;
    return new User(name, email);
};

User.forMailingListEmail = function(email)
{
    // Lots of people use a + url for auto-cc lists, remove it since they
    // often use their normal user name just with the + part added.
    if (User.current && User.current.email === email)
        return User.current;
    var name = email.remove(User.EMAIL_SUFFIX_PATTERN);
    return new User(name, email, name);
};

User.compare = function(userA, userB)
{
    if (userA.displayName === "me")
        return -1;
    if (userB.displayName === "me")
        return 1;
    return userA.displayName.localeCompare(userB.displayName);
};

User.compareEmail = function(userA, userB)
{
    var result = userA.email.localeCompare(userB.email);
    if (!result)
        return User.compare(userA, userB);
    return result;
};

User.prototype.getDetailUrl = function()
{
    return User.DETAIL_URL.assign(encodeURIComponent(this.email || this.name));
};

User.prototype.loadDetails = function()
{
    var user = this;
    return loadText(this.getDetailUrl()).then(function(text) {
        user.parseDetail(text);
        return user;
    });
};

User.prototype.parseDetail = function(text)
{
    var match;

    match = User.EMAIL_PATTERN.exec(text);
    if (match) {
        this.email = match[1];
        this.name = match[2];
        this.displayName = this.email.split("@")[0] || this.name;
    }

    match = User.ISSUES_OPEN_PATTERN.exec(text);
    if (match)
        this.openIssues = Number(match[1]);

    match = User.ISSUES_REVIEW_PATTERN.exec(text);
    if (match)
        this.reviewedIssues = Number(match[1]);
};
