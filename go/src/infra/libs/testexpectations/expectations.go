package testexpectations

import (
	"fmt"
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

// ToCL returns a map of file paths to new file contents.
func (fs *FileSet) ToCL() map[string]string {
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
