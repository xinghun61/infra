// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package local

import (
	"encoding/json"
	"io"
	"io/ioutil"
)

const (
	// Name of the directory inside an installation root reserved for cipd stuff.
	siteServiceDir = ".cipd"
	// Name of the directory inside the package reserved for cipd stuff.
	packageServiceDir = ".cipdpkg"
	// Name of the manifest file inside the package.
	manifestName = packageServiceDir + "/manifest.json"
	// Format version to write to the manifest file.
	manifestFormatVersion = "1"
)

// Manifest defines structure of manifest.json file.
type Manifest struct {
	FormatVersion string     `json:"format_version"`
	PackageName   string     `json:"package_name"`
	Files         []FileInfo `json:"files,omitempty"` // present only in deployed manifest
}

// FileInfo is JSON-ish struct with info extracted from File interface.
type FileInfo struct {
	// Name is slash separated file path relative to a package root, e.g. "dir/dir/file".
	Name string `json:"name"`
	// Size is a size of the file. 0 for symlinks.
	Size uint64 `json:"size"`
	// Executable is true if the file is executable. Only used for Linux\Mac archives. False for symlinks.
	Executable bool `json:"executable,omitempty"`
	// Symlink is a path the symlink points to or "" if this file is not a symlink.
	Symlink string `json:"symlink,omitempty"`
}

// readManifest reads and decodes manifest JSON from io.Reader.
func readManifest(r io.Reader) (manifest Manifest, err error) {
	blob, err := ioutil.ReadAll(r)
	if err == nil {
		err = json.Unmarshal(blob, &manifest)
	}
	return
}

// writeManifest encodes and writes manifest JSON to io.Writer.
func writeManifest(m *Manifest, w io.Writer) error {
	data, err := json.MarshalIndent(m, "", "  ")
	if err != nil {
		return err
	}
	_, err = w.Write(data)
	return err
}
