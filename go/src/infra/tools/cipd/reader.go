// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cipd

import (
	"archive/zip"
	"crypto/sha1"
	"encoding/hex"
	"fmt"
	"io"
	"os"
)

// Package represents a binary package file.
type Package interface {
	// Close shuts down the package and its data provider.
	Close() error
	// Name returns package name, as defined in the manifest.
	Name() string
	// InstanceID returns id that identifies particular built of the package. It's a hash of the package data.
	InstanceID() string
	// Files returns a list of files inside the package.
	Files() []File
	// DataReader returns reader that reads raw package data.
	DataReader() io.ReadSeeker
}

// OpenPackage verifies package SHA1 hash (instanceID if not empty string) and
// prepares a package for extraction. If the call succeeds, Package takes
// ownership of io.ReadSeeker. If it also implements io.Closer, it will be
// closed when package.Close() is called. If an error is returned, io.ReadSeeker
// remains unowned and caller is responsible for closing it (if required).
func OpenPackage(r io.ReadSeeker, instanceID string) (Package, error) {
	out := &packageImpl{data: r}
	err := out.open(instanceID)
	if err != nil {
		return nil, err
	}
	return out, nil
}

// OpenPackageFile opens a package file on disk.
func OpenPackageFile(path string, instanceID string) (pkg Package, err error) {
	file, err := os.Open(path)
	if err != nil {
		return
	}
	pkg, err = OpenPackage(file, instanceID)
	if err != nil {
		file.Close()
	}
	return
}

// ExtractPackage extracts all files from a package into a destination.
func ExtractPackage(p Package, dest Destination) error {
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
	data       io.ReadSeeker
	dataSize   int64
	instanceID string
	zip        *zip.Reader
	files      []File
	manifest   Manifest
}

// open reads the package data , verifies SHA1 hash and reads manifest.
func (p *packageImpl) open(instanceID string) error {
	// Calculate SHA1 of the data to verify it matches expected instanceID.
	_, err := p.data.Seek(0, os.SEEK_SET)
	if err != nil {
		return err
	}
	hash := sha1.New()
	_, err = io.Copy(hash, p.data)
	if err != nil {
		return err
	}
	p.dataSize, err = p.data.Seek(0, os.SEEK_CUR)
	if err != nil {
		return err
	}
	calculatedSHA1 := hex.EncodeToString(hash.Sum(nil))
	if instanceID != "" && instanceID != calculatedSHA1 {
		return fmt.Errorf("Package SHA1 hash mismatch")
	}
	p.instanceID = calculatedSHA1

	// List files inside and package manifest.
	p.zip, err = zip.NewReader(&readerAt{r: p.data}, p.dataSize)
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
	return nil
}

func (p *packageImpl) Close() error {
	if p.data != nil {
		if closer, ok := p.data.(io.Closer); ok {
			closer.Close()
		}
		p.data = nil
	}
	p.dataSize = 0
	p.instanceID = ""
	p.zip = nil
	p.files = []File{}
	p.manifest = Manifest{}
	return nil
}

func (p *packageImpl) InstanceID() string        { return p.instanceID }
func (p *packageImpl) Name() string              { return p.manifest.PackageName }
func (p *packageImpl) Files() []File             { return p.files }
func (p *packageImpl) DataReader() io.ReadSeeker { return p.data }

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
