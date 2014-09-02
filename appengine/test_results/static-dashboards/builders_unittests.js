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

module('builders');

test('loading steps', 4, function() {
    var tests = {}
    var basePath = 'http://build.chromium.org/p/';
    var name = 'dummyname';
    var master = new builders.Master({name: name, url_name: name, tests: tests});

    var builderName = 'dummybuilder';
    var buildNumber = 12345;
    equal(master.logPath(builderName, buildNumber), basePath + name + '/builders/' + builderName + '/builds/' + buildNumber);
    equal(master.builderJsonPath(), basePath + name + '/json/builders');
    equal(master.tests, tests);
    equal(master.name, name);
});

test('builders.getBuilders', 4, function() {
    resetGlobals();

    var builderKeys = [];
    var allBuilders = builders.getBuilders('layout-tests');
    allBuilders.forEach(function(builder) {
        builderKeys.push(builder.key());
    });

    var expectedBuilderKey = new builders.Builder('chromium.webkit', 'WebKit Win').key();
    equal(builderKeys.indexOf(expectedBuilderKey) != -1, true, expectedBuilderKey + ' should be among the current builders');

    expectedBuilderKey = new builders.Builder('chromium.webkit', 'WebKit Linux').key();
    equal(builderKeys.indexOf(expectedBuilderKey) != -1, true, expectedBuilderKey + ' should be among the current builders');
    expectedBuilderKey = new builders.Builder('chromium.win', 'XP Tests (1)').key();
    equal(builderKeys.indexOf(expectedBuilderKey) != -1, false, expectedBuilderKey + ' should not be among the current builders');


    allBuilders = [];
    allBuilders = builders.getBuilders('ash_unittests');
    allBuilders.forEach(function(builder) {
        builderKeys.push(builder.key());
    });
    equal(builderKeys.indexOf(expectedBuilderKey) != -1, true, expectedBuilderKey + ' should be among the current builders');
});

test('builders.Builder.master', 1, function() {
    resetGlobals();

    var allBuilders = builders.getBuilders('unit_tests');
    equal(allBuilders[0].master().basePath, 'http://build.chromium.org/p/chromium.webkit');
});

test('builders.Buidler keys', 2, function() {
    resetGlobals();

    var builder = new builders.Builder('chromium.webkit', 'Blink Linux');
    currentBuilders().push(builder);
    equal(builder.key(), 'chromium.webkit:Blink Linux');
    equal(builders.builderFromKey('chromium.webkit:Blink Linux').key(), 'chromium.webkit:Blink Linux');
});

test('builders.Buidler names', 3, function() {
    resetGlobals();

    var builder = new builders.Builder('chromium.webkit', 'Blink Linux');
    equal(builder.builderName, 'Blink Linux');
    equal(builder.masterName, 'chromium.webkit');
    equal(builder.builderNameForPath(), 'Blink_Linux');
});

test('builders.Buidler duplicate names', 6, function() {
    resetGlobals();

    var masterA = new builders.Master({name: 'Master A', url_name: 'MasterA', tests: [], groups: []});
    var builder1 = new builders.Builder('MasterA', 'Builder');
    builders.masters['MasterA'] = masterA;
    currentBuilders().push(builder1);

    var masterB = new builders.Master({name: 'Master B', url_name: 'MasterB', tests: [], groups: []});
    var builder2 = new builders.Builder('MasterB', 'Builder');
    builders.masters['MasterB'] = masterB;
    currentBuilders().push(builder2);

    var masterP = new builders.Master({name: 'Master P', url_name: 'MasterP', tests: [], groups: []});
    var builder3 = new builders.Builder('MasterP', 'Builder');
    builders.masters['MasterP'] = masterP;
    currentBuilders().push(builder3);
    
    equal(builders.builderFromKey('MasterA:Builder').key(), 'MasterA:Builder');
    equal(builders.builderFromKey('MasterP:Builder').master().name, 'Master P');
    equal(builders.builderFromKey('MasterB:Builder').key(), 'MasterB:Builder');
    equal(builders.builderFromKey('MasterB:Builder').master().name, 'Master B');
    equal(builders.builderFromKey('MasterP:Builder').key(), 'MasterP:Builder');
    equal(builders.builderFromKey('MasterA:Builder').master().name, 'Master A');
});
