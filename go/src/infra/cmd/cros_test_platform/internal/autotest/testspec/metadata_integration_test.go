// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package testspec_test

import (
	"testing"

	"infra/cmd/cros_test_platform/internal/autotest/testspec"
	"infra/cmd/cros_test_platform/internal/testutils"

	"github.com/kylelemons/godebug/pretty"
	"go.chromium.org/chromiumos/infra/proto/go/chromite/api"
)

func TestLoadAndParseSimple(t *testing.T) {
	root, cleanup := testutils.CreateTempDirOrDie(t)
	defer cleanup()

	createTestFileOrDie(t, root, `
		AUTHOR = "somebody"
		NAME = "dummy_Pass"
		TEST_TYPE = "server"
	`)
	createSuiteFileOrDie(t, root, `
		AUTHOR = "somebody"
		NAME = "dummy_suite"
		TEST_TYPE = "server"
	`)
	got, err := testspec.Get(root)
	if err != nil {
		t.Fatalf("Get() failed: %s", err)
	}
	want := &api.TestMetadataResponse{
		Autotest: &api.AutotestTestMetadata{
			Suites: []*api.AutotestSuite{
				{Name: "dummy_suite"},
			},
			Tests: []*api.AutotestTest{
				{
					Name:                 "dummy_Pass",
					AllowRetries:         true,
					MaxRetries:           1,
					ExecutionEnvironment: api.AutotestTest_EXECUTION_ENVIRONMENT_SERVER,
				},
			},
		},
	}
	if diff := pretty.Compare(want, got); diff != "" {
		t.Errorf("response differs, -want +got: %s", diff)
	}
}

func createTestFileOrDie(t *testing.T, root string, text string) {
	testutils.CreateFileOrDie(t, []string{root, "site_tests", "control"}, text)
}

func createSuiteFileOrDie(t *testing.T, root string, text string) {
	testutils.CreateFileOrDie(t, []string{root, "test_suites", "control"}, text)
}
