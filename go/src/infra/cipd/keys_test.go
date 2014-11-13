// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cipd

import (
	"crypto/rsa"
	"math/big"
	"strings"
	"testing"

	. "github.com/smartystreets/goconvey/convey"
)

func TestKeys(t *testing.T) {
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

	Convey("publicKeyFromPEM works", t, func() {
		key, err := publicKeyFromPEM([]byte(testKeyPEM))
		So(key, ShouldResemble, &testKey)
		So(err, ShouldBeNil)
	})

	Convey("publicKeyFromPEM rejects additional data", t, func() {
		key, err := publicKeyFromPEM([]byte(testKeyPEM + testKeyPEM))
		So(key, ShouldBeNil)
		So(err, ShouldNotBeNil)
	})

	Convey("publicKeyFromPEM rejects non PUBLIC KEY pem", t, func() {
		pem := strings.Replace(testKeyPEM, "PUBLIC KEY", "SOME KEY", 2)
		key, err := publicKeyFromPEM([]byte(pem))
		So(key, ShouldBeNil)
		So(err, ShouldNotBeNil)
	})

	Convey("publicKeyFromPEM rejects garbage", t, func() {
		key, err := publicKeyFromPEM([]byte(testKeyPEMWithGarbage))
		So(key, ShouldBeNil)
		So(err, ShouldNotBeNil)
	})

	Convey("publicKeyToPEM works", t, func() {
		pem, err := publicKeyToPEM(&testKey)
		So(pem, ShouldResemble, []byte(testKeyPEM))
		So(err, ShouldBeNil)
	})

	Convey("publicKeyFingerprint works", t, func() {
		fp, err := publicKeyFingerprint(&testKey)
		So(fp, ShouldEqual, testFingerprint)
		So(err, ShouldBeNil)
	})
}
