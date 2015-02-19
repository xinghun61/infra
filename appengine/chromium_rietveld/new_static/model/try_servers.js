// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

"use strict";

function TryServers()
{
    this.serversAndBuilders = [];
    this.buildersToServers = {};
    Object.preventExtensions(this);
}

TryServers.DETAIL_URL = "/api/tryservers";

TryServers.prototype.loadDetails = function()
{
    var tryservers = this;
    return loadJSON(TryServers.DETAIL_URL).then(function(data) {
        tryservers.parseData(data);
        return tryservers;
    });
}

TryServers.prototype.parseData = function(data)
{
    var serversAndBuilders = [];
    var buildersToServers = {};
    for (var i = 0; i < data.length; i++) {
        var tryserverData = data[i];
        var serverName = tryserverData.tryserver;
        var builders = tryserverData.builders;
        var builderNames = [];
        for (var j = 0; j < builders.length; j++) {
            var builder = builders[j].builder;
            buildersToServers[builder] = serverName;
            builderNames.push(builder);
        }
        serversAndBuilders.push({name: serverName, builders: builderNames});
    }

    this.serversAndBuilders = serversAndBuilders;
    this.buildersToServers = buildersToServers;
}

TryServers.prototype.createFlagValue = function(builders)
{
    var tryservers = this;
    return builders.map(function(builder) {
        return tryservers.buildersToServers[builder] + ":" + builder;
    }).join(",");
}
