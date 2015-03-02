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
    this.sendFromEmailAddress = true;
    this.displayExperimentalTryjobs = false;
    Object.preventExtensions(this);
}

UserSettings.DETAIL_URL = "/api/settings";
UserSettings.EDIT_URL = "/settings";

UserSettings.FIELD_NAME_MAP = {
    "deprecated_ui": "deprecatedUi",
    "nickname": "name",
    "notify_by_chat": "notifyByChat",
    "column_width": "columnWidth",
    "tab_spaces": "tabSpaces",
    "context": "context",
    "send_from_email_address": "sendFromEmailAddress",
    "display_exp_tryjob_results": "displayExperimentalTryjobs",
};

UserSettings.prototype.loadDetails = function()
{
    var settings = this;
    return loadJSON(UserSettings.DETAIL_URL).then(function(data) {
        settings.parseData(data);
    });
};

UserSettings.prototype.parseData = function(data)
{
    this.name = User.current.name;

    this.context = data.default_context || "";
    this.columnWidth = data.default_column_width || 0;
    this.tabSpaces = data.default_tab_spaces || 0;
    this.notifyByChat = data.notify_by_chat;
    this.deprecatedUi = data.deprecated_ui;
    this.sendFromEmailAddress = data.send_from_email_addr;
    this.displayExperimentalTryjobs = data.display_exp_tryjob_results;
};

UserSettings.prototype.save = function()
{
    var settings = this;
    return sendFormData(UserSettings.EDIT_URL, {
        nickname: this.name,
        deprecated_ui: this.deprecatedUi ? "on" : "",
        notify_by_chat: this.notifyByChat ? "on" : "",
        notify_by_email: "on",
        column_width: this.columnWidth,
        tab_spaces: this.tabSpaces,
        context: this.context,
        send_from_email_addr: this.sendFromEmailAddress,
        display_exp_tryjob_results: this.displayExperimentalTryjobs,
    }, {
        sendXsrfToken: true,
    }).then(function(xhr) {
        var errorData = parseFormErrorData(xhr.response);
        if (errorData) {
            var error = new Error(errorData.message);
            error.fieldName = UserSettings.FIELD_NAME_MAP[errorData.fieldName] || errorData.fieldName;
            throw error;
        }
        // Synchronize the user's name now that we've saved it to the server.
        User.current.name = settings.name;
    });
};
