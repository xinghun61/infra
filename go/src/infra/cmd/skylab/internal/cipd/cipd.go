// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package cipd is an internal CIPD tool wrapper.
package cipd

import (
	"encoding/json"
	"io/ioutil"
	"os"
	"os/exec"

	"go.chromium.org/luci/common/errors"
)

// Package contains information about an installed package.
type Package struct {
	Package  string `json:"package"`
	Pin      Pin    `json:"pin"`
	Tracking string `json:"tracking"`
}

// Pin contains information about an installed package instance.
type Pin struct {
	Package    string `json:"package"`
	InstanceID string `json:"instance_id"`
}

// InstalledPackages returns information about installed packages.
func InstalledPackages(c Client, root string) ([]Package, error) {
	out, err := c.InstalledPackages(root)
	if err != nil {
		return nil, errors.Annotate(err, "get CIPD packages for %s", root).Err()
	}
	var obj struct {
		Result map[string][]Package `json:"result"`
	}
	err = json.Unmarshal(out, &obj)
	if err != nil {
		return nil, errors.Annotate(err, "get CIPD packages for %s", root).Err()
	}
	if obj.Result == nil {
		return nil, errors.Reason("get CIPD packages for %s: bad JSON", root).Err()
	}
	pkgs, ok := obj.Result[""]
	if !ok {
		return nil, errors.Reason("get CIPD packages for %s: bad JSON", root).Err()
	}
	return pkgs, nil
}

// Client is the interface for a CIPD client.  This can be used to
// mock out the standard CIPD client or otherwise modify how CIPD is
// called.
type Client interface {
	// InstalledPackages returns JSON encoded information about
	// CIPD packages installed in the given CIPD root.  See
	// example for JSON format.
	InstalledPackages(root string) ([]byte, error)
}

// CmdClient provides the standard implementation of the Client interface.
type CmdClient struct{}

// InstalledPackages implements the Client interface.
func (CmdClient) InstalledPackages(root string) ([]byte, error) {
	f, err := ioutil.TempFile("", "skylab-version")
	if err != nil {
		return nil, err
	}
	defer os.Remove(f.Name())
	cmd := exec.Command("cipd", "installed", "-root", root, "-json-output", f.Name())
	if _, err := cmd.Output(); err != nil {
		return nil, err
	}
	out, err := ioutil.ReadAll(f)
	if err != nil {
		return nil, err
	}
	return out, nil
}
