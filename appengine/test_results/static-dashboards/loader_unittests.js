// Copyright (C) Zan Dobersek <zandobersek@gmail.com>
//
// Redistribution and use in source and binary forms, with or without
// modification, are permitted provided that the following conditions are
// met:
//
//         * Redistributions of source code must retain the above copyright
// notice, this list of conditions and the following disclaimer.
//         * Redistributions in binary form must reproduce the above
// copyright notice, this list of conditions and the following disclaimer
// in the documentation and/or other materials provided with the
// distribution.
//         * Neither the name of Google Inc. nor the names of its
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

module('loader');

test('loading steps', 1, function() {
    resetGlobals();
    var loadedSteps = [];
    g_history._handleLocationChange = function() {
        deepEqual(loadedSteps, ['step 1', 'step 2']);
    }
    var resourceLoader = new loader.Loader();
    function loadingStep1() {
        loadedSteps.push('step 1');
        resourceLoader.load();
    }
    function loadingStep2() {
        loadedSteps.push('step 2');
        resourceLoader.load();
    }

    resourceLoader._loadingSteps = [loadingStep1, loadingStep2];
    resourceLoader.load();
});

// Total number of assertions is 1 for the deepEqual of the builder lists
// and then 2 per builder (one for ok, one for deepEqual of tests).
test('results files loading', 13, function() {
    resetGlobals();

    var expectedLoadedBuilderKeys =  ['chromium.webkit:WebKit Linux', 'chromium.webkit:WebKit Linux (dbg)', 'chromium.webkit:WebKit Linux (deps)', 'chromium.webkit:WebKit Mac10.7', 'chromium.webkit:WebKit Win', 'chromium.webkit:WebKit Win (dbg)'];
    var loadedBuilderKeys = [];
    var resourceLoader = new loader.Loader();
    resourceLoader._loadNext = function() {
        deepEqual(loadedBuilderKeys.sort(), expectedLoadedBuilderKeys);
        loadedBuilderKeys.forEach(function(builderKey) {
            ok('secondsSinceEpoch' in g_resultsByBuilder[builderKey]);
            deepEqual(g_resultsByBuilder[builderKey].tests, {});
        });
    }

    var requestFunction = loader.request;
    loader.request = function(url, successCallback, errorCallback) {
        var masterName = 'chromium.webkit';
        var builderName = /builder=([\w ().]+)&/.exec(url)[1];
        loadedBuilderKeys.push(masterName + ':' + builderName);
        successCallback({responseText: '{"version":4,"' + builderName + '":{"failure_map":{"A":"AUDIO","C":"CRASH","F":"TEXT"},"secondsSinceEpoch":[' + Date.now() + '],"tests":{}}}'});
    }

    resourceLoader._builders = builders.getBuilders('layout-tests');

    try {
        resourceLoader._loadResultsFiles();
    } finally {
        loader.request = requestFunction;
    }
});

test('results file failing to load', 2, function() {
    resetGlobals();

    var resourceLoader = new loader.Loader();
    resourceLoader._builders = builders.getBuilders('layout-tests');
    var resourceLoadCount = 0;
    resourceLoader._handleResourceLoad = function() {
        resourceLoadCount++;
    }

    var builder1 = new builders.Builder('DummyMaster1', 'DummyBuilder1');
    resourceLoader._builders.push(builder1);
    resourceLoader._handleResultsFileLoadError(builder1);

    var builder2 = new builders.Builder('DummyMaster2', 'DummyBuilder2');
    resourceLoader._builders.push(builder2);
    resourceLoader._handleResultsFileLoadError(builder2);

    deepEqual(resourceLoader.builderKeysThatFailedToLoad(), [builder1.key(), builder2.key()]);
    equal(resourceLoadCount, 2);
});

test('Default builder gets set.', 3, function() {
    resetGlobals();

    // Simulate error loading the default builder data, then make sure
    // a new defaultBuilder is set, and isn't the now invalid one.
    var resourceLoader = new loader.Loader();
    resourceLoader._builders = builders.getBuilders('layout-tests');

    var firstBuilder = resourceLoader._builders[0];
    ok(firstBuilder, "Default builder should exist.");

    resourceLoader._handleResultsFileLoadError(resourceLoader._builders[0]);
    var newDefaultBuilder = resourceLoader._builders[0];
    ok(newDefaultBuilder, "There should still be a default builder.");
    notEqual(newDefaultBuilder.key(), firstBuilder.key(), "Default builder should not be the old default builder");
});

test('addBuilderLoadErrors', 1, function() {
    var resourceLoader = new loader.Loader();
    resourceLoader._builderKeysThatFailedToLoad = ['FailMaster1:FailBuilder1', 'FailMaster2:FailBuilder2'];
    resourceLoader._staleBuilderKeys = ['StaleMaster:StaleBuilder'];
    resourceLoader._addErrors();
    equal(resourceLoader._errors._messages, 'ERROR: Failed to get data from FailMaster1:FailBuilder1,FailMaster2:FailBuilder2.<br>ERROR: Data from StaleMaster:StaleBuilder is more than 1 day stale.<br>');
});

test('flattenTrie', 1, function() {
    resetGlobals();
    var tests = {
        'bar.html': {'results': [[100, 'F']], 'times': [[100, 0]]},
        'foo': {
            'bar': {
                'baz.html': {'results': [[100, 'F']], 'times': [[100, 0]]},
            }
        }
    };
    var expectedFlattenedTests = {
        'bar.html': {'results': [[100, 'F']], 'times': [[100, 0]]},
        'foo/bar/baz.html': {'results': [[100, 'F']], 'times': [[100, 0]]},
    };
    equal(JSON.stringify(loader.Loader._flattenTrie(tests)), JSON.stringify(expectedFlattenedTests))
});
