// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cipd

import (
	"bytes"
	"crypto/rsa"
	"crypto/x509"
	"encoding/pem"
	"strings"
	"testing"

	. "github.com/smartystreets/goconvey/convey"
)

func TestPrivateKeyWorks(t *testing.T) {
	Convey("Make sure bundled test private key can be loaded", t, func() {
		k := privateKeyForTest()
		So(k, ShouldNotBeNil)
		So(k.Validate(), ShouldBeNil)
	})
}

func TestSign(t *testing.T) {
	Convey("Sign works", t, func() {
		sig, err := Sign(bytes.NewReader([]byte("123")), privateKeyForTest())
		So(err, ShouldBeNil)
		So(sig.HashAlgo, ShouldEqual, "SHA512")
		So(len(sig.Hash), ShouldEqual, sigBlockHash.New().Size())
		So(sig.SignatureAlgo, ShouldEqual, "PKCS1v15")
		So(len(sig.Signature), ShouldEqual, 128)
	})
}

func TestMarshalSignatureList(t *testing.T) {
	Convey("MarshalSignatureList empty", t, func() {
		out, err := MarshalSignatureList([]SignatureBlock{})
		So(err, ShouldBeNil)
		So(len(out), ShouldEqual, 0)
	})

	Convey("MarshalSignatureList one", t, func() {
		out, err := MarshalSignatureList([]SignatureBlock{SignatureBlock{}})
		So(err, ShouldBeNil)
		So(string(out), ShouldEqual, `-----BEGIN CIPD SIGNATURE-----
eyJIYXNoQWxnbyI6IiIsIkhhc2giOm51bGwsIlNpZ25hdHVyZUFsZ28iOiIiLCJT
aWduYXR1cmVLZXkiOiIiLCJTaWduYXR1cmUiOm51bGx9
-----END CIPD SIGNATURE-----
170`)
	})

	Convey("MarshalSignatureList two", t, func() {
		one := SignatureBlock{}
		two := SignatureBlock{HashAlgo: "AAAAAAAAA"}
		out, err := MarshalSignatureList([]SignatureBlock{one, two})
		So(err, ShouldBeNil)
		So(string(out), ShouldEqual, `-----BEGIN CIPD SIGNATURE-----
eyJIYXNoQWxnbyI6IiIsIkhhc2giOm51bGwsIlNpZ25hdHVyZUFsZ28iOiIiLCJT
aWduYXR1cmVLZXkiOiIiLCJTaWduYXR1cmUiOm51bGx9
-----END CIPD SIGNATURE-----
-----BEGIN CIPD SIGNATURE-----
eyJIYXNoQWxnbyI6IkFBQUFBQUFBQSIsIkhhc2giOm51bGwsIlNpZ25hdHVyZUFs
Z28iOiIiLCJTaWduYXR1cmVLZXkiOiIiLCJTaWduYXR1cmUiOm51bGx9
-----END CIPD SIGNATURE-----
352`)
	})
}

func TestReadSignatureList(t *testing.T) {
	Convey("With some signature block", t, func() {
		someSignatureList := []SignatureBlock{
			SignatureBlock{
				HashAlgo:      "hashAlgo",
				Hash:          []byte{1, 2, 3},
				SignatureAlgo: "signatureAlgo",
				SignatureKey:  "signatureKey",
				Signature:     []byte{4, 5, 6},
			},
			SignatureBlock{
				HashAlgo:      "hashAlgo2",
				Hash:          []byte{1, 2, 3},
				SignatureAlgo: "signatureAlgo2",
				SignatureKey:  "signatureKey2",
				Signature:     []byte{4, 5, 6},
			},
		}

		someSignatureBytes, err := MarshalSignatureList(someSignatureList)
		So(err, ShouldBeNil)

		Convey("FindSignatureList works in simple case", func() {
			// Prepare some data with attached signature block.
			out := &bytes.Buffer{}
			out.WriteString("Some data")
			out.Write(someSignatureBytes)

			// Read it back.
			sigs, offset, err := ReadSignatureList(bytes.NewReader(out.Bytes()))
			So(err, ShouldBeNil)
			So(sigs, ShouldResemble, someSignatureList)
			So(offset, ShouldEqual, len("Some data"))
		})

		Convey("FindSignatureList works in case there's no signatures in small buf", func() {
			out := &bytes.Buffer{}
			out.WriteString("abc")
			sigs, offset, err := ReadSignatureList(bytes.NewReader(out.Bytes()))
			So(err, ShouldBeNil)
			So(len(sigs), ShouldEqual, 0)
			So(offset, ShouldEqual, len(out.Bytes()))
		})

		Convey("FindSignatureList works in case there's no signatures in large buf", func() {
			out := &bytes.Buffer{}
			out.Write(bytes.Repeat([]byte("abc"), 200))
			sigs, offset, err := ReadSignatureList(bytes.NewReader(out.Bytes()))
			So(err, ShouldBeNil)
			So(len(sigs), ShouldEqual, 0)
			So(offset, ShouldEqual, len(out.Bytes()))
		})

		Convey("FindSignatureList works with good test data", func() {
			sigs, offset, err := ReadSignatureList(strings.NewReader(`abcdef-----BEGIN CIPD SIGNATURE-----
eyJIYXNoQWxnbyI6IiIsIkhhc2giOm51bGwsIlNpZ25hdHVyZUFsZ28iOiIiLCJT
aWduYXR1cmVLZXkiOiIiLCJTaWduYXR1cmUiOm51bGx9
-----END CIPD SIGNATURE-----
170`))
			So(err, ShouldBeNil)
			So(sigs, ShouldResemble, []SignatureBlock{SignatureBlock{}})
			So(offset, ShouldEqual, 6)
		})

		Convey("FindSignatureList works with missing offset footer", func() {
			_, _, err := ReadSignatureList(strings.NewReader(`abcdef-----BEGIN CIPD SIGNATURE-----
eyJIYXNoQWxnbyI6IiIsIkhhc2giOm51bGwsIlNpZ25hdHVyZUFsZ28iOiIiLCJT
aWduYXR1cmVLZXkiOiIiLCJTaWduYXR1cmUiOm51bGx9
-----END CIPD SIGNATURE-----
`))
			So(err, ShouldNotBeNil)
		})

		Convey("FindSignatureList works with bad offset footer: not an int", func() {
			_, _, err := ReadSignatureList(strings.NewReader(`abcdef-----BEGIN CIPD SIGNATURE-----
eyJIYXNoQWxnbyI6IiIsIkhhc2giOm51bGwsIlNpZ25hdHVyZUFsZ28iOiIiLCJT
aWduYXR1cmVLZXkiOiIiLCJTaWduYXR1cmUiOm51bGx9
-----END CIPD SIGNATURE-----
blah`))
			So(err, ShouldNotBeNil)
		})

		Convey("FindSignatureList works with bad offset footer: too large", func() {
			_, _, err := ReadSignatureList(strings.NewReader(`abcdef-----BEGIN CIPD SIGNATURE-----
eyJIYXNoQWxnbyI6IiIsIkhhc2giOm51bGwsIlNpZ25hdHVyZUFsZ28iOiIiLCJT
aWduYXR1cmVLZXkiOiIiLCJTaWduYXR1cmUiOm51bGx9
-----END CIPD SIGNATURE-----
500`))
			So(err, ShouldNotBeNil)
		})

		Convey("FindSignatureList works with bad offset footer: large, but not very", func() {
			_, _, err := ReadSignatureList(strings.NewReader(`abcdef-----BEGIN CIPD SIGNATURE-----
eyJIYXNoQWxnbyI6IiIsIkhhc2giOm51bGwsIlNpZ25hdHVyZUFsZ28iOiIiLCJT
aWduYXR1cmVLZXkiOiIiLCJTaWduYXR1cmUiOm51bGx9
-----END CIPD SIGNATURE-----
171`))
			So(err, ShouldNotBeNil)
		})

		Convey("FindSignatureList works with bad offset footer: a bit smaller", func() {
			_, _, err := ReadSignatureList(strings.NewReader(`abcdef-----BEGIN CIPD SIGNATURE-----
eyJIYXNoQWxnbyI6IiIsIkhhc2giOm51bGwsIlNpZ25hdHVyZUFsZ28iOiIiLCJT
aWduYXR1cmVLZXkiOiIiLCJTaWduYXR1cmUiOm51bGx9
-----END CIPD SIGNATURE-----
169`))
			So(err, ShouldNotBeNil)
		})

		Convey("FindSignatureList works with bad offset footer: negative", func() {
			_, _, err := ReadSignatureList(strings.NewReader(`abcdef-----BEGIN CIPD SIGNATURE-----
eyJIYXNoQWxnbyI6IiIsIkhhc2giOm51bGwsIlNpZ25hdHVyZUFsZ28iOiIiLCJT
aWduYXR1cmVLZXkiOiIiLCJTaWduYXR1cmUiOm51bGx9
-----END CIPD SIGNATURE-----
-10`))
			So(err, ShouldNotBeNil)
		})

		Convey("FindSignatureList works with wrong PEM footer", func() {
			_, _, err := ReadSignatureList(strings.NewReader(`abcdef-----BEGIN XXXX SIGNATURE-----
eyJIYXNoQWxnbyI6IiIsIkhhc2giOm51bGwsIlNpZ25hdHVyZUFsZ28iOiIiLCJT
aWduYXR1cmVLZXkiOiIiLCJTaWduYXR1cmUiOm51bGx9
-----END CIPD SIGNATURE-----
170`))
			So(err, ShouldNotBeNil)
		})

		Convey("FindSignatureList works with corrupted PEM", func() {
			_, _, err := ReadSignatureList(strings.NewReader(`abcdef-----BEGIN CIPD SIGNATURE-----
eyJIYXaoQWxnbyI6IiIsIkhhc2giOm51bGwsIlNpZ25hdHVyZUFsZ28iOiIiLCJT
aWduYXR1cmVLZXkiOiIiLCJTaWduYXR1cmUiO-------
-----END CIPD SIGNATURE-----
170`))
			So(err, ShouldNotBeNil)
		})

		Convey("FindSignatureList works with corrupted PEM", func() {
			_, _, err := ReadSignatureList(strings.NewReader(`abcdef-----BEGIN CIPD SIGNATURE-----
eyJIYXaoQWxnbyI6IiIsIkhhc2giOm51bGwsIlNpZ25hdHVyZUFsZ28iOiIiLCJT
aWduYXR1cmVLZXkiOiIiLCJTaWduYXR1cmUiO-------
-----END CIPD SIGNATURE-----
170`))
			So(err, ShouldNotBeNil)
		})

		Convey("FindSignatureList works with wrong PEM type", func() {
			_, _, err := ReadSignatureList(strings.NewReader(`abcdef-----BEGIN CIPD SIGNATURE-----
eyJIYXNoQWxnbyI6IiIsIkhhc2giOm51bGwsIlNpZ25hdHVyZUFsZ28iOiIiLCJT
aWduYXR1cmVLZXkiOiIiLCJTaWduYXR1cmUiOm51bGx9
-----END CIPD SIGNATURE-----
-----BEGIN XXXX SIGNATURE-----
eyJIYXNoQWxnbyI6IkFBQUFBQUFBQSIsIkhhc2giOm51bGwsIlNpZ25hdHVyZUFs
Z28iOiIiLCJTaWduYXR1cmVLZXkiOiIiLCJTaWduYXR1cmUiOm51bGx9
-----END XXXX SIGNATURE-----
-----BEGIN CIPD SIGNATURE-----
eyJIYXNoQWxnbyI6IkFBQUFBQUFBQSIsIkhhc2giOm51bGwsIlNpZ25hdHVyZUFs
Z28iOiIiLCJTaWduYXR1cmVLZXkiOiIiLCJTaWduYXR1cmUiOm51bGx9
-----END CIPD SIGNATURE-----
534`))
			So(err, ShouldNotBeNil)
		})

		Convey("FindSignatureList works with non PEM inside", func() {
			_, _, err := ReadSignatureList(strings.NewReader(`abcdef-----BEGIN CIPD SIGNATURE-----
eyJIYXNoQWxnbyI6IiIsIkhhc2giOm51bGwsIlNpZ25hdHVyZUFsZ28iOiIiLCJT
aWduYXR1cmVLZXkiOiIiLCJTaWduYXR1cmUiOm51bGx9
-----END CIPD SIGNATURE-----
sneaky
-----BEGIN CIPD SIGNATURE-----
eyJIYXNoQWxnbyI6IkFBQUFBQUFBQSIsIkhhc2giOm51bGwsIlNpZ25hdHVyZUFs
Z28iOiIiLCJTaWduYXR1cmVLZXkiOiIiLCJTaWduYXR1cmUiOm51bGx9
-----END CIPD SIGNATURE-----
359`))
			So(err, ShouldNotBeNil)
		})
	})
}

////////////////////////////////////////////////////////////////////////////////

// 1024bit RSA private key, just for testing.
// Generated by 'openssl genrsa -out private.pem 1024'
var pkey = `-----BEGIN RSA PRIVATE KEY-----
MIICXgIBAAKBgQDNUJYDD/cLzIpCbEHyCRWCWaYajI5thLviKDHJoBjjQZdzGy/k
lIGYTTDyXCC8XNtmDBfZaV1gMj5SZAtNMbarvWyUtek++pE8ZoOhyO/sy6P652Fb
stcZn+UbO6x8JFI12mjUHn9vLzeo90cFpedP60WZqyK025thWaZJO3LghQIDAQAB
AoGBAMPajM9tClhaDMXiKWIuYjNPO5F15WP5y5SojR3uN++JoWRvWdduBtX3RKrd
UWj+F1iYTqPZy/Y415SW1OUVeE9SPo7yw21Y893Lxioahzeo2TMg+5dqskJ0T6OX
lSsgCwM02q/r3g3rJjIqC6hJPRtUXUlrlbgsgFJCKikmC4ZdAkEA/SC6W5sZVUMz
LS43K1H76K5UGeOEC2FwrU2xnCkpkgh+wH3Eql8UeK1PngjercYO9OcwzYt1K+mp
EpsUJ2dwEwJBAM+k+Sc2OnZq4aX6tg2NrvmZzJ031aeXi2WGviHoTK6fvmHrRSbU
12fVB7+yk6CjDy/mQAtQUXHmfdqRivrf8AcCQQDHmW0aGx1IzGqob871C/rWKdEL
cQqIZteQ8Lji6Nps2uIIK6ROrBbaad9kQJ5G7OySVVN4YUWN0PyPPVYRFFGdAkEA
jDjLLIi5aDh7U1wATxzL+bC79bu746Y6M4CPq1Q1XINxzKxVkYiQQoUg63qLqSIU
YnNp8nn11iYh/VTl9s79RwJAaiWtkA5HoiO53RKVTCmO/te1F9TzBvda7z2jGiqF
KcrJ5HlhilaBDv4VcFjbI20V82ZrymlWgjAUq0xoixNIdg==
-----END RSA PRIVATE KEY-----`

var cachedPrivateKeyForTest *rsa.PrivateKey

// privateKeyForTest returns RSA private key to use in tests.
func privateKeyForTest() *rsa.PrivateKey {
	if cachedPrivateKeyForTest == nil {
		block, rest := pem.Decode([]byte(pkey))
		if len(rest) != 0 {
			panic("PEM should have one block only")
		}
		if block.Type != "RSA PRIVATE KEY" {
			panic("Expecting RSA PRIVATE KEY")
		}
		var err error
		cachedPrivateKeyForTest, err = x509.ParsePKCS1PrivateKey(block.Bytes)
		if err != nil {
			panic("Failed to parse RSA key")
		}
	}
	return cachedPrivateKeyForTest
}
