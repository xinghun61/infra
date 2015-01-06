// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cipd

import (
	"crypto"
	_ "crypto/sha512" // required for crypto.SHA512.New
	"encoding/json"
	"fmt"
	"io"
	"io/ioutil"
	"regexp"

	"infra/libs/build"
)

// Name of the directory inside the package reserved for cipd stuff.
const packageServiceDir = ".cipdpkg"

// Name of the directory inside an installation root reserved for cipd stuff.
const siteServiceDir = ".cipd"

// packageNameRe is a Regular expression for a package name: <word>/<word/<word>
// Package names must be lower case.
var packageNameRe = regexp.MustCompile(`^([a-z0-9_\-]+/)*[a-z0-9_\-]+$`)

// Name of the manifest file inside the package.
const manifestName = packageServiceDir + "/manifest.json"

// Format version to write to the manifest file.
const manifestFormatVersion = "1"

// Hashing algorithm used to generate the signature.
const sigBlockHash = crypto.SHA512

// Symbolic name of the algorithm, will show up in the signature block.
const sigBlockHashName = "SHA512"

// Symbolic name of signature algorithm, will show up in the signature block.
const sigBlockSigName = "PKCS1v15"

// Name of the signature PEM block.
const sigBlockPEMType = "CIPD SIGNATURE"

// Manifest defines structure of manifest.json file.
type Manifest struct {
	FormatVersion string `json:"format_version"`
	PackageName   string `json:"package_name"`
}

// SignatureBlock is appended to the end of the package as PEM encoded JSON.
// It can also float on its own as a separate entity.
type SignatureBlock struct {
	HashAlgo      string `json:"hash_algo"`
	Digest        []byte `json:"digest"`
	SignatureAlgo string `json:"signature_algo"`
	SignatureKey  string `json:"signature_key"`
	Signature     []byte `json:"signature"`
}

// Metadata is stored on the server alongside a package (but not as part of the
// package). It describes when and how the package was built and uploaded.
type Metadata struct {
	Date     string `json:"date"`
	Hostname string `json:"hostname"`
	User     string `json:"user"`
}

// ValidatePackageName returns error if a string doesn't look like a valid package name.
func ValidatePackageName(name string) error {
	if !packageNameRe.MatchString(name) {
		return fmt.Errorf("Invalid package name: %s", name)
	}
	return nil
}

// ValidateInstanceID returns error if a string doesn't look like a valid package instance id.
func ValidateInstanceID(s string) error {
	// Instance id is SHA1 hex digest currently.
	if len(s) != 40 {
		return fmt.Errorf("Not a valid package instance ID \"%s\": not 40 bytes", s)
	}
	for _, c := range s {
		if !((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f')) {
			return fmt.Errorf("Not a valid package instance ID \"%s\": wrong char %c", s, c)
		}
	}
	return nil
}

// DefaultServiceURL returns URL to a backend to use by default.
func DefaultServiceURL() string {
	if build.ReleaseBuild {
		return "https://chrome-infra-packages.appspot.com"
	}
	return "https://chrome-infra-packages-dev.appspot.com"
}

// readManifest reads and decodes manifest JSON from io.Reader.
func readManifest(r io.Reader) (Manifest, error) {
	blob, err := ioutil.ReadAll(r)
	if err != nil {
		return Manifest{}, err
	}
	manifest := Manifest{}
	err = json.Unmarshal(blob, &manifest)
	if err != nil {
		return Manifest{}, err
	}
	return manifest, nil
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

// userAgent returns user agent string to send with each request.
func userAgent() string {
	if build.ReleaseBuild {
		return "cipd 1.0 release"
	}
	return "cipd 1.0 testing"
}
