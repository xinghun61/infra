package testexpectations

import (
	"fmt"
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
			p := NewStringParser(test.input)
			if test.expected != nil {
				test.expected.Original = test.input
			}
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
