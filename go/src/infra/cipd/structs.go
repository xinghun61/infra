// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cipd

import (
	"crypto"
	_ "crypto/sha512"
	"encoding/json"
	"io"
	"io/ioutil"
)

// NAme of the directory inside the package reserved for cipd stuff.
const packageServiceDir = ".cipdpkg"

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
