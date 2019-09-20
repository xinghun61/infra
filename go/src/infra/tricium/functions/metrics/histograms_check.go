// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"bufio"
	"encoding/xml"
	"flag"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"time"

	tricium "infra/tricium/api/v1"
)

const (
	category        = "Metrics"
	histogramEndTag = "</histogram>"
	ownerStartTag   = "<owner"
	dateFormat      = "2006-01-02"

	oneOwnerError = `[WARNING] It's a best practice to list multiple owners,
so that there's no single point of failure for communication:
https://chromium.googlesource.com/chromium/src/+/HEAD/tools/metrics/histograms/README.md#Owners.`
	firstOwnerTeamError = `[WARNING] Please list an individual as the primary owner for this metric:
https://chromium.googlesource.com/chromium/src/+/HEAD/tools/metrics/histograms/README.md#Owners.`
	noExpiryError = `[ERROR] Please specify an expiry condition for this histogram:
https://chromium.googlesource.com/chromium/src/+/HEAD/tools/metrics/histograms/README.md#Histogram-Expiry`
	badExpiryError = `[ERROR] Could not parse histogram expiry. Please format as YYYY-MM-DD or MXX:
https://chromium.googlesource.com/chromium/src/+/HEAD/tools/metrics/histograms/README.md#Histogram-Expiry`
	pastExpiryWarning = `[WARNING] This expiry date is in the past. Did you mean to set an expiry date in the future?`
	farExpiryWarning  = `[WARNING] It's a best practice to choose an expiry that is at most one year out:
https://chromium.googlesource.com/chromium/src/+/HEAD/tools/metrics/histograms/README.md#Histogram-Expiry`
	neverExpiryInfo = `[INFO] The expiry should only be set to \"never\" in rare cases.
Please double-check that this use of \"never\" is appropriate:
https://chromium.googlesource.com/chromium/src/+/HEAD/tools/metrics/histograms/README.md#Histogram-Expiry`
	neverExpiryError = `[ERROR] Histograms that never expire must have an XML comment describing why,
such as <!-- expires-never: \"heartbeat\" metric (internal: go/uma-heartbeats) -->:
https://chromium.googlesource.com/chromium/src/+/HEAD/tools/metrics/histograms/README.md#Histogram-Expiry`
)

var (
	// We need a pattern for matching the histogram start tag because
	// there are other tags that share the "histogram" prefix like "histogram-suffixes"
	histogramStartPattern     = regexp.MustCompile(`^<histogram(\s|>)`)
	neverExpiryCommentPattern = regexp.MustCompile(`^<!--\s?expires-never`)
	// Match date patterns of format YYYY-MM-DD
	expiryDatePattern      = regexp.MustCompile(`^[0-9]{4}-(0[1-9]|1[0-2])-(0[1-9]|[1-2][0-9]|3[0-1])$`)
	expiryMilestonePattern = regexp.MustCompile(`^M([0-9]{2,3})$`)

	// Now is an alias for time.Now, can be overwritten by tests
	now = time.Now
)

// Histogram contains all info about a UMA histogram
type Histogram struct {
	Name     string   `xml:"name,attr"`
	Enum     string   `xml:"enum,attr"`
	Units    string   `xml:"units,attr"`
	Expiry   string   `xml:"expires_after,attr"`
	Obsolete string   `xml:"obsolete"`
	Owners   []string `xml:"owner"`
	Summary  string   `xml:"summary"`
}

// Metadata contains metadata about histogram tags and required comments
type Metadata struct {
	HistogramLineNum      int
	OwnerLineNum          int
	HasNeverExpiryComment bool
}

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

	results := &tricium.Data_Results{}

	files, err := tricium.FilterFiles(input.Files, "*.xml")
	if err != nil {
		log.Fatalf("Failed to filter files: %v", err)
	}
	for _, file := range files {
		log.Printf("ANALYZING File: %s", file.Path)
		p := filepath.Join(*inputDir, file.Path)
		f := openFileOrDie(p)
		defer closeFileOrDie(f)
		results.Comments = append(results.Comments, analyzeFile(bufio.NewScanner(f), p)...)
	}

	// Write Tricium RESULTS data.
	path, err := tricium.WriteDataType(*outputDir, results)
	if err != nil {
		log.Fatalf("Failed to write RESULTS data: %v", err)
	}
	log.Printf("Wrote RESULTS data to path %q.", path)
}

func analyzeFile(scanner *bufio.Scanner, path string) []*tricium.Data_Comment {
	var comments []*tricium.Data_Comment
	// Struct that holds line numbers of different tags in histogram
	var metadata *Metadata
	// Buffer that holds current histogram
	var currHistogram []byte
	// Start line number for current histogram
	var histogramStart int
	lineNum := 1
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if currHistogram != nil {
			// Add line to currHistogram if currently between some histogram tags
			currHistogram = append(currHistogram, scanner.Bytes()...)
		}
		if histogramStartPattern.MatchString(line) {
			// Initialize currHistogram and metadata when a new histogram is encountered
			histogramStart = lineNum
			metadata = newMetadata(histogramStart)
			currHistogram = scanner.Bytes()
		} else if strings.HasPrefix(line, histogramEndTag) {
			// Analyze entire histogram after histogram end tag is encountered
			if comment := checkHistogram(path, currHistogram, metadata); comment != nil {
				comments = append(comments, comment...)
			}
			currHistogram = nil
		} else if strings.HasPrefix(line, ownerStartTag) {
			if metadata.OwnerLineNum == histogramStart {
				metadata.OwnerLineNum = lineNum
			}
		} else if neverExpiryCommentPattern.MatchString(line) {
			metadata.HasNeverExpiryComment = true
		}
		lineNum++
	}
	return comments
}

func checkHistogram(path string, histBytes []byte, metadata *Metadata) []*tricium.Data_Comment {
	var histogram Histogram
	if err := xml.Unmarshal(histBytes, &histogram); err != nil {
		log.Printf("WARNING: Failed to unmarshal histogram at line %d", metadata.HistogramLineNum)
		return nil
	}
	var comments []*tricium.Data_Comment
	if comment := checkNumOwners(path, histogram, metadata); comment != nil {
		comments = append(comments, comment)
	}
	if comment := checkNonTeamOwner(path, histogram, metadata); comment != nil {
		comments = append(comments, comment)
	}
	if expiryComments := checkExpiry(path, histogram, metadata); expiryComments != nil {
		comments = append(comments, expiryComments...)
	}
	return comments
}

func checkNumOwners(path string, histogram Histogram, metadata *Metadata) *tricium.Data_Comment {
	if len(histogram.Owners) <= 1 {
		comment := createOwnerComment(oneOwnerError, path, metadata)
		log.Printf("ADDING Comment for %s at line %d: %s", histogram.Name, comment.StartLine, "[ERROR]: One Owner")
		return comment
	}
	return nil
}

func checkNonTeamOwner(path string, histogram Histogram, metadata *Metadata) *tricium.Data_Comment {
	if len(histogram.Owners) > 0 && strings.Contains(histogram.Owners[0], "-") {
		comment := createOwnerComment(firstOwnerTeamError, path, metadata)
		log.Printf("ADDING Comment for %s at line %d: %s", histogram.Name, comment.StartLine, "[ERROR]: First Owner Team")
		return comment
	}
	return nil
}

func createOwnerComment(message string, path string, metadata *Metadata) *tricium.Data_Comment {
	return &tricium.Data_Comment{
		Category:  fmt.Sprintf("%s/%s", category, "Owners"),
		Message:   message,
		Path:      path,
		StartLine: int32(metadata.OwnerLineNum),
	}
}

func checkExpiry(path string, histogram Histogram, metadata *Metadata) []*tricium.Data_Comment {
	var commentMessage string
	var logMessage string
	var extraComment *tricium.Data_Comment
	if expiry := histogram.Expiry; expiry == "" {
		commentMessage = noExpiryError
		logMessage = "[ERROR]: No Expiry"
	} else if expiry == "never" {
		commentMessage = neverExpiryInfo
		logMessage = "[INFO]: Never Expiry"
		// Add second Tricium comment if an expiry of never has no comment
		if !metadata.HasNeverExpiryComment {
			extraComment = createExpiryComment(neverExpiryError, path, metadata)
			logMessage += " & [ERROR]: No Comment"
		}
	} else {
		dateMatch := expiryDatePattern.MatchString(expiry)
		milestoneMatch := expiryMilestonePattern.MatchString(expiry)
		if dateMatch {
			inputDate, err := time.Parse(dateFormat, expiry)
			if err != nil {
				log.Fatalf("Failed to parse expiry date")
			}
			dateDiff := int(inputDate.Sub(now()).Hours()/24) + 1
			if dateDiff <= 0 {
				commentMessage = pastExpiryWarning
				logMessage = "[WARNING]: Expiry in past"
			} else if dateDiff >= 365 {
				commentMessage = farExpiryWarning
				logMessage = "[WARNING]: Expiry past one year"
			} else {
				commentMessage = fmt.Sprintf("[INFO]: Expiry date is in %d days", dateDiff)
				logMessage = commentMessage
			}
		} else if milestoneMatch {
			// TODO: check that milestone is within time limit
		} else {
			commentMessage = badExpiryError
			logMessage = "[ERROR]: Expiry condition badly formatted"
		}
	}
	if commentMessage == "" {
		log.Fatalf("Primary expiry comment should not be empty")
	}
	expiryComments := []*tricium.Data_Comment{createExpiryComment(commentMessage, path, metadata)}
	if extraComment != nil {
		expiryComments = append(expiryComments, extraComment)
	}
	log.Printf("ADDING Comment for %s at line %d: %s", histogram.Name, metadata.HistogramLineNum, logMessage)
	return expiryComments
}

func createExpiryComment(message string, path string, metadata *Metadata) *tricium.Data_Comment {
	return &tricium.Data_Comment{
		Category:  fmt.Sprintf("%s/%s", category, "Expiry"),
		Message:   message,
		Path:      path,
		StartLine: int32(metadata.HistogramLineNum),
	}
}

func openFileOrDie(path string) *os.File {
	f, err := os.Open(path)
	if err != nil {
		log.Fatalf("Failed to open file: %v, path: %s", err, path)
	}
	return f
}

func closeFileOrDie(f *os.File) {
	if err := f.Close(); err != nil {
		log.Fatalf("Failed to close file: %v", err)
	}
}

// Constructor for creating a Metadata struct with defaultLineNum
func newMetadata(defaultLineNum int) *Metadata {
	return &Metadata{
		HistogramLineNum: defaultLineNum,
		OwnerLineNum:     defaultLineNum,
	}
}
