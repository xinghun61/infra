// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package som

import (
	"infra/monitoring/messages"
)

// getBuildersByMaster builds a map with master name keys and a list of builder names
// for each value.
//
// It returns the map and takes a slice of AlertedBuilders that need to be sorted based on their masters.
func getBuildersByMaster(builders []messages.AlertedBuilder) map[string][]string {
	buildersByMaster := map[string][]string{}
	for _, builder := range builders {
		buildersByMaster[builder.Master] = append(buildersByMaster[builder.Master], builder.Name)
	}
	return buildersByMaster
}

// isTestFaillure returns true/false based on whether the given Alert is for BuildFailure.
func isTestFailure(alert messages.Alert) bool {
	if bf, ok := alert.Extension.(messages.BuildFailure); ok && bf.Reason.Kind() == "test" {
		return true
	}
	return false
}
