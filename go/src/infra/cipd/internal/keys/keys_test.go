// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package keys

import (
	"crypto/rsa"
	"math/big"
	"strings"
	"testing"

	. "github.com/smartystreets/goconvey/convey"
)

func TestKeyGetters(t *testing.T) {
	// TODO: this test is not concurrently safe, it modifies global 'publicKeys'.
	Convey("Given a fake key set", t, func() {
		origKeys := publicKeys
		publicKeys = []PublicKey{
			PublicKey{
				Valid:       true,
				Name:        "fake",
				Fingerprint: "abcd",
				PEM:         "",
			},
		}
		origName := keysetName
		keysetName = "unit test"
		Reset(func() {
			publicKeys = origKeys
			keysetName = origName
		})

		Convey("KnownPublicKey finds a key", func() {
			key := KnownPublicKey("abcd")
			So(key, ShouldResemble, publicKeys[0])
		})

		Convey("KnownPublicKey doesn't find a key", func() {
			key := KnownPublicKey("missing")
			So(key.Valid, ShouldBeFalse)
		})

		Convey("KeysetName works", func() {
			So(KeysetName(), ShouldEqual, "unit test")
		})
	})
}

func TestFingerprints(t *testing.T) {
	Convey("Verify hardcoded fingerprints are correct", t, func() {
		for _, k := range publicKeys {
			pk, err := PublicKeyFromPEM([]byte(k.PEM))
			So(err, ShouldBeNil)
			fp, err := PublicKeyFingerprint(pk)
			So(err, ShouldBeNil)
			So(k.Fingerprint, ShouldEqual, fp)
		}
	})
}

func TestPEMEncoding(t *testing.T) {
	// 256 bit key generated with rsa.GenerateKey.
	testKey := rsa.PublicKey{
		N: new(big.Int),
		E: 65537,
	}
	testKey.N.SetString("90039878730443641739427612723097259966477000457155816752429128861050545410677", 10)

	// Same key as a PEM string.
	testKeyPEM := `-----BEGIN PUBLIC KEY-----
MDwwDQYJKoZIhvcNAQEBBQADKwAwKAIhAMcQw+/w7KQ9xYUQwxqdUeT6rhyDWudT
UFzBFAy3uJJ1AgMBAAE=
-----END PUBLIC KEY-----
`

	// Fingerprint of that key.
	testFingerprint := "31a49d219561318c7ad8e193906754c6633fb367"

	// A key with some random garbage inside.
	testKeyPEMWithGarbage := `-----BEGIN PUBLIC KEY-----
MDwwDQYJKoZIhvcNAQEBBQA00000000000000000000000UQwxqdUeT6rhyDWudT
UFzBFAy3uJJ1AgMBAAE=
-----END PUBLIC KEY-----
`

	Convey("PublicKeyFromPEM works", t, func() {
		key, err := PublicKeyFromPEM([]byte(testKeyPEM))
		So(key, ShouldResemble, &testKey)
		So(err, ShouldBeNil)
	})

	Convey("PublicKeyFromPEM rejects additional data", t, func() {
		key, err := PublicKeyFromPEM([]byte(testKeyPEM + testKeyPEM))
		So(key, ShouldBeNil)
		So(err, ShouldNotBeNil)
	})

	Convey("PublicKeyFromPEM rejects non PUBLIC KEY pem", t, func() {
		pem := strings.Replace(testKeyPEM, "PUBLIC KEY", "SOME KEY", 2)
		key, err := PublicKeyFromPEM([]byte(pem))
		So(key, ShouldBeNil)
		So(err, ShouldNotBeNil)
	})

	Convey("PublicKeyFromPEM rejects garbage", t, func() {
		key, err := PublicKeyFromPEM([]byte(testKeyPEMWithGarbage))
		So(key, ShouldBeNil)
		So(err, ShouldNotBeNil)
	})

	Convey("PublicKeyToPEM works", t, func() {
		pem, err := PublicKeyToPEM(&testKey)
		So(pem, ShouldResemble, []byte(testKeyPEM))
		So(err, ShouldBeNil)
	})

	Convey("PublicKeyFingerprint works", t, func() {
		fp, err := PublicKeyFingerprint(&testKey)
		So(fp, ShouldEqual, testFingerprint)
		So(err, ShouldBeNil)
	})
}
