// Copyright (C) 2012 Google Inc. All rights reserved.
// Copyright (C) 2012 Zan Dobersek <zandobersek@gmail.com>
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

var loader = loader || {};

(function() {

// Avoid protocol-relative URL to avoid upsetting file:// URLs more than
// necessary.
var TEST_RESULTS_PROTOCOL = (location.protocol == 'https:') ? 'https:' : 'http:';
var TEST_RESULTS_SERVER = TEST_RESULTS_PROTOCOL + '//test-results.appspot.com/';

function pathToResultsFile(testType, builder) {
    return TEST_RESULTS_SERVER + 'testfile?builder=' + builder.builderName +
           '&master=' + builder.masterName +
           '&testtype=' + testType + '&name=';
}

loader.request = function(url, success, error, opt_isBinaryData)
{
    var xhr = new XMLHttpRequest();
    xhr.open('GET', url, true);
    if (opt_isBinaryData)
        xhr.overrideMimeType('text/plain; charset=x-user-defined');
    xhr.onreadystatechange = function(e) {
        if (xhr.readyState == 4) {
            if (xhr.status == 200)
                success(xhr);
            else
                error(xhr);
        }
    }
    xhr.send();
}

loader.Loader = function()
{
    this._builderKeysThatFailedToLoad = [];
    this._staleBuilderKeys = [];
    this._errors = new ui.Errors();
    // TODO(jparent): Pass in the appropriate history obj per db.
    this._history = g_history;
    this._builders = [];
}

// TODO(aboxhall): figure out whether this is a performance bottleneck and
// change calling code to understand the trie structure instead if necessary.
loader.Loader._flattenTrie = function(trie, prefix)
{
    var result = {};
    for (var name in trie) {
        var fullName = prefix ? prefix + "/" + name : name;
        var data = trie[name];
        if ("results" in data)
            result[fullName] = data;
        else {
            var partialResult = loader.Loader._flattenTrie(data, fullName);
            for (var key in partialResult) {
                result[key] = partialResult[key];
            }
        }
    }
    return result;
}

loader.Loader.prototype = {
    load: function()
    {
        this._testType = this._history.crossDashboardState.testType;
        this._builders = builders.getBuilders(this._testType);
        // TODO(sergiyb): Remove this when all layout tests are using swarming (crbug.com/524758).
        if (this._testType == "webkit_layout_tests")
          this._extraBuilders = builders.getBuilders("webkit_tests");
        if (this._testType == "webkit_tests")
          this._extraBuilders = builders.getBuilders("webkit_layout_tests");
        this._loadResultsFiles();
    },
    showErrors: function()
    {
        this._errors.show();
    },
    builderKeysThatFailedToLoad: function() {
        return this._builderKeysThatFailedToLoad;
    },
    staleBuilderKeys: function() {
        return this._staleBuilderKeys;
    },
    _loadResultsFiles: function()
    {
        if (this._builders && this._builders.length) {
            this._builders.forEach(this._loadResultsFile.bind(this, this._testType));
            // TODO(sergiyb): Remove this when all layout tests are using swarming (crbug.com/524758).
            if (this._testType == "webkit_layout_tests")
              this._extraBuilders.forEach(this._loadResultsFile.bind(this, "webkit_tests"));
            if (this._testType == "webkit_tests")
              this._extraBuilders.forEach(this._loadResultsFile.bind(this, "webkit_layout_tests"));
        } else {
            this._completeLoading();
        }
    },
    _loadResultsFile: function(testType, builder)
    {
        var resultsFilename;
        // FIXME: times_ms.json should store the actual buildnumber and
        // this should be changed to buildnumber=latest, which doesn't work.
        if (this._history.crossDashboardState.showAllRuns)
            resultsFilename = 'results.json';
        else
            resultsFilename = 'results-small.json';

        var resultsFileLocation = pathToResultsFile(testType, builder) + resultsFilename;
        loader.request(resultsFileLocation,
                partial(function(loader, builder, xhr) {
                    loader._handleResultsFileLoaded(builder, xhr.responseText);
                }, this, builder),
                partial(function(loader, builder, xhr) {
                    loader._handleResultsFileLoadError(builder);
                }, this, builder));
    },
    _handleResultsFileLoaded: function(builder, fileData)
    {
        this._processResultsJSONData(builder, fileData);

        // We need this work-around for webkit.org/b/50589.
        if (!g_resultsByBuilder[builder.key()]) {
            this._handleResultsFileLoadError(builder);
            return;
        }

        this._handleResourceLoad();
    },
    _processResultsJSONData: function(builder, fileData)
    {
        try {
            var builds = JSON.parse(fileData);
        } catch (e) {
            console.error(e);
            return;
        }

        if (builder.builderName == 'version' || builder.builderName == 'failure_map')
             return;

        var ONE_DAY_SECONDS = 60 * 60 * 24;
        var ONE_WEEK_SECONDS = ONE_DAY_SECONDS * 7;

        // If a test suite stops being run on a given builder, we don't want to show it.
        // Assume any builder without a run in two weeks for a given test suite isn't
        // running that suite anymore.
        // FIXME: Grab which bots run which tests directly from the buildbot JSON instead.
        var lastRunSeconds = builds[builder.builderName].secondsSinceEpoch[0];
        if ((Date.now() / 1000) - lastRunSeconds > ONE_WEEK_SECONDS)
            return;

        if ((Date.now() / 1000) - lastRunSeconds > ONE_DAY_SECONDS)
            this._staleBuilderKeys.push(builder.key());

        var build = builds[builder.builderName];
        build[results.TESTS] = loader.Loader._flattenTrie(build[results.TESTS]);
        results.simplifyFailureMap(build[results.FAILURE_MAP]);
        g_resultsByBuilder[builder.key()] = build;
    },
    _handleResultsFileLoadError: function(builder)
    {
        // FIXME: loader shouldn't depend on state defined in dashboard_base.js.
        this._builderKeysThatFailedToLoad.push(builder.key());

        // Remove this builder from builders, so we don't try to use the
        // data that isn't there.
        for (var c = this._builders.length - 1; c >= 0; --c) {
            if (this._builders[c].key() == builder.key())
                this._builders.splice(c, 1);
        }

        // TODO(sergiyb): Remove this when all layout tests are using swarming (crbug.com/524758).
        if (this._testType == "webkit_layout_tests" || this._testType == "webkit_tests") {
            for (var c = this._extraBuilders.length - 1; c >= 0; --c) {
                if (this._extraBuilders[c].key() == builder.key())
                    this._extraBuilders.splice(c, 1);
            }
        }

        // Proceed as if the resource had loaded.
        this._handleResourceLoad();
    },
    _handleResourceLoad: function()
    {
        if (this._haveResultsFilesLoaded()) {
          this._completeLoading();
        }
    },
    _haveResultsFilesLoaded: function()
    {
        for (var c = 0; c < this._builders.length; c++) {
            var builderKey = this._builders[c].key();
            if (!g_resultsByBuilder[builderKey] && this._builderKeysThatFailedToLoad.indexOf(builderKey) < 0)
                return false;
        }
        // TODO(sergiyb): Remove this when all layout tests are using swarming (crbug.com/524758).
        if (this._testType == "webkit_layout_tests" || this._testType == "webkit_tests") {
            for (var c = 0; c < this._extraBuilders.length; c++) {
                var builderKey = this._extraBuilders[c].key();
                if (!g_resultsByBuilder[builderKey] && this._builderKeysThatFailedToLoad.indexOf(builderKey) < 0)
                    return false;
            }
        }
        return true;
    },
    _completeLoading: function()
    {
        // Add errors
        if (this._builderKeysThatFailedToLoad.length) {
            this._errors.addMissing(this._builderKeysThatFailedToLoad);
        }
        if (this._staleBuilderKeys.length) {
            this._errors.addStale(this._staleBuilderKeys);
        }

        // Display page
        this._history.initialize();
    }
}

})();
