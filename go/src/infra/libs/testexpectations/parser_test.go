package testexpectations

import (
	"bytes"
	"encoding/base64"
	"fmt"
	"io/ioutil"
	"net/http"
	"sort"
	"strings"
	"testing"

	. "github.com/smartystreets/goconvey/convey"
)

func TestParse(t *testing.T) {
	Convey("Parser", t, func() {
		tests := []struct {
			input    string
			expected *ExpectationStatement
			err      error
		}{
			{
				"",
				&ExpectationStatement{},
				nil,
			},
			{
				"# This is a comment.",
				&ExpectationStatement{
					Comment: "# This is a comment.",
				},
				nil,
			},
			{
				"fast/html/keygen.html [ Skip ]",
				&ExpectationStatement{
					TestName:     "fast/html/keygen.html",
					Expectations: []string{"Skip"},
				},
				nil,
			},
			{
				"crbug.com/12345 fast/html/keygen.html [ Crash ]",
				&ExpectationStatement{
					Bugs:         []string{"crbug.com/12345"},
					TestName:     "fast/html/keygen.html",
					Expectations: []string{"Crash"},
				},
				nil,
			},
			{
				"crbug.com/12345 fast/html/keygen.html [ Crash Pass ]",
				&ExpectationStatement{
					Bugs:         []string{"crbug.com/12345"},
					TestName:     "fast/html/keygen.html",
					Expectations: []string{"Crash", "Pass"},
				},
				nil,
			},
			{
				"crbug.com/12345 [ Win Debug ] fast/html/keygen.html [ Crash ]",
				&ExpectationStatement{
					Bugs:         []string{"crbug.com/12345"},
					Modifiers:    []string{"Win", "Debug"},
					TestName:     "fast/html/keygen.html",
					Expectations: []string{"Crash"},
				},
				nil,
			},
			{
				"crbug.com/12345 [ Win Debug ] fast/html/keygen.html [ Crash Pass ]",
				&ExpectationStatement{
					Bugs:         []string{"crbug.com/12345"},
					Modifiers:    []string{"Win", "Debug"},
					TestName:     "fast/html/keygen.html",
					Expectations: []string{"Crash", "Pass"},
				},
				nil,
			},
			{
				"Bug(darin) [ Mac10.9 Debug ] fast/html/keygen.html [ Skip ]",
				&ExpectationStatement{
					Bugs:         []string{"Bug(darin)"},
					Modifiers:    []string{"Mac10.9", "Debug"},
					TestName:     "fast/html/keygen.html",
					Expectations: []string{"Skip"},
				},
				nil,
			},
			{
				"crbug.com/504613 crbug.com/524248 paint/images/image-backgrounds-not-antialiased.html [ Failure ]",
				&ExpectationStatement{
					Bugs:         []string{"crbug.com/504613", "crbug.com/524248"},
					TestName:     "paint/images/image-backgrounds-not-antialiased.html",
					Expectations: []string{"Failure"},
				},
				nil,
			},
			{
				"crbug.com/504613 crbug.com/524248 [ Mac Win ] paint/images/image-backgrounds-not-antialiased.html [ Failure ]",
				&ExpectationStatement{
					Bugs:         []string{"crbug.com/504613", "crbug.com/524248"},
					Modifiers:    []string{"Mac", "Win"},
					TestName:     "paint/images/image-backgrounds-not-antialiased.html",
					Expectations: []string{"Failure"},
				},
				nil,
			},
			{
				"crbug.com/24182 fast/overflow/lots-of-sibling-inline-boxes.html [ Slow ] # Particularly slow in Debug: >12x slower!",
				&ExpectationStatement{
					Bugs:         []string{"crbug.com/24182"},
					TestName:     "fast/overflow/lots-of-sibling-inline-boxes.html",
					Expectations: []string{"Slow"},
					Comment:      "# Particularly slow in Debug: >12x slower!",
				},
				nil,
			},
			{
				"[ Debug ] http/tests/perf [ WontFix ]",
				&ExpectationStatement{
					Modifiers:    []string{"Debug"},
					TestName:     "http/tests/perf",
					Expectations: []string{"WontFix"},
				},
				nil,
			},
			{
				"not a valid input line",
				nil,
				fmt.Errorf(`expected tokLB or tokIDENT for expectations, but found "valid"`),
			},
		}

		for _, test := range tests {
			p := NewParser(bytes.NewBufferString(test.input))
			stmt, err := p.Parse()
			So(err, ShouldResemble, test.err)
			So(stmt, ShouldResemble, test.expected)

			if test.err != nil {
				continue
			}

			// And test round-trip back into a string.
			So(stmt.String(), ShouldEqual, test.input)
		}
	})
}

func ExampleParser_Parse() {
	var names []string
	for name := range LayoutTestExpectations {
		names = append(names, name)
	}
	sort.Strings(names)

	for _, name := range names {
		path := LayoutTestExpectations[name]
		URL := fmt.Sprintf("https://chromium.googlesource.com/chromium/src/+/master%s?format=TEXT", path)
		resp, err := http.Get(URL)
		if err != nil {
			fmt.Printf("Error fetching: %s\n", err)
			return
		}
		defer resp.Body.Close()

		reader := base64.NewDecoder(base64.StdEncoding, resp.Body)
		b, err := ioutil.ReadAll(reader)
		if err != nil {
			fmt.Printf("Error reading: %s\n", err)
			return
		}

		lines := strings.Split(string(b), "\n")
		stmts := []*ExpectationStatement{}
		for n, line := range lines {
			p := NewParser(bytes.NewBufferString(line))
			stmt, err := p.Parse()
			if err != nil {
				fmt.Printf("Error parsing %s:%d %q: %s\n", name, n, line, err)
				return
			}
			stmt.LineNumber = n
			stmt.Original = line
			stmts = append(stmts, stmt)
		}

		fmt.Printf("%s line count match? %t\n", name, len(stmts) == len(lines))

		for _, s := range stmts {
			r := s.String()
			// TODO(seanmccullough): Track extra whitespace between test names and
			// expectations in the original lines, or otherwise keep the original text
			// if we haven't edited the semantics of the line. The len(...) comparison
			// below is a brittle hack to test around this.

			if s.Original != r && len(s.Original)-len(r) != 1 {
				fmt.Printf("%s:%d differs:\n%q\n%q\n", path, s.LineNumber, s.Original, r)
			}
		}
	}

	// -Output:
	// ASANExpectations line count match? true
	// LeakExpectations line count match? true
	// MSANExpectations line count match? true
	// NeverFixTests line count match? true
	// SlowTests line count match? true
	// SmokeTests line count match? true
	// StaleTestExpectations line count match? true
	// TestExpectations line count match? true
	// W3CImportExpectations line count match? true
}
