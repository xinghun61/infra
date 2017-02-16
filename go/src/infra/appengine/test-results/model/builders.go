// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package model

// BuilderData is the data returned from the GET "/builders"
// endpoint.
type BuilderData struct {
	Masters           []Master `json:"masters"`
	NoUploadTestTypes []string `json:"no_upload_test_types"`
}

// Master represents information about a build master.
type Master struct {
	Name       string           `json:"name"`
	Identifier string           `json:"url_name"`
	Groups     []string         `json:"groups"`
	Tests      map[string]*Test `json:"tests"`
}

// Test represents information about Tests in a master.
type Test struct {
	Builders []string `json:"builders"`
}
