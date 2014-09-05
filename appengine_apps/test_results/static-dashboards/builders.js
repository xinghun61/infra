// Copyright (C) 2012 Google Inc. All rights reserved.
//
// Redistribution and use in source and binary forms, with or without
// modification, are permitted provided that the following conditions are
// met:
//
//    * Redistributions of source code must retain the above copyright
// notice, this list of conditions and the following disclaimer.
//    * Redistributions in binary form must reproduce the above
// copyright notice, this list of conditions and the following disclaimer
// in the documentation and/or other materials provided with the
// distribution.
//    * Neither the name of Google Inc. nor the names of its
// contributors may be used to endorse or promote products derived from
// this software without specific prior written permission.
//
// THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
// "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
// LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
// A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
// OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
// SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
// LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
// DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
// THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
// (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
// OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

function LOAD_BUILDBOT_DATA(builderData)
{
    builders.masters = {};
    var testTypes = {};
    var testTypesThatDoNotUpload = {};
    builders.noUploadTestTypes = builderData['no_upload_test_types'];
    builders.testTypeToBuilder = {};

    builderData['masters'].forEach(function(master) {
        builders.masters[master.url_name] = new builders.Master(master);
        Object.keys(master.tests).forEach(function(testType) {
            if (!master.builderNames)
                master.builderNames = {};
            var builderNames = master.tests[testType].builders;
            builderNames.forEach(function(builderName) {
                master.builderNames[builderName] = true;
                if (!builders.testTypeToBuilder[testType])
                    builders.testTypeToBuilder[testType] = [];
                builders.testTypeToBuilder[testType].push(new builders.Builder(master.url_name, builderName));
            });

            if (builders.testTypeUploadsToFlakinessDashboardServer(testType))
                testTypes[testType] = true;
            else
                testTypesThatDoNotUpload[testType] = true;
        });
    });
    builders.testTypes = Object.keys(testTypes);
    builders.testTypes.sort();
    // FIXME: Expose this in the flakiness dashboard UI and give a clear error message
    // pointing to a bug about getting the test type in question uploading results.
    builders.testTypesThatDoNotUpload = Object.keys(testTypesThatDoNotUpload);
    builders.testTypesThatDoNotUpload.sort();
}

var builders = builders || {};

(function() {

builders.testTypeUploadsToFlakinessDashboardServer = function(testType)
{
    for (var i = 0; i < builders.noUploadTestTypes.length; i++) {
        if (string.contains(testType, builders.noUploadTestTypes[i]))
            return false;
    }
    return true;
}

builders.getBuilders = function(testType)
{
    var currentBuilders = builders.testTypeToBuilder[testType];
    if (!currentBuilders)
        console.error('No master and builder found for ' + testType);
    return currentBuilders;
}

builders.Builder = function(masterName, builderName)
{
    this.masterName = masterName;
    this.builderName = builderName;
}

builders.Builder.prototype = {
    key: function() {
        return this.masterName + ':' + this.builderName;
    },
    master: function() {
        if (!builders.masters[this.masterName])
            console.error('Master not found for ' + this.key());
        return builders.masters[this.masterName];
    },
    builderNameForPath: function() {
        var name = this.builderName;
        return name.replace(/[ .()]/g, '_');
    }
}

builders.builderFromKey = function(builderKey)
{
    if (!builderKey)
        return undefined;

    var masterNameAndBuilderName = builderKey.split(':');
    if (!masterNameAndBuilderName.length) {
        console.error('Builder not found for ' + builderKey);
        return undefined;
    }

    var masterName = masterNameAndBuilderName[0];
    if (!builders.masters[masterName])
        console.error('Master "' + masterName + '" not found');
    return new builders.Builder(masterName, masterNameAndBuilderName[1]);
}

builders.Master = function(master_data)
{
    this.name = master_data.name;
    this.basePath = 'http://build.chromium.org/p/' + master_data.url_name;
    this.tests = master_data.tests;
}

builders.Master.prototype = {
    logPath: function(builder, buildNumber)
    {
        return this.builderPath(builder) + '/builds/' + buildNumber;
    },
    builderPath: function(builder)
    {
        return this.basePath + '/builders/' + builder;
    },
    builderJsonPath: function()
    {
        return this.basePath + '/json/builders';
    },
}

})();
