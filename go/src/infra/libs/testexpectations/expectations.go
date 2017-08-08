package testexpectations

import (
	"fmt"
	"sort"
	"strings"

	"golang.org/x/net/context"

	"infra/monitoring/client"
)

var (
	// LayoutTestExpectations is a map of expectation file locations, relative to repo+branch.
	LayoutTestExpectations = map[string]string{
		"TestExpectations":      "third_party/WebKit/LayoutTests/TestExpectations",      // The main test failure suppression file. In theory, this should be used for flaky lines and NeedsRebaseline/NeedsManualRebaseline lines.
		"ASANExpectations":      "third_party/WebKit/LayoutTests/ASANExpectations",      // Tests that fail under ASAN.
		"LeakExpectations":      "third_party/WebKit/LayoutTests/LeakExpectations",      // Tests that have memory leaks under the leak checker.
		"MSANExpectations":      "third_party/WebKit/LayoutTests/MSANExpectations",      // Tests that fail under MSAN.
		"NeverFixTests":         "third_party/WebKit/LayoutTests/NeverFixTests",         // Tests that we never intend to fix (e.g. a test for Windows-specific behavior will never be fixed on Linux/Mac). Tests that will never pass on any platform should just be deleted, though.
		"SlowTests":             "third_party/WebKit/LayoutTests/SlowTests",             // Tests that take longer than the usual timeout to run. Slow tests are given 5x the usual timeout.
		"SmokeTests":            "third_party/WebKit/LayoutTests/SmokeTests",            // A small subset of tests that we run on the Android bot.
		"StaleTestExpectations": "third_party/WebKit/LayoutTests/StaleTestExpectations", // Platform-specific lines that have been in TestExpectations for many months. They‘re moved here to get them out of the way of people doing rebaselines since they’re clearly not getting fixed anytime soon.
		"W3CImportExpectations": "third_party/WebKit/LayoutTests/W3CImportExpectations", // A record of which W3C tests should be imported or skipped.
	}
)

// FileSet is a set of expectation files.
type FileSet struct {
	Files []*File
}

// File is an expectation file.
type File struct {
	Path         string
	Expectations []*ExpectationStatement
}

func (f *File) String() string {
	s := []string{}
	for _, e := range f.Expectations {
		s = append(s, e.String())
	}
	return strings.Join(s, "\n")
}

// LoadAll returns a FileSet of all known layout test expectation files.
func LoadAll(c context.Context) (*FileSet, error) {
	type resp struct {
		err  error
		file *File
	}

	rCh := make(chan resp)

	for n, p := range LayoutTestExpectations {
		name, path := n, p
		go func() {
			r := resp{}

			URL := fmt.Sprintf("https://chromium.googlesource.com/chromium/src/+/master/%s?format=TEXT", path)
			b, err := client.GetGitiles(c, URL)
			if err != nil {
				r.err = fmt.Errorf("error reading: %s", err)
				rCh <- r
				return
			}
			lines := strings.Split(string(b), "\n")
			stmts := make([]*ExpectationStatement, len(lines))
			for n, line := range lines {
				p := NewStringParser(line)
				stmt, err := p.Parse()
				if err != nil {
					r.err = fmt.Errorf("error parsing %s:%d %q: %s", name, n, line, err)
					rCh <- r
					return
				}
				stmt.LineNumber = n
				stmts[n] = stmt
			}
			r.file = &File{Path: path, Expectations: stmts}
			rCh <- r
			return
		}()
	}

	ret := &FileSet{}
	errs := []error{}

	for _ = range LayoutTestExpectations {
		r := <-rCh
		if r.err != nil {
			errs = append(errs, r.err)
		} else {
			ret.Files = append(ret.Files, r.file)
		}
	}

	if len(errs) > 0 {
		return nil, fmt.Errorf("errors fetching Expectation files: %v", errs)
	}
	return ret, nil
}

// UpdateExpectation updates a test expectation within a FileSet.
func (fs *FileSet) UpdateExpectation(es *ExpectationStatement) error {
	// Find all files that mention es.TestName already
	// Naive: just replace any existing rules. This won't work in practice.
	for _, file := range fs.Files {
		for _, exp := range file.Expectations {
			// TODO: deal with directories in addition to exact matches.
			if exp.TestName == es.TestName {
				exp.Expectations = es.Expectations
				exp.Modifiers = es.Modifiers
				exp.Bugs = es.Bugs
				exp.Dirty = true
			}
		}
	}

	return nil
}

type byOverrides []*ExpectationStatement

func (l byOverrides) Len() int           { return len(l) }
func (l byOverrides) Less(i, j int) bool { return l[i].Overrides(l[j]) }
func (l byOverrides) Swap(i, j int)      { l[i], l[j] = l[j], l[i] }

// ToCL returns a map of file paths to new file contents.
func (fs *FileSet) ToCL() map[string]string {
	// TODO: expectation coalescing, normalizing, splitting. This is probably
	// not the right function to implement those operations but they need to be
	// implemented.
	ret := map[string]string{}
	for _, file := range fs.Files {
		for _, s := range file.Expectations {
			// Only include files with modified lines in the CL.
			if s.Dirty {
				ret[file.Path] = file.String()
			}
		}
	}
	return ret
}

// NameMatch returns true if the extatement matches testName.
func (es *ExpectationStatement) NameMatch(testName string) bool {
	// Direct matches.
	if testName == es.TestName {
		return true
	}

	// Partial matches.
	if es.IsDir() && strings.HasPrefix(testName, es.TestName) {
		return true
	}

	return false
}

// IsDir returns true if the statement's test name is actually a file path to
// a directory rather than an individual test.
func (es *ExpectationStatement) IsDir() bool {
	// If the expectation specifies a file path that is a directory, it
	// applies to anything under that directory. This "doesn't end in .html"
	// heuristic may be too brittle. TODO: Investigate accuracy of this assumption,
	// and look into alternatives if it doesn't hold.
	// In particular, look into virtual_test_suites in
	// third_party/WebKit/Tools/Scripts/webkitpy/layout_tests/port/base.py

	return !strings.HasSuffix(es.TestName, ".html")
}

// ExpandModifiers returns the list of all modifiers that the rule should match.
func (es *ExpectationStatement) ExpandModifiers() []string {
	ret := es.Modifiers
	for _, m := range es.Modifiers {
		switch strings.ToLower(m) {
		case "mac":
			ret = append(ret, "retina", "mac10.9", "mac10.11", "mac10.12")
			break
		case "win":
			ret = append(ret, "win7", "win10")
			break
		case "linux":
			ret = append(ret, "trusty")
			break
		case "android":
			ret = append(ret, "kitkat")
		}
	}

	return ret
}

// ModifierMatch returns true if the given modifier matches the statement's
// modifier or any of its expanded modifiers.
func (es *ExpectationStatement) ModifierMatch(mod string) bool {
	if len(es.Modifiers) == 0 {
		// No modifers specified means it applies to all configurations.
		return true
	}

	for _, m := range es.ExpandModifiers() {
		if strings.ToLower(m) == strings.ToLower(mod) {
			return true
		}
	}
	return false
}

// Overrides returns true if the receiver should override other when evaluating
// statement matches for a given test, configuration. This establishes an
// ordering on the expectation statements so they can be sorted by precedence.
func (es *ExpectationStatement) Overrides(other *ExpectationStatement) bool {
	// Similarly to CSS selectors, these rules give preference to higher specificity.
	// First check modifier specificity, then test path specificity.
	// See https://chromium.googlesource.com/chromium/src/+/master/docs/testing/layout_test_expectations.md
	// for more complete documentation.
	if len(other.Modifiers) == 0 && len(es.Modifiers) > 0 {
		// Using any modifiers is more specific than not using any modifiers.
		return true
	}

	if len(other.ExpandModifiers()) > len(other.Modifiers) &&
		len(es.ExpandModifiers()) == len(es.Modifiers) &&
		len(es.Modifiers) > 0 {
		// other is using a modifier macro, which is less specific than a particular configuration.
		return true
	}

	if other.IsDir() && !es.IsDir() {
		// other is using a directory path, which is less specific than a particluar test file name.
		return true
	}

	return false
}

// Applies returns true if the statement applies to the given test, configuration.
func (es *ExpectationStatement) Applies(testName, configuration string) bool {
	return es.NameMatch(testName) && es.ModifierMatch(configuration)
}

// ForTest returns a list of ExpectationStatement, sorted in decreasing order of
// precedence, that match the given test and configuration.
func (fs *FileSet) ForTest(testName, configuration string) []*ExpectationStatement {
	ret := []*ExpectationStatement{}
	for _, file := range fs.Files {
		for _, s := range file.Expectations {
			if s.Applies(testName, configuration) {
				ret = append(ret, s)
			}
		}
	}

	// Return most specific applicable statement first.
	sort.Sort(byOverrides(ret))
	return ret
}
