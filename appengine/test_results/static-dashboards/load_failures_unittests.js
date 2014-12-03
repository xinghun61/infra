// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

module('loadfailures');

test('htmlForBuilder', 1, function() {
    var mockMaster = new builders.Master({name: 'MockMaster1', url_name: 'mock.master', tests: [], groups: []});
    builders.masters['mock.master'] = mockMaster;
    var builder = new builders.Builder('mock.master', 'Builder1');
    var html = loadfailures._htmlForBuilder(builder, 'layout-tests');

    equal(html, '<tr class="builder">' +
        '<td>mock.master:Builder1' +
        '<td><a href="http://test-results.appspot.com/testfile?testtype=layout-tests&builder=Builder1&master=mock.master">uploaded results</a>' +
        '<td><a href="http://build.chromium.org/p/mock.master/builders/Builder1">buildbot</a>' +
    '</tr>');
});

test('html', 4, function() {
    var mockMaster = new builders.Master({name: 'MockMaster', url_name: 'mock.master', tests: [], groups: []});
    builders.masters['mock.master'] = mockMaster;
    var builderFail = new builders.Builder('mock.master', 'BuilderFail');
    var builderStale = new builders.Builder('mock.master', 'BuilderStale');

    var failureData = {
        failingBuilders: {
            'MockTestType': [builderFail],
        },
        staleBuilders: {
            'MockTestType': [builderStale],
        },
        testTypesWithNoSuccessfullLoads: [ 'MockTestType' ],
    }

    var container = document.createElement('div');
    container.innerHTML = loadfailures._html(failureData);

    equal(container.querySelectorAll('.builder').length, 2, 'There should be 2 builders');

    var firstFailingBuilder = container.querySelector('table').querySelector('tr:nth-child(2) > td:nth-child(2)');
    equal(firstFailingBuilder.querySelector('b').innerHTML, 'No builders with up to date results.');
    equal(firstFailingBuilder.querySelectorAll('.builder').length, 1, 'There should be one failing builder in the first group.');

    var firstStaleBuilder = container.querySelector('table').querySelector('tr:nth-child(2) > td:nth-child(3)');
    equal(firstFailingBuilder.querySelectorAll('.builder').length, 1, 'There should be one stale builder in the first group.');
});

test('load failure', 3, function() {
    loadfailures._loader = new loader.Loader();
    loadfailures._loader._builderKeysThatFailedToLoad = ['FailMaster:FailBuilder'];
    loadfailures._testTypeIndex = builders.testTypes.length - 1; // Only load the last test.

    loadfailures._generatePage = function() {
        var failureData = loadfailures._failureData;
        var failingTestTypes = Object.keys(failureData.failingBuilders);
        equal(failingTestTypes.length, 1, 'There should be one failing test type.');
        var failingBuilders = failureData.failingBuilders[failingTestTypes[0]];
        equal(failingBuilders.length, 1, 'There should be one failing builder.');
        equal(failingBuilders[0].key(), 'FailMaster:FailBuilder');
    }

    loadfailures.loadNextTestType();
});
