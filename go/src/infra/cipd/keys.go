// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cipd

import (
	"crypto"
	"crypto/rsa"
	_ "crypto/sha1"
	"crypto/x509"
	"encoding/hex"
	"encoding/pem"
	"fmt"
)

// publicKeyFromPEM parses PEM encoded RSA public key.
func publicKeyFromPEM(data []byte) (*rsa.PublicKey, error) {
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

// publicKeyToPEM takes rsa.PublicKey and produced PEM encoded file.
func publicKeyToPEM(k *rsa.PublicKey) ([]byte, error) {
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

// publicKeyFingerprint takes rsa.PublicKey and returns its fingerprint.
func publicKeyFingerprint(k *rsa.PublicKey) (string, error) {
	blob, err := publicKeyToPEM(k)
	if err != nil {
		return "", err
	}
	h := crypto.SHA1.New()
	h.Write(blob)
	return hex.EncodeToString(h.Sum(nil)), nil
}
