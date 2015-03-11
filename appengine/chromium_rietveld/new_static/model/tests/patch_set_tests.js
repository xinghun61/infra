"use strict";

describe("PatchSet", function() {
    var assert = chai.assert;

    function assertSortedNames(inputNames, sortedNames) {
        var files = {};
        inputNames.forEach(function(name) {
            files[name] = {};
        });
        var patchset = new PatchSet(new Issue(1), 2);
        patchset.parseData({
            issue: 1,
            patchset: 2,
            files: files,
        });
        var actualNames = patchset.files.map(function(file) {
            return file.name;
        });
        assert.deepEqual(actualNames, sortedNames);
    }

    it("should sort headers before implementation files", function() {
        assertSortedNames([
            "Source/rendering/FrameView.hpp",
            "Source/frame/Frame.cpp",
            "Source/core/Document.cpp",
            "LayoutTests/foo/bar.js",
            "Source/core/DocumentImplementation.h",
            "Source/frame/Frame.h",
            "LayoutTests/foo/bar.html",
            "Source/rendering/FrameView.cpph",
            "Source/rendering/FrameView.cpp",
            "public/rendering/FrameView.cpp",
            "LayoutTests/foo/ack.html",
            "LayoutTests/foo/bar.hxx",
            "Source/rendering/FrameView.html",
            "Source/core/Document.h",
        ], [
            "public/rendering/FrameView.cpp",
            "Source/core/Document.h",
            "Source/core/Document.cpp",
            "Source/core/DocumentImplementation.h",
            "Source/frame/Frame.h",
            "Source/frame/Frame.cpp",
            "Source/rendering/FrameView.hpp",
            "Source/rendering/FrameView.cpp",
            "Source/rendering/FrameView.cpph",
            "Source/rendering/FrameView.html",
            "LayoutTests/foo/ack.html",
            "LayoutTests/foo/bar.hxx",
            "LayoutTests/foo/bar.html",
            "LayoutTests/foo/bar.js",
        ]);
    });

    it("should sort files without extensions", function() {
        assertSortedNames([
            "chrome/chrome_tests_unit.gypi",
            "components/webdata/DEPS",
            "components/webdata_services/DEPS",
            "components/components.gyp",
            "chrome/browser/sync/profile_sync_service_autofill_unittest.a",
            "components/webdata_services/web_data_service_test_util.cc",
            "chrome/browser/BUILD.gn",
            "components/webdata_services/web_data_service_wrapper.cc",
            "components/webdata_services/web_data_service_test_util.h",
            "components/OWNERS",
            "components/autofill/core/browser/DEPS",
            "components/webdata/common/web_data_service_test_util.cc",
            "chrome/browser/DEPS",
            "components/webdata_services/BUILD.gn",
            "chrome/browser/webdata/web_data_service_factory.h",
        ], [
            "chrome/browser/BUILD.gn",
            "chrome/browser/DEPS",
            "chrome/browser/sync/profile_sync_service_autofill_unittest.a",
            "chrome/browser/webdata/web_data_service_factory.h",
            "chrome/chrome_tests_unit.gypi",
            "components/autofill/core/browser/DEPS",
            "components/components.gyp",
            "components/OWNERS",
            "components/webdata_services/BUILD.gn",
            "components/webdata_services/DEPS",
            "components/webdata_services/web_data_service_test_util.h",
            "components/webdata_services/web_data_service_test_util.cc",
            "components/webdata_services/web_data_service_wrapper.cc",
            "components/webdata/common/web_data_service_test_util.cc",
            "components/webdata/DEPS",
        ]);
    });
});
