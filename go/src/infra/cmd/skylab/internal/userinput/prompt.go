// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package userinput

import (
	"bufio"
	"fmt"
	"io"
	"strings"

	"go.chromium.org/luci/common/errors"
)

// CLIPrompt returns a PromptFunc to prompt user on CLI.
//
// In case of erroneous input from user, the returned PromptFunc prompts the
// user again.
// defaultResponse is returned on empty response from the user.
// In case of other system errors, the returned promptFunc returns false.
func CLIPrompt(w io.Writer, r io.Reader, defaultResponse bool) PromptFunc {
	return func(reason string) bool {
		if err := prompt(w, reason, defaultResponse); err != nil {
			return escapeHatchResponse
		}
		for {
			i, err := getPromptResponse(r)
			if err != nil {
				return escapeHatchResponse
			}
			switch i {
			case "":
				return defaultResponse
			case "y", "yes":
				return true
			case "n", "no":
				fmt.Fprintln(w, "User aborted session.")
				return false
			default:
				if err := reprompt(w, i); err != nil {
					return escapeHatchResponse
				}
			}
		}
	}
}

// escapeHatchResponse is the response from user prompt on system errors.
//
// In case of such errors, we're unable to interact with the user entirely, so
// it's best to abort the userinput session.
const escapeHatchResponse = false

func prompt(w io.Writer, reason string, defaultResponse bool) error {
	b := bufio.NewWriter(w)
	fmt.Fprintf(b, "%s\n", reason)
	fmt.Fprintf(b, "\tContinue?")
	if defaultResponse {
		fmt.Fprintf(b, " [Y/n] ")
	} else {
		fmt.Fprintf(b, " [y/N] ")
	}
	return b.Flush()
}

func getPromptResponse(r io.Reader) (string, error) {
	b := bufio.NewReader(r)
	i, err := b.ReadString('\n')
	if err != nil {
		return "", errors.Annotate(err, "get prompt response").Err()
	}
	return strings.Trim(strings.ToLower(i), " \n\t"), nil
}

func reprompt(w io.Writer, response string) error {
	b := bufio.NewWriter(w)
	fmt.Fprintf(b, "\n\tInvalid response %s. Please enter 'y' or 'n': ", response)
	return b.Flush()
}
