// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cipd

import (
	"crypto"
	_ "crypto/sha512"
	"encoding/json"
	"fmt"
	"io"
	"io/ioutil"
	"strings"
)

// Name of the directory inside the package reserved for cipd stuff.
const packageServiceDir = ".cipdpkg"

// Name of the directory inside an installation root reserved for cipd stuff.
const siteServiceDir = ".cipd"

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
	// Manifest format version, see manifestFormatVersion.
	FormatVersion string
	// Name of the package, e.g. 'infra/cipd'.
	PackageName string
}

// SignatureBlock is appended to the end of the package as PEM encoded JSON.
// It can also float on its own as a separate entity.
type SignatureBlock struct {
	// Hash algorithm used.
	HashAlgo string
	// Package data digest.
	Hash []byte

	// Signing algorithm used.
	SignatureAlgo string
	// Fingerprint of the PEM encoded public key (its SHA1 hex digest).
	SignatureKey string
	// The actual signature.
	Signature []byte
}

// ValidatePackageName returns error if a string doesn't look like a valid package name.
func ValidatePackageName(name string) error {
	// TODO: implement.
	if name == "" || strings.Contains(name, "..") || name[0] == '/' {
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
