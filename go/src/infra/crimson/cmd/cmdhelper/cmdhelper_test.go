// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmdhelper

import (
	"testing"
)

func TestGetVlanFromCommentVlanName(t *testing.T) {
	t.Parallel()
	// Testing only vlan-name here
	// Normal formatting
	line := "# @vlan-name: blah"
	names := vlanNames{}
	err := names.getVlanFromComment(line)
	if err != nil {
		t.Errorf("expected nil error, got '%s'", err)
	}
	if names.vlanName != "blah" {
		t.Errorf("vlanName: expected '%s', got '%s'", "blah", names.vlanName)
	}

	// No space after #
	line = "#@vlan-name: blah"
	names = vlanNames{}
	err = names.getVlanFromComment(line)
	if err != nil {
		t.Errorf("expected nil error, got '%s'", err)
	}
	if names.vlanName != "blah" {
		t.Errorf("vlanName: expected '%s', got '%s'", "blah", names.vlanName)
	}

	// No space after ':'
	line = "# @vlan-name:blah"
	names = vlanNames{}
	err = names.getVlanFromComment(line)
	if err != nil {
		t.Errorf("expected nil error, got '%s'", err)
	}
	if names.vlanName != "blah" {
		t.Errorf("vlanName: expected '%s', got '%s'", "blah", names.vlanName)
	}

	// space before ':'
	line = "# @vlan-name :blah"
	names = vlanNames{}
	err = names.getVlanFromComment(line)
	if err != nil {
		t.Errorf("expected nil error, got '%s'", err)
	}
	if names.vlanName != "blah" {
		t.Errorf("vlanName: expected '%s', got '%s'", "blah", names.vlanName)
	}

	// multiple spaces before name
	line = "# @vlan-name:    blah"
	names = vlanNames{}
	err = names.getVlanFromComment(line)
	if err != nil {
		t.Errorf("expected nil error, got '%s'", err)
	}
	if names.vlanName != "blah" {
		t.Errorf("vlanName: expected '%s', got '%s'", "blah", names.vlanName)
	}

	// trailing space
	line = "# @vlan-name: blah    "
	names = vlanNames{}
	err = names.getVlanFromComment(line)
	if err != nil {
		t.Errorf("expected nil error, got '%s'", err)
	}
	if names.vlanName != "blah" {
		t.Errorf("vlanName: expected '%s', got '%s'", "blah", names.vlanName)
	}

	// weird characters in the name

	weirdName := "abAZ09/@._-"
	line = "# @vlan-name: " + weirdName
	names = vlanNames{}
	err = names.getVlanFromComment(line)
	if err != nil {
		t.Errorf("expected nil error, got ''%s''", err)
	}
	if names.vlanName != weirdName {
		t.Errorf("vlanName: expected '%s', got '%s'", weirdName, names.vlanName)
	}

	// text after the name is an error: no space in vlan names
	line = "# @vlan-name: blah_1 triggers an error"
	names = vlanNames{}
	err = names.getVlanFromComment(line)
	if err == nil {
		t.Error("expected error, got nil")
	}
	if names.vlanName != "" {
		t.Errorf("vlanName: expected empty string, got '%s'", names.vlanName)
	}
}

func TestGetVlanFromCommentGeneric(t *testing.T) {
	t.Parallel()
	// Garbage data: error must be returned, names must be unchanged
	line := "asdjfk; epy53 fq8071ht4"
	names := vlanNames{
		vlanName:   "name sentinel",
		vlanSuffix: "suffix sentinel",
	}
	err := names.getVlanFromComment(line)
	if err == nil {
		t.Error("expected non-nil error, got nil")
	}
	if names.vlanSuffix != "suffix sentinel" {
		t.Errorf("vlanName: expected '%s', got '%s'",
			"suffix sentinel", names.vlanSuffix)
	}
	if names.vlanName != "name sentinel" {
		t.Errorf("vlanName: expected '%s', got '%s'",
			"name sentinel", names.vlanName)
	}

	// Missing name
	line = "# @vlan-name:  "
	names = vlanNames{
		vlanName:   "name sentinel",
		vlanSuffix: "suffix sentinel",
	}
	err = names.getVlanFromComment(line)
	if err == nil {
		t.Error("expected error, got nil")
	}
	if names.vlanSuffix != "suffix sentinel" {
		t.Errorf("vlanName: expected '%s', got '%s'",
			"suffix sentinel", names.vlanSuffix)
	}
	if names.vlanName != "name sentinel" {
		t.Errorf("vlanName: expected '%s', got '%s'",
			"name sentinel", names.vlanName)
	}

	// Normal formatting: vlan-suffix
	line = "# @vlan-suffix: -m1"
	names = vlanNames{}
	err = names.getVlanFromComment(line)
	if err != nil {
		t.Errorf("expected nil error, got '%s'", err)
	}
	if names.vlanSuffix != "-m1" {
		t.Errorf("vlanName: expected '%s', got '%s'", "-m1", names.vlanSuffix)
	}

	// Normal formatting: vlan-suffix + existing vlanName
	line = "# @vlan-suffix: -m1"
	names = vlanNames{vlanName: "name sentinel"}
	err = names.getVlanFromComment(line)
	if err != nil {
		t.Errorf("expected nil error, got '%s'", err)
	}
	if names.vlanSuffix != "-m1" {
		t.Errorf("vlanName: expected '%s', got '%s'", "-m1", names.vlanSuffix)
	}
	if names.vlanName != "name sentinel" {
		t.Errorf("vlanName: expected '%s', got '%s'",
			"name sentinel", names.vlanName)
	}
}
