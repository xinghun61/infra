// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"testing"

	. "github.com/smartystreets/goconvey/convey"

	"go.chromium.org/chromiumos/infra/proto/go/lab_platform"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform/skylab_local_state"
)

func TestUpdateDutStateFromHostInfo(t *testing.T) {
	Convey("When a DUT state is updated only provisionable labels and attributes are changed.", t, func() {
		i := &skylab_local_state.AutotestHostInfo{
			Attributes: map[string]string{
				"dummy-attribute": "dummy-value",
				"job_repo_url":    "dummy-url",
				"outlet_changed":  "true",
			},
			Labels: []string{
				"dummy-label:dummy-value",
				"cros-version:dummy-os-version",
				"fwro-version:dummy-fwro-version",
				"fwrw-version:dummy-fwrw-version",
			},
			SerializerVersion: 1,
		}

		state := &lab_platform.DutState{
			State: "dummy_state",
		}

		updateDutStateFromHostInfo(state, i)

		want := &lab_platform.DutState{
			State: "dummy_state",
			ProvisionableAttributes: map[string]string{
				"job_repo_url":   "dummy-url",
				"outlet_changed": "true",
			},
			ProvisionableLabels: map[string]string{
				"cros-version": "dummy-os-version",
				"fwro-version": "dummy-fwro-version",
				"fwrw-version": "dummy-fwrw-version",
			},
		}

		So(want, ShouldResemble, state)
	})
}
