// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package inventory

import (
	"io/ioutil"
	"os"
	"testing"

	"github.com/kylelemons/godebug/pretty"
)

func TestWriteAndLoadLab(t *testing.T) {
	t.Parallel()
	d, err := ioutil.TempDir("", "test")
	if err != nil {
		t.Fatalf("Error creating temporary directory: %s", err)
	}
	defer os.RemoveAll(d)
	id := "some-dut"
	want := &Lab{
		Duts: []*DeviceUnderTest{
			{Common: &CommonDeviceSpecs{Id: &id, Hostname: &id}},
		},
	}
	if err := WriteLab(want, d); err != nil {
		t.Fatal(err)
	}
	got, err := LoadLab(d)
	if err != nil {
		t.Fatal(err)
	}
	if diff := pretty.Compare(want, got); diff != "" {
		t.Errorf("Loaded Lab differs -want +got, %s", diff)
	}
}
