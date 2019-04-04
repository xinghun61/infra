// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package userinput

import (
	"infra/libs/skylab/inventory"
	"regexp"
	"strings"
	"testing"

	"github.com/golang/protobuf/proto"
	"github.com/kylelemons/godebug/pretty"
)

func TestGetDeviceSpecs(t *testing.T) {
	s := &deviceSpecsGetter{
		inputFunc: newRegexpReplacer(regexp.MustCompile(`some\-hostname`), "this-other-hostname"),
	}

	initial := &inventory.CommonDeviceSpecs{
		Id:       stringPtr("some-id"),
		Hostname: stringPtr("some-hostname"),
	}
	got, err := s.Get(initial, "")
	if err != nil {
		t.Errorf("error in GetDeviceSpecs(): %s", err)
	}

	want := &inventory.CommonDeviceSpecs{
		Id:       stringPtr("some-id"),
		Hostname: stringPtr("this-other-hostname"),
	}
	if !proto.Equal(want, got) {
		t.Errorf("incorrect response from GetDeviceSpecs, -want, +got:\n%s", pretty.Compare(want, got))
	}
}

// newRegexpReplacer returns an inputFunc that replaces text matching re with
// repl.
func newRegexpReplacer(re *regexp.Regexp, repl string) inputFunc {
	r := regexpEditor{re: re, repl: []byte(repl)}
	return r.ReplaceAll
}

// regexpEditor has a method to replace occurrences of re with repl in given
// text.
type regexpEditor struct {
	re   *regexp.Regexp
	repl []byte
}

// ReplaceAll uses Regexp.ReplaceAll to modify incoming text.
//
// This function can be used as an inputFunc
func (e *regexpEditor) ReplaceAll(initial []byte) ([]byte, error) {
	return e.re.ReplaceAll(initial, e.repl), nil
}

func TestRegexpEditor(t *testing.T) {
	e := regexpEditor{
		re:   regexp.MustCompile(`some\-hostname`),
		repl: []byte("this-other-hostname"),
	}

	r, err := e.ReplaceAll([]byte(`Some multi-line.
text with some-hostname in the middle`))
	if err != nil {
		t.Errorf("error in regexpEditor.InteractiveInput(): %s", err)
	}

	got := string(r)
	want := `Some multi-line.
text with this-other-hostname in the middle`
	if want != got {
		t.Errorf("Incorrect output from regexpEditor.InteractiveInput(), -want, +got:\n%s",
			pretty.Compare(strings.Split(want, "\n"), strings.Split(got, "\n")))
	}
}

func TestCommentLines(t *testing.T) {
	text := `# first line is already a comment
second line will be commented.
    third line has spaces at the start.
		fourth has tabs.`
	want := `# first line is already a comment
# second line will be commented.
#     third line has spaces at the start.
# 		fourth has tabs.`
	got := commentLines(text)
	if want != got {
		t.Errorf("Incorrect output from commentLines(), -want, +got:\n%s",
			pretty.Compare(strings.Split(want, "\n"), strings.Split(got, "\n")))
	}
}

func TestDropCommentLines(t *testing.T) {
	text := `# first line is a comment, will be dropped.
second line will survive.
  # third line has comment after spaces, will be dropped.
	# fourth line has comment after tabs, will be dropped.
#fifth line has no space before comment, will be dropped.`
	want := "second line will survive."
	got := dropCommentLines(text)
	if want != got {
		t.Errorf("Incorrect output from dropCommentLines(), -want, +got:\n%s",
			pretty.Compare(strings.Split(want, "\n"), strings.Split(got, "\n")))
	}
}

func stringPtr(s string) *string {
	return &s
}
