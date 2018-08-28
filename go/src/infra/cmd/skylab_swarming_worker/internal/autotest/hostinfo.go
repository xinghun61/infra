// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package autotest

import (
	"encoding/json"
	"fmt"
)

// HostInfo stores the host information.  Hostinfo files are used to
// pass host information to Autotest and receive host information
// changes from Autotest.
type HostInfo struct {
	Labels     []string          `json:"labels"`
	Attributes map[string]string `json:"attributes"`
}

type versionedHostInfo struct {
	*HostInfo
	SerializerVersion int `json:"serializer_version"`
}

const supportedSerializerVersion = 1

// UnmarshalHostInfo deserializes a HostInfo struct from a slice of bytes.
func UnmarshalHostInfo(blob []byte) (*HostInfo, error) {
	var vhi versionedHostInfo
	err := json.Unmarshal(blob, &vhi)
	if vhi.SerializerVersion != supportedSerializerVersion {
		return nil, fmt.Errorf("Can not unmarshal HostInfo with serializer version %d",
			vhi.SerializerVersion)
	}
	return vhi.HostInfo, err
}

// MarshalHostInfo serializes the HostInfo struct into a slice of bytes.
func MarshalHostInfo(hi *HostInfo) ([]byte, error) {
	vhi := versionedHostInfo{
		HostInfo:          hi,
		SerializerVersion: supportedSerializerVersion,
	}
	return json.Marshal(vhi)
}
