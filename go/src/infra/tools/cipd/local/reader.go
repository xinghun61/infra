// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package local

import (
	"archive/zip"
	"crypto/sha1"
	"encoding/hex"
	"fmt"
	"io"
	"io/ioutil"
	"os"

	"infra/tools/cipd/common"
)

// PackageInstance represents a binary package file.
type PackageInstance interface {
	// Close shuts down the package and its data provider.
	Close() error
	// Pin identifies package name and concreted package instance ID of this package file.
	Pin() common.Pin
	// Files returns a list of files inside the package.
	Files() []File
	// DataReader returns reader that reads raw package data.
	DataReader() io.ReadSeeker
}

// OpenInstance verifies package SHA1 hash (instanceID if not empty string) and
// prepares a package instance for extraction. If the call succeeds,
// PackageInstance takes ownership of io.ReadSeeker. If it also implements
// io.Closer, it will be closed when package.Close() is called. If an error is
// returned, io.ReadSeeker remains unowned and caller is responsible for closing
// it (if required).
func OpenInstance(r io.ReadSeeker, instanceID string) (PackageInstance, error) {
	out := &packageInstance{data: r}
	err := out.open(instanceID)
	if err != nil {
		return nil, err
	}
	return out, nil
}

// OpenInstanceFile opens a package instance file on disk.
func OpenInstanceFile(path string, instanceID string) (inst PackageInstance, err error) {
	file, err := os.Open(path)
	if err != nil {
		return
	}
	inst, err = OpenInstance(file, instanceID)
	if err != nil {
		file.Close()
	}
	return
}

// ExtractInstance extracts all files from a package instance into a destination.
func ExtractInstance(inst PackageInstance, dest Destination) error {
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
	extractRegularFile := func(f File) error {
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

	extractSymlinkFile := func(f File) error {
		target, err := f.SymlinkTarget()
		if err != nil {
			return err
		}
		return dest.CreateSymlink(f.Name(), target)
	}

	files := inst.Files()
	for _, f := range files {
		if f.Symlink() {
			err = extractSymlinkFile(f)
		} else {
			err = extractRegularFile(f)
		}
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
// PackageInstance implementation.

type packageInstance struct {
	data       io.ReadSeeker
	dataSize   int64
	instanceID string
	zip        *zip.Reader
	files      []File
	manifest   Manifest
}

// open reads the package data , verifies SHA1 hash and reads manifest.
func (inst *packageInstance) open(instanceID string) error {
	// Calculate SHA1 of the data to verify it matches expected instanceID.
	_, err := inst.data.Seek(0, os.SEEK_SET)
	if err != nil {
		return err
	}
	hash := sha1.New()
	_, err = io.Copy(hash, inst.data)
	if err != nil {
		return err
	}
	inst.dataSize, err = inst.data.Seek(0, os.SEEK_CUR)
	if err != nil {
		return err
	}
	calculatedSHA1 := hex.EncodeToString(hash.Sum(nil))
	if instanceID != "" && instanceID != calculatedSHA1 {
		return fmt.Errorf("Package SHA1 hash mismatch")
	}
	inst.instanceID = calculatedSHA1

	// List files inside and package manifest.
	inst.zip, err = zip.NewReader(&readerAt{r: inst.data}, inst.dataSize)
	if err != nil {
		return err
	}
	inst.files = make([]File, len(inst.zip.File))
	for i, zf := range inst.zip.File {
		inst.files[i] = &fileInZip{z: zf}
		if inst.files[i].Name() == manifestName {
			inst.manifest, err = readManifestFile(inst.files[i])
			if err != nil {
				return err
			}
		}
	}
	return nil
}

func (inst *packageInstance) Close() error {
	if inst.data != nil {
		if closer, ok := inst.data.(io.Closer); ok {
			closer.Close()
		}
		inst.data = nil
	}
	inst.dataSize = 0
	inst.instanceID = ""
	inst.zip = nil
	inst.files = []File{}
	inst.manifest = Manifest{}
	return nil
}

func (inst *packageInstance) Pin() common.Pin {
	return common.Pin{
		PackageName: inst.manifest.PackageName,
		InstanceID:  inst.instanceID,
	}
}

func (inst *packageInstance) Files() []File             { return inst.files }
func (inst *packageInstance) DataReader() io.ReadSeeker { return inst.data }

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

func (f *fileInZip) Name() string  { return f.z.Name }
func (f *fileInZip) Symlink() bool { return (f.z.Mode() & os.ModeSymlink) != 0 }

func (f *fileInZip) Executable() bool {
	if f.Symlink() {
		return false
	}
	return (f.z.Mode() & 0100) != 0
}

func (f *fileInZip) Size() uint64 {
	if f.Symlink() {
		return 0
	}
	return f.z.UncompressedSize64
}

func (f *fileInZip) SymlinkTarget() (string, error) {
	if !f.Symlink() {
		return "", fmt.Errorf("Not a symlink: %s", f.Name())
	}
	r, err := f.z.Open()
	if err != nil {
		return "", err
	}
	defer r.Close()
	data, err := ioutil.ReadAll(r)
	if err != nil {
		return "", err
	}
	return string(data), nil
}

func (f *fileInZip) Open() (io.ReadCloser, error) {
	if f.Symlink() {
		return nil, fmt.Errorf("Opening a symlink is not allowed: %s", f.Name())
	}
	return f.z.Open()
}

////////////////////////////////////////////////////////////////////////////////
// ReaderAt implementation via ReadSeeker. Not concurrency safe, moves file
// pointer around without any locking. Works OK in the context of OpenInstance
// function though (where OpenInstance takes sole ownership of io.ReadSeeker).

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
