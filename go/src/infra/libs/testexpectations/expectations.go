package testexpectations

var (
	// LayoutTestExpectations is a map of expectation file locations, relative to repo+branch.
	LayoutTestExpectations = map[string]string{
		"TestExpectations":      "/third_party/WebKit/LayoutTests/TestExpectations",      // The main test failure suppression file. In theory, this should be used for flaky lines and NeedsRebaseline/NeedsManualRebaseline lines.
		"ASANExpectations":      "/third_party/WebKit/LayoutTests/ASANExpectations",      // Tests that fail under ASAN.
		"LeakExpectations":      "/third_party/WebKit/LayoutTests/LeakExpectations",      // Tests that have memory leaks under the leak checker.
		"MSANExpectations":      "/third_party/WebKit/LayoutTests/MSANExpectations",      // Tests that fail under MSAN.
		"NeverFixTests":         "/third_party/WebKit/LayoutTests/NeverFixTests",         // Tests that we never intend to fix (e.g. a test for Windows-specific behavior will never be fixed on Linux/Mac). Tests that will never pass on any platform should just be deleted, though.
		"SlowTests":             "/third_party/WebKit/LayoutTests/SlowTests",             // Tests that take longer than the usual timeout to run. Slow tests are given 5x the usual timeout.
		"SmokeTests":            "/third_party/WebKit/LayoutTests/SmokeTests",            // A small subset of tests that we run on the Android bot.
		"StaleTestExpectations": "/third_party/WebKit/LayoutTests/StaleTestExpectations", // Platform-specific lines that have been in TestExpectations for many months. They‘re moved here to get them out of the way of people doing rebaselines since they’re clearly not getting fixed anytime soon.
		"W3CImportExpectations": "/third_party/WebKit/LayoutTests/W3CImportExpectations", // A record of which W3C tests should be imported or skipped.
	}
)
