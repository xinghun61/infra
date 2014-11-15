// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/*
Package infra.cipd.internal.keys contains hardcoded RSA public keys used to
validate signatures of packages or replies from a server.

There are two set of keys: testing and release. Testing keys are used when
building cipd by default and their corresponding private keys are committed into
the repo for any developer to use. Testing keys should be used only during
development.

Release keys are used when cipd is built with '+release' build tag. Private keys
are kept secret.
*/
package keys

import (
	"crypto"
	"crypto/rsa"
	_ "crypto/sha1"
	"crypto/x509"
	"encoding/hex"
	"encoding/pem"
	"fmt"
)

// TODO: Support public keys fetched from a server.

// PublicKey defines PEM encoded RSA public key that can be used to verify
// a signature.
type PublicKey struct {
	Valid       bool
	Name        string
	Fingerprint string
	PEM         string
}

// KnownPublicKey returns a hardcoded public key given its fingerprint.
func KnownPublicKey(fingerprint string) PublicKey {
	for _, k := range publicKeys {
		if k.Fingerprint == fingerprint {
			return k
		}
	}
	return PublicKey{}
}

// KeysetName returns name of the keys set hardcoded into the binary. It should
// be "testing" or "release".
func KeysetName() string {
	return keysetName
}

// PublicKeyFromPEM parses PEM encoded RSA public key.
func PublicKeyFromPEM(data []byte) (*rsa.PublicKey, error) {
	block, rest := pem.Decode(data)
	if len(rest) != 0 {
		return nil, fmt.Errorf("PEM should have one block only")
	}
	if block.Type != "PUBLIC KEY" {
		return nil, fmt.Errorf("Expecting PUBLIC KEY got %s instead", block.Type)
	}
	key, err := x509.ParsePKIXPublicKey(block.Bytes)
	if err != nil {
		return nil, err
	}
	pubKey, ok := key.(*rsa.PublicKey)
	if !ok {
		return nil, fmt.Errorf("Expecting RSA public key")
	}
	return pubKey, nil
}

// PublicKeyToPEM takes rsa.PublicKey and produced PEM encoded file.
func PublicKeyToPEM(k *rsa.PublicKey) ([]byte, error) {
	der, err := x509.MarshalPKIXPublicKey(k)
	if err != nil {
		return nil, err
	}
	out := pem.EncodeToMemory(&pem.Block{
		Type:  "PUBLIC KEY",
		Bytes: der,
	})
	return out, nil
}

// PublicKeyFingerprint takes rsa.PublicKey and returns its fingerprint.
func PublicKeyFingerprint(k *rsa.PublicKey) (string, error) {
	blob, err := PublicKeyToPEM(k)
	if err != nil {
		return "", err
	}
	h := crypto.SHA1.New()
	h.Write(blob)
	return hex.EncodeToString(h.Sum(nil)), nil
}

// CheckRSASignature verifies the signature on a given digest.
func CheckRSASignature(publicKey *PublicKey, hash crypto.Hash, digest []byte, sig []byte) bool {
	if !publicKey.Valid {
		return false
	}
	key, err := PublicKeyFromPEM([]byte(publicKey.PEM))
	if err != nil {
		return false
	}
	err = rsa.VerifyPKCS1v15(key, hash, digest, sig)
	if err != nil {
		return false
	}
	return true
}
