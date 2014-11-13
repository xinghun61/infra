// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cipd

import (
	"archive/zip"
	"bytes"
	"crypto/rsa"
	"encoding/json"
	"encoding/pem"
	"fmt"
	"io"
	"io/ioutil"
	"strings"
)

// BuildPackageOptions defines options for BuildPackage function.
type BuildPackageOptions struct {
	// List of files to add to the package.
	Input []File
	// Where to write the package file to.
	Output io.Writer
	// Package name, e.g. 'infra/cipd'.
	PackageName string
}

// BuildPackageOptions defines options for SignPackage function.
type SignPackageOptions struct {
	// Reads package data (excluding any existing inline signatures!).
	Package io.Reader
	// Where to write the signature data to.
	Output io.Writer
	// Private key to sign the package with.
	PrivateKey *rsa.PrivateKey
	// Source of randomness for the signing.
	Random io.Reader
}

// BuildPackage builds a new package (named opts.PackageName) by archiving
// input files (passed via opts.Input). The final binary is written to
// opts.Output. Some output may be written even if BuildPackage eventually
// returns an error.
func BuildPackage(opts BuildPackageOptions) error {
	// Make sure no files are written to package service directory.
	for _, f := range opts.Input {
		if strings.HasPrefix(f.Name(), packageServiceDir+"/") {
			return fmt.Errorf("Can't write to %s: %s", packageServiceDir, f.Name())
		}
	}

	// Generate the manifest file, add to the list of input files.
	manifestFile, err := makeManifestFile(opts)
	if err != nil {
		return err
	}
	files := append(opts.Input, manifestFile)

	// Make sure filenames are unique.
	seenNames := make(map[string]struct{})
	for _, f := range files {
		_, seen := seenNames[f.Name()]
		if seen {
			return fmt.Errorf("File %s is provided twice", f.Name())
		}
		seenNames[f.Name()] = struct{}{}
	}

	// Write the final zip file.
	return zipInputFiles(files, opts.Output)
}

// SignPackage generates a signature given package file.
func SignPackage(opts SignPackageOptions) error {
	// Hash.
	hash := sigBlockHash.New()
	_, err := io.Copy(hash, opts.Package)
	if err != nil {
		return err
	}
	digest := hash.Sum(nil)

	// Sign the hash with the private key to get the signature.
	sig, err := rsa.SignPKCS1v15(opts.Random, opts.PrivateKey, sigBlockHash, digest)
	if err != nil {
		return err
	}
	keyFingerprint, err := publicKeyFingerprint(&opts.PrivateKey.PublicKey)
	if err != nil {
		return err
	}

	// Append PEM encoded signature block to the end, reader will scan for PEM
	// header and footer to figure out how to read it.
	block, err := makeSignatureBlock(digest, sig, keyFingerprint)
	if err != nil {
		return err
	}
	_, err = opts.Output.Write(block)
	return err
}

// zipInputFiles deterministically builds a zip archive out of input files and
// writes it to the writer. Files are written in the order given.
func zipInputFiles(files []File, w io.Writer) error {
	writer := zip.NewWriter(w)
	defer writer.Close()

	for _, in := range files {
		// Intentionally do not add timestamp or file mode to make zip archive
		// deterministic. See also zip.FileInfoHeader() implementation.
		fh := zip.FileHeader{
			Name:               in.Name(),
			UncompressedSize64: in.Size(),
			Method:             zip.Deflate,
		}
		if fh.UncompressedSize64 > (1<<32)-1 {
			fh.UncompressedSize = (1 << 32) - 1
		} else {
			fh.UncompressedSize = uint32(fh.UncompressedSize64)
		}
		// Use owner file mode bit to carry 'executable' flag.
		if in.Executable() {
			fh.SetMode(0700)
		} else {
			fh.SetMode(0600)
		}

		src, err := in.Open()
		if err != nil {
			return err
		}

		dst, err := writer.CreateHeader(&fh)
		if err != nil {
			src.Close()
			return err
		}

		written, err := io.Copy(dst, src)
		src.Close()
		if err != nil {
			return err
		}

		if uint64(written) != in.Size() {
			return fmt.Errorf("File %s changed midway", in.Name())
		}
	}

	return nil
}

////////////////////////////////////////////////////////////////////////////////

type manifestFile []byte

func (m *manifestFile) Name() string     { return manifestName }
func (m *manifestFile) Size() uint64     { return uint64(len(*m)) }
func (m *manifestFile) Executable() bool { return false }
func (m *manifestFile) Open() (io.ReadCloser, error) {
	return ioutil.NopCloser(bytes.NewReader(*m)), nil
}

// makeManifestFile generates a package manifest file and returns it as
// File interface.
func makeManifestFile(opts BuildPackageOptions) (File, error) {
	buf := &bytes.Buffer{}
	err := writeManifest(&Manifest{
		FormatVersion: manifestFormatVersion,
		PackageName:   opts.PackageName,
	}, buf)
	if err != nil {
		return nil, err
	}
	out := manifestFile(buf.Bytes())
	return &out, nil
}

////////////////////////////////////////////////////////////////////////////////

// makeSignatureBlock produces byte buffer with PEM encoded signature JSON.
func makeSignatureBlock(digest []byte, sig []byte, keyFingerprint string) ([]byte, error) {
	// To JSON byte array.
	block := SignatureBlock{
		HashAlgo:      sigBlockHashName,
		Hash:          digest,
		SignatureAlgo: sigBlockSigName,
		SignatureKey:  keyFingerprint,
		Signature:     sig,
	}
	data, err := json.Marshal(block)
	if err != nil {
		return nil, err
	}

	// To PEM encoded byte array.
	asPem := pem.EncodeToMemory(&pem.Block{
		Type:  sigBlockPEMType,
		Bytes: data,
	})

	return asPem, nil
}
