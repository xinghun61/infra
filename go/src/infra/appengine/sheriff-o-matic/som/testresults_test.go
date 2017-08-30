// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package som

import (
	"infra/monitoring/messages"
	"reflect"
	"testing"
)

var alertedBuilders = []messages.AlertedBuilder{
	{Name: "builderOne", Master: "masterOne"},
	{Name: "builderTwo", Master: "masterOne"},
	{Name: "builderThree", Master: "masterTwo"},
}

func TestGetBuildersByMaster(t *testing.T) {
	expectedMap := map[string][]string{
		"masterOne": {"builderOne", "builderTwo"},
		"masterTwo": {"builderThree"},
	}
	buildersMap := getBuildersByMaster(alertedBuilders)
	if !reflect.DeepEqual(expectedMap, buildersMap) {
		t.Errorf("expected map: %v. Found map: %v", expectedMap, buildersMap)
	}
}

type mockTestFailure struct{}

func (t *mockTestFailure) Signature() string {
	return "stepName and testNames"
}

func (t *mockTestFailure) Kind() string {
	return "test"
}

func (t *mockTestFailure) Severity() messages.Severity {
	return messages.NoSeverity
}

func (t *mockTestFailure) Title(bs []*messages.BuildStep) string {
	return "failing somewhere"
}

type fakeExtension struct{}

func TestIsTestFailure(t *testing.T) {
	testAlert := messages.Alert{
		Extension: messages.BuildFailure{
			Reason: &messages.Reason{
				Raw: &mockTestFailure{},
			},
		},
	}
	if !isTestFailure(testAlert) {
		t.Error("expected true, found false")
	}

	alert := messages.Alert{Extension: fakeExtension{}}
	if isTestFailure(alert) {
		t.Error("expected false, found true")
	}
}
