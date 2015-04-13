// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

"use strict";

function loadResource(type, url)
{
    return new Promise(function(fulfill, reject) {
        var xhr = new XMLHttpRequest();
        xhr.open("GET", url);
        xhr.responseType = type;
        xhr.send();
        xhr.onload = function() {
            fulfill(xhr);
        };
        xhr.onerror = function() {
            reject(xhr);
        };
    });
}

function loadText(url)
{
    return loadResource("text", url).then(function(xhr) {
        return xhr.responseText;
    });
}

function loadDocument(url)
{
    return loadResource("document", url).then(function(xhr) {
        if (!xhr.responseXML)
            throw new Error("Not found");
        return xhr.responseXML;
    });
}

function loadJSON(url)
{
    return loadResource("json", url).then(function(xhr) {
        if (!xhr.response)
            throw new Error("Not found");
        return xhr.response;
    });
}

function sendFormData(url, data, options)
{
    // Clone data before the async request so callers can reuse it if needed.
    options = Object.clone(options) || {};
    data = Object.clone(data) || {};

    function sendInternal() {
        return new Promise(function(fulfill, reject) {
            var formData = Object.keys(data).map(function(key) {
                return key + "=" + encodeURIComponent(data[key]);
            }).join("&");

            var xhr = new XMLHttpRequest();
            xhr.open("POST", url);
            xhr.responseType = options.responseType || "document";
            xhr.setRequestHeader("Content-Type","application/x-www-form-urlencoded");
            Object.keys(options.headers || {}, function(name, value) {
                xhr.setRequestHeader(name, value);
            });

            xhr.send(formData);
            xhr.onload = function() {
                fulfill(xhr);
            };
            xhr.onerror = function() {
                reject(xhr);
            };
        });
    }
    if (!options.sendXsrfToken)
        return sendInternal();
    return User.loadCurrentUser().then(function(user) {
        data.xsrf_token = user.xsrfToken;
        return sendInternal();
    });
}

function parseFormErrorData(doc)
{
    var li = doc.querySelector(".errorlist li");
    if (!li)
        return null;
    var input = li.parentNode.parentNode.querySelector("input");
    if (!input)
        return null;
    return {
        message: li.textContent,
        fieldName: input.name,
    };
}
