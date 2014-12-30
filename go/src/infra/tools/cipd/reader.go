// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cipd

import (
	"archive/zip"
	"bytes"
	"crypto"
	_ "crypto/sha1"   // required for crypto.SHA1.New
	_ "crypto/sha512" // required for crypto.SHA512.New
	"encoding/hex"
	"fmt"
	"hash"
	"io"
	"os"

	"infra/tools/cipd/internal/keys"
)

// Hash algo name -> crypto.Hash.
var knownHashAlgos = map[string]crypto.Hash{
	"SHA1":   crypto.SHA1,
	"SHA512": crypto.SHA512,
}

// PackageReader acts as a provider of package's binary data.
type PackageReader interface {
	io.Closer
	io.Reader
	io.Seeker
}

// Package represents a binary package file.
type Package interface {
	// Close shuts down the package and its data provider.
	Close() error
	// Signed returns true if at least one signature has been verified.
	Signed() bool
	// Name returns package name, as defined in the manifest. Valid only for signed packages.
	Name() string
	// InstanceID returns id that identifies particular built of the package. It's a hash of the package data (excluding signatures).
	InstanceID() string
	// Files returns a list of files inside the package. Valid only for signed packages.
	Files() []File
	// Signatures returns a list of all package signatures (valid or not).
	Signatures() []SignatureBlock
	// DataReader returns reader that reads only package data block (skipping any signatures).
	// Note that it moves internal file pointer and thus can't be used at the same time files are extracted.
	DataReader() io.ReadSeeker
}

// PublicKeyProvider can hand out public keys given fingerprints.
type PublicKeyProvider func(fingerpint string) keys.PublicKey

// OpenPackage prepares a package for extraction. It verifies package signature
// and reads the list of package files. If the call succeeds, Package takes
// ownership of PackageReader and closes it when package.Close() is called. If
// an error is returned, PackageReader remains open.
func OpenPackage(r PackageReader, keys PublicKeyProvider) (Package, error) {
	out := &packageImpl{
		data: r,
	}
	err := out.open(keys)
	if err != nil {
		return nil, err
	}
	return out, nil
}

// OpenPackageFile opens a package file on disk.
func OpenPackageFile(path string, keys PublicKeyProvider) (pkg Package, err error) {
	file, err := os.Open(path)
	if err != nil {
		return
	}
	pkg, err = OpenPackage(file, keys)
	if err != nil {
		file.Close()
	}
	return
}

// ExtractPackage extracts all files from a signed package into a destination.
func ExtractPackage(p Package, dest Destination) error {
	if !p.Signed() {
		return fmt.Errorf("Package is not signed")
	}
	err := dest.Begin()
	if err != nil {
		return err
	}

	// Do not leave garbage around in case of a panic.
	needToEnd := true
	defer func() {
		if needToEnd {
			dest.End(false)
		}
	}()

	// Use a nested function in a loop for defers.
	extractOne := func(f File) error {
		out, err := dest.CreateFile(f.Name(), f.Executable())
		if err != nil {
			return err
		}
		defer out.Close()
		in, err := f.Open()
		if err != nil {
			return err
		}
		defer in.Close()
		_, err = io.Copy(out, in)
		return err
	}

	files := p.Files()
	for i, f := range files {
		log.Infof("[%d/%d] inflating %s", i+1, len(files), f.Name())
		err = extractOne(f)
		if err != nil {
			break
		}
	}

	needToEnd = false
	if err == nil {
		err = dest.End(true)
	} else {
		// Ignore error in 'End' and return the original error.
		dest.End(false)
	}

	return err
}

////////////////////////////////////////////////////////////////////////////////
// Package implementation.

type packageImpl struct {
	data       PackageReader
	dataSize   int64
	instanceID string

	hashes     map[string][]byte
	signatures []*signatureInfo
	signed     bool

	zip      *zip.Reader
	files    []File
	manifest Manifest
}

// signatureInfo is deserialized SignatureBlock plus some additional fields
// used by Package for bookkeeping.
type signatureInfo struct {
	// Decoded signature block as read from PEM.
	block SignatureBlock
	// True if we know about signing scheme used.
	supported bool
	// True if package hash doesn't match the hash in the signature.
	mismatch bool
	// Corresponding public key (publicKey.Valid is false if not known).
	publicKey keys.PublicKey
	// True if this signature has been successfully verified.
	verified bool
}

// open reads and verifies signatures.
func (p *packageImpl) open(keyGetter PublicKeyProvider) error {
	// Use hardcoded public keys by default.
	if keyGetter == nil {
		keyGetter = keys.KnownPublicKey
	}

	// Read all signatures from the file tail.
	signatures, signaturesOffset, err := ReadSignatureList(p.data)
	p.dataSize = signaturesOffset
	if err != nil {
		return err
	}

	// Mapping "hash algo name" -> hash.Hash. nil values means that we still
	// need to calculate that hash. All hashing is done via one pass over the
	// file.
	hashes := make(map[string]hash.Hash)
	// Need SHA1 for package.instanceID method.
	hashes["SHA1"] = nil

	// Figure out what signature algos are supported, grab public keys.
	for _, block := range signatures {
		info := &signatureInfo{block: block}
		if block.HashAlgo == sigBlockHashName && block.SignatureAlgo == sigBlockSigName {
			info.supported = true
			info.publicKey = keyGetter(info.block.SignatureKey)
			if info.publicKey.Valid {
				// Request to hash the body using this algo, we'd need to verify it.
				hashes[block.HashAlgo] = nil
			}
		}
		p.signatures = append(p.signatures, info)
	}

	// Calculate requested hashes.
	workers := []io.Writer{}
	for algoName := range hashes {
		hashes[algoName] = knownHashAlgos[algoName].New()
		workers = append(workers, hashes[algoName])
	}
	_, err = p.data.Seek(0, os.SEEK_SET)
	if err != nil {
		return err
	}
	// Calculate all hashes, read the data once.
	_, err = io.CopyN(io.MultiWriter(workers...), p.data, signaturesOffset)
	if err != nil {
		return err
	}
	// Extract digests into p.hashes map.
	p.hashes = make(map[string][]byte)
	for algoName, h := range hashes {
		p.hashes[algoName] = h.Sum(nil)
	}
	p.instanceID = hex.EncodeToString(p.hashes["SHA1"])

	// Now that hashes are known, verify signatures on them.
	for _, info := range p.signatures {
		if !info.supported || !info.publicKey.Valid {
			continue
		}
		digest := p.hashes[info.block.HashAlgo]
		if !bytes.Equal(digest, info.block.Digest) {
			info.mismatch = true
			continue
		}
		algo := knownHashAlgos[info.block.HashAlgo]
		info.verified = keys.CheckRSASignature(&info.publicKey, algo, info.block.Digest, info.block.Signature)
		if info.verified {
			p.signed = true
		}
	}

	// Do not attempt to read zip directory of an unsigned packages. Who knows
	// what may be inside.
	if p.signed {
		p.zip, err = zip.NewReader(&readerAt{r: p.data}, signaturesOffset)
		if err != nil {
			return err
		}
		p.files = make([]File, len(p.zip.File))
		for i, zf := range p.zip.File {
			p.files[i] = &fileInZip{z: zf}
			if p.files[i].Name() == manifestName {
				p.manifest, err = readManifestFile(p.files[i])
				if err != nil {
					return err
				}
			}
		}
	}

	return nil
}

func (p *packageImpl) Close() error {
	if p.data != nil {
		p.data.Close()
		p.data = nil
	}
	p.dataSize = 0
	p.instanceID = ""
	p.hashes = make(map[string][]byte)
	p.signatures = []*signatureInfo{}
	p.signed = false
	p.zip = nil
	p.files = []File{}
	p.manifest = Manifest{}
	return nil
}

func (p *packageImpl) Signed() bool       { return p.signed }
func (p *packageImpl) InstanceID() string { return p.instanceID }
func (p *packageImpl) Name() string       { return p.manifest.PackageName }
func (p *packageImpl) Files() []File      { return p.files }

func (p *packageImpl) Signatures() (out []SignatureBlock) {
	for _, s := range p.signatures {
		out = append(out, s.block)
	}
	return
}

func (p *packageImpl) DataReader() io.ReadSeeker {
	return io.NewSectionReader(&readerAt{r: p.data}, 0, p.dataSize)
}

////////////////////////////////////////////////////////////////////////////////
// Utilities.

// readManifestFile decodes manifest file zipped inside the package.
func readManifestFile(f File) (Manifest, error) {
	r, err := f.Open()
	if err != nil {
		return Manifest{}, err
	}
	defer r.Close()
	return readManifest(r)
}

////////////////////////////////////////////////////////////////////////////////
// File interface implementation via zip.File.

type fileInZip struct {
	z *zip.File
}

func (f *fileInZip) Name() string                 { return f.z.Name }
func (f *fileInZip) Size() uint64                 { return f.z.UncompressedSize64 }
func (f *fileInZip) Executable() bool             { return (f.z.Mode() & 0100) != 0 }
func (f *fileInZip) Open() (io.ReadCloser, error) { return f.z.Open() }

////////////////////////////////////////////////////////////////////////////////
// ReaderAt implementation via ReadSeeker. Not concurrency safe, moves file
// pointer around without any locking. Works OK in the context of OpenPackage
// function though (where OpenPackage takes sole ownership of ReadSeeker).

type readerAt struct {
	r io.ReadSeeker
}

func (r *readerAt) ReadAt(data []byte, off int64) (int, error) {
	_, err := r.r.Seek(off, os.SEEK_SET)
	if err != nil {
		return 0, err
	}
	return r.r.Read(data)
}
