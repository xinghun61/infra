// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"bufio"
	"bytes"
	"flag"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"regexp"
	"strings"

	"infra/tricium/api/v1"
)

const (
	category = "Copyright"
)

var (
	fileWhitelist = []string{".c", ".cc", ".cpp", ".h", ".java", ".js", ".py", ".sh"}
	// A comment is any amount of whitespace followed by any of the following
	// character sets: #, //, /*, *, ;
	commentRegexp    = regexp.MustCompile(`^[ \t\n\r\v\f]*[#|\/\/|\/\*|\*|;].*`)
	whitespaceRegexp = regexp.MustCompile(`^[ \t\n\r\v\f]*$`)
	// Expected copyright statements (any year or author accepted).
	bsdCopyrightRegexp = regexp.MustCompile(`Copyright 20[0-9][0-9] ` +
		`The [A-Za-z]* Authors\. All rights reserved\. ` +
		`Use of this source code is governed by a BSD-style license ` +
		`that can be found in the LICENSE file\.`)
	mitCopyrightRegexp = regexp.MustCompile(`Copyright 20[0-9][0-9] ` +
		`The [A-Za-z]* Authors ` +
		`Use of this source code is governed by a MIT-style license ` +
		`that can be found in the LICENSE file or at ` +
		`https:\/\/opensource\.org\/licenses\/MIT`)

	// Old-style copyright with (c).
	oldCopyrightRegexp = regexp.MustCompile(`Copyright \(c\) 20[0-9][0-9] ` +
		`The [A-Za-z]* Authors. ` +
		`All rights reserved. Use of this source code is governed by ` +
		`a BSD-style license that can be found in the LICENSE file.`)
)

func main() {
	inputDir := flag.String("input", "", "Path to root of Tricium input")
	outputDir := flag.String("output", "", "Path to root of Tricium output")
	flag.Parse()
	if flag.NArg() != 0 {
		log.Fatalf("Unexpected argument.")
	}

	// Read Tricium input FILES data.
	input := &tricium.Data_Files{}
	if err := tricium.ReadDataType(*inputDir, input); err != nil {
		log.Fatalf("Failed to read FILES data: %v", err)
	}
	log.Printf("Read FILES data.")

	// Create RESULTS data.
	output := &tricium.Data_Results{}
	for _, file := range input.Files {
		if file.IsBinary {
			log.Printf("Skipping binary file %q.", file.Path)
			continue
		}
		if !isWhitelisted(file.Path) {
			log.Printf("Skipping file: %q.", file.Path)
			continue
		}
		if c := checkCopyright(filepath.Join(*inputDir, file.Path)); c != nil {
			output.Comments = append(output.Comments, c)
		}
	}

	// Write Tricium RESULTS data.
	path, err := tricium.WriteDataType(*outputDir, output)
	if err != nil {
		log.Fatalf("Failed to write RESULTS data: %v", err)
	}
	log.Printf("Wrote RESULTS data to %q.", path)
}

func isWhitelisted(path string) bool {
	for _, ext := range fileWhitelist {
		if ext == filepath.Ext(path) || ext == filepath.Base(path) {
			return true
		}
	}
	return false
}

func checkCopyright(path string) *tricium.Data_Comment {
	file, err := os.Open(path)
	if err != nil {
		log.Fatalf("Failed to open file: %v, path: %s", err, path)
	}
	defer func() {
		if err := file.Close(); err != nil {
			log.Fatalf("Failed to close file: %v, path: %s", err, path)
		}
	}()
	header := getFileHeader(path, file)
	if whitespaceRegexp.MatchString(header) {
		return missingCopyrightComment(path)
	} else if oldCopyrightRegexp.MatchString(header) {
		return oldCopyrightComment(path)
	} else if !bsdCopyrightRegexp.MatchString(header) && !mitCopyrightRegexp.MatchString(header) {
		return incorrectCopyrightComment(path)
	}
	return nil
}

func getFileHeader(path string, file *os.File) string {
	scanner := bufio.NewScanner(file)
	var header bytes.Buffer
	// While line is comment/whitespace
	for scanner.Scan() {
		text := scanner.Text()

		// If it's not a comment or whitespace, we've gone past the file header and don't care.
		if !whitespaceRegexp.MatchString(text) && !commentRegexp.MatchString(text) {
			return header.String()
		}

		// Remove any pre and post whitespace, and comment symbol.
		text = strings.TrimRight(text, " \t\n\r\v\f")
		text = strings.TrimLeft(text, " \t\n\r\v\f#/*;")

		// Add line to header string.
		header.WriteString(text)
		if text != "" {
			header.WriteString(" ")
		}

		if err := scanner.Err(); err != nil {
			log.Fatalf("Failed to read file: %v, path: %s", err, path)
		}
	}
	return header.String()
}

func missingCopyrightComment(path string) *tricium.Data_Comment {
	return &tricium.Data_Comment{
		Category: fmt.Sprintf("%s/%s", category, "Missing"),
		Message: "Missing copyright statement.\n" +
			"Use the following for BSD:\n" +
			"Copyright <year> The <group> Authors. All rights reserved.\n" +
			"Use of this source code is governed by a BSD-style license that can be\n" +
			"found in the LICENSE file.\n\n" +
			"See: https://chromium.googlesource.com/chromium/src/+/master/styleguide/c++/c++.md#file-headers\n\n" +
			"Or the following for MIT: Copyright <year> The <group> Authors\n\n" +
			"Use of this source code is governed by a MIT-style\n" +
			"license that can be found in the LICENSE file or at\n" +
			"https://opensource.org/licenses/MIT.",
		Path:      path,
		StartLine: int32(1),
		EndLine:   int32(1),
		EndChar:   int32(1),
	}
}

func incorrectCopyrightComment(path string) *tricium.Data_Comment {
	return &tricium.Data_Comment{
		Category: fmt.Sprintf("%s/%s", category, "Incorrect"),
		Message: "Incorrect copyright statement.\n" +
			"Use the following for BSD:\n" +
			"Copyright <year> The <group> Authors. All rights reserved.\n" +
			"Use of this source code is governed by a BSD-style license that can be\n" +
			"found in the LICENSE file.\n\n" +
			"See: https://chromium.googlesource.com/chromium/src/+/master/styleguide/c++/c++.md#file-headers\n\n" +
			"Or the following for MIT: Copyright <year> The <group> Authors\n\n" +
			"Use of this source code is governed by a MIT-style\n" +
			"license that can be found in the LICENSE file or at\n" +
			"https://opensource.org/licenses/MIT.",
		Path:      path,
		StartLine: int32(1),
		EndLine:   int32(1),
		EndChar:   int32(1),
	}
}

func oldCopyrightComment(path string) *tricium.Data_Comment {
	return &tricium.Data_Comment{
		Category: fmt.Sprintf("%s/%s", category, "OutOfDate"),
		Message: "Out of date copyright statement (omit the (c) to update).\n\n" +
			"See: https://chromium.googlesource.com/chromium/src/+/master/styleguide/c++/c++.md#file-headers",
		Path:      path,
		StartLine: int32(1),
		EndLine:   int32(1),
		EndChar:   int32(1),
	}
}
