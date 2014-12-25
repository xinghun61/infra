// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cipd

import (
	"bytes"
	"crypto/rand"
	"crypto/rsa"
	"io"
	"io/ioutil"
	"os"
	"testing"

	"infra/tools/cipd/internal/keys"

	. "github.com/smartystreets/goconvey/convey"
)

func TestPackageReading(t *testing.T) {
	goodManifest := `{
  "FormatVersion": "1",
  "PackageName": "testing"
}`

	sign := func(pkg []byte, pkey *rsa.PrivateKey, out io.Writer) {
		sig, err := Sign(bytes.NewReader(pkg), pkey)
		So(err, ShouldBeNil)
		marshaled, err := MarshalSignatureList([]SignatureBlock{sig})
		So(err, ShouldBeNil)
		_, err = out.Write(marshaled)
		So(err, ShouldBeNil)
	}

	Convey("Open empty signed package works", t, func() {
		// Build an empty package.
		out := bytes.Buffer{}
		err := BuildPackage(BuildPackageOptions{
			Output:      &out,
			PackageName: "testing",
		})
		So(err, ShouldBeNil)

		// Sign it, append signature to the end.
		sign(out.Bytes(), privateKeyForTest(), &out)

		// Open it, it will validate the signature.
		pkg, err := OpenPackage(newPackageReaderFromBytes(out.Bytes()), testingPublicKeys)
		if pkg != nil {
			defer pkg.Close()
		}
		So(pkg, ShouldNotBeNil)
		So(err, ShouldBeNil)
		So(pkg.Signed(), ShouldBeTrue)
		So(pkg.Name(), ShouldEqual, "testing")
		So(pkg.InstanceID(), ShouldEqual, "4571652804acba0ec97c37c2257d6ac67c87baa1")
		So(len(pkg.Files()), ShouldEqual, 1)
		So(len(pkg.Signatures()), ShouldEqual, 1)

		// Contains single manifest file.
		f := pkg.Files()[0]
		So(f.Name(), ShouldEqual, ".cipdpkg/manifest.json")
		So(f.Size(), ShouldEqual, 54)
		So(f.Executable(), ShouldBeFalse)
		r, err := f.Open()
		if r != nil {
			defer r.Close()
		}
		So(err, ShouldBeNil)
		manifest, err := ioutil.ReadAll(r)
		So(err, ShouldBeNil)
		So(string(manifest), ShouldEqual, goodManifest)
	})

	Convey("Open unsigned package works", t, func() {
		// Build an empty package, do not sign it.
		out := bytes.Buffer{}
		err := BuildPackage(BuildPackageOptions{
			Output:      &out,
			PackageName: "testing",
		})
		So(err, ShouldBeNil)

		// Open it, it will skip body reading since signature is missing.
		pkg, err := OpenPackage(newPackageReaderFromBytes(out.Bytes()), testingPublicKeys)
		if pkg != nil {
			defer pkg.Close()
		}
		So(pkg, ShouldNotBeNil)
		So(err, ShouldBeNil)
		So(pkg.Signed(), ShouldBeFalse)
		So(pkg.Name(), ShouldEqual, "")
		So(pkg.InstanceID(), ShouldEqual, "4571652804acba0ec97c37c2257d6ac67c87baa1")
		So(len(pkg.Files()), ShouldEqual, 0)
	})

	Convey("Open package with unknown signatures work", t, func() {
		// Build an empty package.
		out := bytes.Buffer{}
		err := BuildPackage(BuildPackageOptions{
			Output:      &out,
			PackageName: "testing",
		})
		So(err, ShouldBeNil)

		// Sign use some random "unknown" key.
		pkey, err := rsa.GenerateKey(rand.Reader, 1024)
		So(err, ShouldBeNil)
		sign(out.Bytes(), pkey, &out)

		// Open it, it will skip body reading since signature is invalid.
		pkg, err := OpenPackage(newPackageReaderFromBytes(out.Bytes()), testingPublicKeys)
		if pkg != nil {
			defer pkg.Close()
		}
		So(pkg, ShouldNotBeNil)
		So(err, ShouldBeNil)
		So(pkg.Signed(), ShouldBeFalse)
		So(pkg.Name(), ShouldEqual, "")
		So(pkg.InstanceID(), ShouldEqual, "4571652804acba0ec97c37c2257d6ac67c87baa1")
		So(len(pkg.Files()), ShouldEqual, 0)
	})

	Convey("Open package with two signatures work", t, func() {
		// Build an empty package.
		out := bytes.Buffer{}
		err := BuildPackage(BuildPackageOptions{
			Output:      &out,
			PackageName: "testing",
		})
		So(err, ShouldBeNil)

		// Generate random key.
		pkey, err := rsa.GenerateKey(rand.Reader, 1024)
		So(err, ShouldBeNil)

		// Sign use some random "unknown" key and known key.
		sig1, err := Sign(bytes.NewReader(out.Bytes()), pkey)
		So(err, ShouldBeNil)
		sig2, err := Sign(bytes.NewReader(out.Bytes()), privateKeyForTest())
		So(err, ShouldBeNil)

		// Write both signatures.
		marshaled, err := MarshalSignatureList([]SignatureBlock{sig1, sig2})
		So(err, ShouldBeNil)
		_, err = out.Write(marshaled)
		So(err, ShouldBeNil)

		// Signed, should be readable.
		pkg, err := OpenPackage(newPackageReaderFromBytes(out.Bytes()), testingPublicKeys)
		if pkg != nil {
			defer pkg.Close()
		}
		So(pkg, ShouldNotBeNil)
		So(err, ShouldBeNil)
		So(pkg.Signed(), ShouldBeTrue)
		So(pkg.Name(), ShouldEqual, "testing")
		So(pkg.InstanceID(), ShouldEqual, "4571652804acba0ec97c37c2257d6ac67c87baa1")
		So(len(pkg.Files()), ShouldEqual, 1)
	})

	Convey("OpenPackageFile works", t, func() {
		// Open temp file.
		tempFile, err := ioutil.TempFile("", "cipdtest")
		So(err, ShouldBeNil)
		tempFilePath := tempFile.Name()
		defer os.Remove(tempFilePath)

		// Write empty package to it.
		err = BuildPackage(BuildPackageOptions{
			Output:      tempFile,
			PackageName: "testing",
		})
		So(err, ShouldBeNil)
		tempFile.Close()

		// Read back the body to sign it.
		r, err := os.Open(tempFilePath)
		So(err, ShouldBeNil)
		data, err := ioutil.ReadAll(r)
		So(err, ShouldBeNil)
		r.Close()

		// Append the signature.
		w, err := os.OpenFile(tempFilePath, os.O_WRONLY|os.O_APPEND, 0660)
		sign(data, privateKeyForTest(), w)
		w.Close()

		// Read the package.
		pkg, err := OpenPackageFile(tempFilePath, testingPublicKeys)
		if pkg != nil {
			defer pkg.Close()
		}
		So(pkg, ShouldNotBeNil)
		So(err, ShouldBeNil)
		So(pkg.Signed(), ShouldBeTrue)
	})

	Convey("ExtractPackage works", t, func() {
		// Add a bunch of files to a package.
		out := bytes.Buffer{}
		err := BuildPackage(BuildPackageOptions{
			Input: []File{
				makeTestFile("testing/qwerty", "12345", false),
				makeTestFile("abc", "duh", true),
			},
			Output:      &out,
			PackageName: "testing",
		})
		So(err, ShouldBeNil)

		// Sign the package.
		sign(out.Bytes(), privateKeyForTest(), &out)

		// Extract files.
		pkg, err := OpenPackage(newPackageReaderFromBytes(out.Bytes()), testingPublicKeys)
		if pkg != nil {
			defer pkg.Close()
		}
		So(err, ShouldBeNil)
		dest := &testDestination{}
		err = ExtractPackage(pkg, dest)
		So(err, ShouldBeNil)
		So(dest.beginCalls, ShouldEqual, 1)
		So(dest.endCalls, ShouldEqual, 1)
		So(len(dest.files), ShouldEqual, 3)

		// Verify file list, file data and flags are correct.
		names := []string{}
		for _, f := range dest.files {
			names = append(names, f.name)
		}
		So(names, ShouldResemble, []string{
			"testing/qwerty",
			"abc",
			".cipdpkg/manifest.json",
		})
		So(string(dest.files[0].Bytes()), ShouldEqual, "12345")
		So(dest.files[1].executable, ShouldBeTrue)
	})

	Convey("Extract from unsigned package doesn't work", t, func() {
		// Build an empty package, do not sign it.
		out := bytes.Buffer{}
		err := BuildPackage(BuildPackageOptions{
			Input:       []File{makeTestFile("testing/qwerty", "12345", false)},
			Output:      &out,
			PackageName: "testing",
		})
		So(err, ShouldBeNil)

		// No signature.
		pkg, err := OpenPackage(newPackageReaderFromBytes(out.Bytes()), testingPublicKeys)
		if pkg != nil {
			defer pkg.Close()
		}
		So(pkg, ShouldNotBeNil)
		So(err, ShouldBeNil)
		So(pkg.Signed(), ShouldBeFalse)
		So(pkg.Name(), ShouldEqual, "")
		So(len(pkg.Files()), ShouldEqual, 0)

		// ExtractPackage freaks out.
		err = ExtractPackage(pkg, &testDestination{})
		So(err, ShouldNotBeNil)
	})

	Convey("Package DataReader works with unsigned package", t, func() {
		// Build an empty package.
		out := bytes.Buffer{}
		err := BuildPackage(BuildPackageOptions{
			Output:      &out,
			PackageName: "testing",
		})
		So(err, ShouldBeNil)

		// Read it back in its entirety via DataReader, no signatures yet.
		pkg, err := OpenPackage(newPackageReaderFromBytes(out.Bytes()), testingPublicKeys)
		if pkg != nil {
			defer pkg.Close()
		}
		So(err, ShouldBeNil)
		r := pkg.DataReader()
		read, err := ioutil.ReadAll(r)
		So(err, ShouldBeNil)
		So(read, ShouldResemble, out.Bytes())
	})

	Convey("Package DataReader works with signed package", t, func() {
		// Build an empty package.
		out := bytes.Buffer{}
		err := BuildPackage(BuildPackageOptions{
			Output:      &out,
			PackageName: "testing",
		})
		So(err, ShouldBeNil)

		// Remember the data without the signature.
		packageData := out.Bytes()

		// Sign it, append signature to the end.
		sign(packageData, privateKeyForTest(), &out)

		// Read back package data only.
		pkg, err := OpenPackage(newPackageReaderFromBytes(out.Bytes()), testingPublicKeys)
		if pkg != nil {
			defer pkg.Close()
		}
		So(err, ShouldBeNil)
		r := pkg.DataReader()
		read, err := ioutil.ReadAll(r)
		So(err, ShouldBeNil)
		So(read, ShouldResemble, packageData)
	})
}

////////////////////////////////////////////////////////////////////////////////
// Nop readerSeekerCloser, since ioutil.NopClose works only with io.Reader,
// but not with io.ReadSeeker.

type readerSeekerCloser struct {
	io.ReadSeeker
}

func (r *readerSeekerCloser) Close() error { return nil }

func newPackageReaderFromBytes(b []byte) PackageReader {
	return &readerSeekerCloser{bytes.NewReader(b)}
}

////////////////////////////////////////////////////////////////////////////////

type testDestination struct {
	beginCalls int
	endCalls   int
	files      []*testDestinationFile
}

type testDestinationFile struct {
	bytes.Buffer
	name       string
	executable bool
}

func (d *testDestinationFile) Close() error { return nil }

func (d *testDestination) Begin() error {
	d.beginCalls++
	return nil
}

func (d *testDestination) CreateFile(name string, executable bool) (io.WriteCloser, error) {
	f := &testDestinationFile{
		name:       name,
		executable: executable,
	}
	d.files = append(d.files, f)
	return f, nil
}

func (d *testDestination) End(success bool) error {
	d.endCalls++
	return nil
}

////////////////////////////////////////////////////////////////////////////////

// testingPublicKeys is PublicKeyProvider that knows public key that corresponds
// to privateKeyForTest().
func testingPublicKeys(fingerprint string) keys.PublicKey {
	private := privateKeyForTest()
	fp, err := keys.PublicKeyFingerprint(&private.PublicKey)
	if err != nil {
		panic("Can't get fingerprint")
	}
	pem, err := keys.PublicKeyToPEM(&private.PublicKey)
	if err != nil {
		panic("Can't convert key to PEM")
	}
	if fingerprint == fp {
		return keys.PublicKey{
			Valid:       true,
			Name:        "testing/fake_key",
			Fingerprint: fp,
			PEM:         string(pem),
		}
	}
	return keys.PublicKey{}
}
