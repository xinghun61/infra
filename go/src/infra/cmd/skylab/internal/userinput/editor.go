// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package userinput

import (
	"io/ioutil"
	"os"
	"os/exec"

	"go.chromium.org/luci/common/errors"
)

// textEditorInput gets text input from user using a text editor.
//
// - Initial text is provided to the user in their favourite EDITOR.
// - The user may edit and save this text. Eventually the user quits the
//   EDITOR.
// - The resulting text is returned.
//
// name is the basename of the temporary file created.
func textEditorInput(initial []byte, name string) ([]byte, error) {
	p, err := writeTempFile(initial, name)
	if err != nil {
		return nil, errors.Annotate(err, "text editor").Err()
	}
	defer os.Remove(p)

	c := editorCmd(p)
	if err := c.Run(); err != nil {
		return nil, errors.Annotate(err, "text editor").Err()
	}
	return ioutil.ReadFile(p)
}

// writeTempFile writes a new temporary file with the given data and returns
// the path to the new file.
//
// On successful return, caller is responsible for deleting the created temporary file.
func writeTempFile(data []byte, name string) (string, error) {
	f, err := ioutil.TempFile("", name)
	if err != nil {
		return "", errors.Annotate(err, "write temp file").Err()
	}
	defer f.Close()

	if _, err := f.Write(data); err != nil {
		os.Remove(f.Name())
		return "", errors.Annotate(err, "write temp file").Err()
	}
	return f.Name(), nil
}

// defaultEditor is an editor that is likely to exist on all users' system.
const defaultEditor = "nano"

func editorCmd(filePath string) *exec.Cmd {
	p := os.Getenv("EDITOR")
	if p == "" {
		p = defaultEditor
	}

	c := exec.Command(p, filePath)
	c.Stdin = os.Stdin
	c.Stdout = os.Stdout
	c.Stderr = os.Stderr
	return c
}
