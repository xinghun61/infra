// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

"use strict";

function UserSettings()
{
    this.name = "";
    this.context = "";
    this.columnWidth = 0;
    this.tabSpaces = 0;
    this.notifyByChat = false;
    this.deprecatedUi = false;
    this.sendFromEmailAddr = true;
}

UserSettings.DETAIL_URL = "scrape/settings";

UserSettings.FIELD_NAME_MAP = {
    "deprecated_ui": "deprecatedUi",
    "nickname": "name",
    "notify_by_chat": "notifyByChat",
    "column_width": "columnWidth",
    "tab_spaces": "tabSpaces",
    "context": "context",
    "send_from_email_address": "sendFromEmailAddr",
};

UserSettings.prototype.loadDetails = function()
{
    var settings = this;
    return loadDocument(UserSettings.DETAIL_URL).then(function(doc) {
        settings.parseDocument(doc);
        return settings;
    });
};

UserSettings.prototype.parseDocument = function(doc)
{
    this.name = User.current.name;

    var context = doc.getElementById("id_context");
    if (context && context.selectedOptions && context.selectedOptions.length)
        this.context = context.selectedOptions[0].value;

    var columnWidth = doc.getElementById("id_column_width");
    if (columnWidth)
        this.columnWidth = parseInt(columnWidth.value, 10) || 0;

    var tabSpaces = doc.getElementById("id_tab_spaces");
    if (tabSpaces)
        this.tabSpaces = parseInt(tabSpaces.value, 10) || 0;

    var notifyByChat = doc.getElementById("id_notify_by_chat");
    if (notifyByChat)
        this.notifyByChat = notifyByChat.checked;

    var deprecatedUi = doc.getElementById("id_deprecated_ui");
    if (deprecatedUi)
        this.deprecatedUi = deprecatedUi.checked;

    var sendFromEmailAddr = doc.getElementById("id_send_from_email_addr");
    if (sendFromEmailAddr)
        this.sendFromEmailAddr = sendFromEmailAddr.checked;
};

UserSettings.prototype.save = function()
{
    var settings = this;
    return this.createSaveData().then(function(data) {
        return sendFormData(UserSettings.DETAIL_URL, data).then(function(xhr) {
            var errorData = parseFormErrorData(xhr.response);
            if (!errorData) {
                // Synchronize the user's name now that we've saved it to the server.
                return User.loadCurrentUser().then(function() {
                    return settings;
                });
            }
            var error = new Error(errorData.message);
            error.fieldName = UserSettings.FIELD_NAME_MAP[errorData.fieldName] || errorData.fieldName;
            throw error;
        });
    });
};

UserSettings.prototype.createSaveData = function()
{
    var settings = this;
    return User.loadCurrentUser().then(function(user) {
        return {
            nickname: settings.name,
            xsrf_token: user.xsrfToken,
            deprecated_ui: settings.deprecatedUi ? "on" : "",
            notify_by_chat: settings.notifyByChat ? "on" : "",
            notify_by_email: "on",
            column_width: settings.columnWidth,
            tab_spaces: settings.tabSpaces,
            context: settings.context,
            send_from_email_addr: settings.sendFromEmailAddr,
        };
    });
};
