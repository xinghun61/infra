// Copyright (c) 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package system

import (
	"fmt"
	"io/ioutil"
	"os/exec"
	"strings"

	"golang.org/x/net/context"
	"howett.net/plist"
)

func osInformation() (string, string, error) {
	data, err := ioutil.ReadFile("/System/Library/CoreServices/SystemVersion.plist")
	if err != nil {
		return "mac", "unknown", err
	}

	contents := map[string]interface{}{}
	if _, err := plist.Unmarshal(data, contents); err != nil {
		return "mac", "unknown", err
	}

	version, ok := contents["ProductVersion"]
	if !ok {
		return "mac", "unknown", fmt.Errorf("SystemVersion.plist is missing ProductVersion")
	}
	return "mac", version.(string), nil
}

func model(c context.Context) (string, error) {
	cmd := exec.CommandContext(c, "sysctl", "hw.model")
	out, err := cmd.Output()
	if err != nil {
		return "", err
	}
	s := string(out)
	return strings.TrimSpace(strings.TrimPrefix(s, "hw.model:")), nil
}
