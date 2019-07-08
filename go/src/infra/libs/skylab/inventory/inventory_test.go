// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package inventory

import (
	fmt "fmt"
	"io/ioutil"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"unicode"

	"github.com/kylelemons/godebug/pretty"
)

func TestWriteAndLoadLab(t *testing.T) {
	t.Parallel()
	id := "some-dut"
	board := "some-board"
	labs := map[string]*Lab{
		"empty": {},
		"has_common": {Duts: []*DeviceUnderTest{
			{Common: &CommonDeviceSpecs{
				Id:       &id,
				Hostname: &id,
			}},
		}},
		"has_labels": {Duts: []*DeviceUnderTest{
			{Common: &CommonDeviceSpecs{
				Id:       &id,
				Hostname: &id,
				Labels:   &SchedulableLabels{Board: &board},
			}},
		}},
	}

	for lname, lab := range labs {
		t.Run(fmt.Sprintf("%s", lname), func(t *testing.T) {
			d, err := ioutil.TempDir("", "test")
			if err != nil {
				t.Fatalf("Error creating temporary directory: %s", err)
			}
			defer func() {
				if err = os.RemoveAll(d); err != nil {
					t.Fatal(err)
				}
			}()
			if err := WriteLab(lab, d); err != nil {
				t.Fatal(err)
			}
			got, err := LoadLab(d)
			if err != nil {
				t.Fatal(err)
			}
			if diff := pretty.Compare(lab, got); diff != "" {
				t.Errorf("Loaded Lab differs -want +got, %s", diff)
			}
		})
	}
}

func TestWriteLabPythonifies(t *testing.T) {
	t.Parallel()
	d, err := ioutil.TempDir("", "test")
	if err != nil {
		t.Fatalf("Error creating temporary directory: %s", err)
	}
	defer os.RemoveAll(d)
	id := "some-dut"
	l := &Lab{
		Duts: []*DeviceUnderTest{
			{Common: &CommonDeviceSpecs{Id: &id, Hostname: &id}},
		},
	}
	if err = WriteLab(l, d); err != nil {
		t.Fatal(err)
	}

	text, err := ioutil.ReadFile(filepath.Join(d, labFilename))
	if err != nil {
		t.Errorf("Error reading back lab: %s", err)
	}
	lines := stripWhitespace(strings.Split(string(text), "\n"))
	want := strings.Split(`
  duts {
    common {
      hostname: "some-dut"
      id: "some-dut"
    }
	}`, "\n")
	want = stripWhitespace(want)
	if diff := pretty.Compare(want, lines); diff != "" {
		t.Errorf("Loaded Lab differs -want +got, %s", diff)
	}
}

func stripWhitespace(lines []string) []string {
	ret := make([]string, 0, len(lines))
	for i := range lines {
		l := strings.TrimFunc(lines[i], unicode.IsSpace)
		if l != "" {
			ret = append(ret, l)
		}
	}
	return ret
}
