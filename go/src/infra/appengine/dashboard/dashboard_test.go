// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package dashboard

import (
	"testing"
)

func TestDataRetrieved(t *testing.T) {
	services := []ChopsService{
		{
			Name: "testService",
			Sla:  "www.google.com",
		},
	}

	testService := ChopsService{
		Name: "testService",
		Sla:  "www.google.com",
	}

	for _, service := range services {
		if service.Name != testService.Name {
			t.Errorf("Service name, %q, does not match expected service name: %q", service.Name, testService.Name)
			continue
		}
	}
}
