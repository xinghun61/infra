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

// InstalledPackages returns information about installed CIPD packages.
func InstalledPackages(root string) ([]Package, error) {
	out, err := installedPackages(root)
	if err != nil {
		return nil, errors.Annotate(err, "get CIPD packages for %s", root).Err()
	}
	pkgs, err := unmarshalPackages(out)
	if err != nil {
		return nil, errors.Annotate(err, "get CIPD packages for %s", root).Err()
	}
	return pkgs, nil
}

// installedPackages returns the raw JSON from running a cipd installed command.
func installedPackages(root string) ([]byte, error) {
	cmd := exec.Command("cipd", "installed", "-root", root)
	return jsonCmdOutput(cmd)
}

func unmarshalPackages(jsonData []byte) ([]Package, error) {
	var obj struct {
		Result map[string][]Package `json:"result"`
	}
	if err := json.Unmarshal(jsonData, &obj); err != nil {
		return nil, errors.Annotate(err, "unmarshal packages").Err()
	}
	if obj.Result == nil {
		return nil, errors.Reason("unmarshal packages: bad JSON").Err()
	}
	pkgs, ok := obj.Result[""]
	if !ok {
		return nil, errors.Reason("unmarshal packages: bad JSON").Err()
	}
	return pkgs, nil
}

// Run a cipd command that supports -json-output and return the raw JSON.
func jsonCmdOutput(cmd *exec.Cmd) ([]byte, error) {
	f, err := ioutil.TempFile("", "skylab-cipd-output")
	if err != nil {
		return nil, errors.Annotate(err, "JSON command output").Err()
	}
	defer os.Remove(f.Name())
	cmd.Args = append(cmd.Args, "-json-output", f.Name())
	if _, err = cmd.Output(); err != nil {
		return nil, errors.Annotate(err, "JSON command output").Err()
	}
	out, err := ioutil.ReadAll(f)
	if err != nil {
		return nil, errors.Annotate(err, "JSON command output").Err()
	}
	return out, nil
}
