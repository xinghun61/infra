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
	"strings"

	tricium "infra/tricium/api/v1"
)

const (
	category        = "Metrics"
	histogramEndTag = "</histogram>"
	/* We want both of these histogram tags because there are other tags that
	share the "histogram" prefix like "histogram-suffixes" */
	histogramStartTagAtt = "<histogram "
	histogramStartTagEmp = "<histogram>"
	ownerStartTag        = "<owner"

	oneOwnerError = `It's a best practice to list multiple owners, 
	so that there's no single point of failure for communication:
	https://chromium.googlesource.com/chromium/src/+/HEAD/tools/metrics/histograms/README.md#Owners.`
	firstOwnerTeamError = `Please list an individual as the primary owner for this metric: 
	https://chromium.googlesource.com/chromium/src/+/HEAD/tools/metrics/histograms/README.md#Owners.`
)

// Histogram contains all info about a UMA histogram
type Histogram struct {
	Name       string   `xml:"name,attr"`
	Enum       string   `xml:"enum,attr"`
	Units      string   `xml:"units,attr"`
	Expiration string   `xml:"expiry,attr"`
	Obsolete   string   `xml:"obsolete"`
	Owners     []string `xml:"owner"`
	Summary    string   `xml:"summary"`
}

// LineNum will eventually contain all line nums for tags inside a histogram
type LineNum struct {
	HistogramLineNum int
	OwnerLineNum     int
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
	var tagLineNums *LineNum
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
		if strings.HasPrefix(line, histogramStartTagEmp) || strings.HasPrefix(line, histogramStartTagAtt) {
			// Initialize currHistogram and tagLineNums when a new histogram is encountered
			histogramStart = lineNum
			tagLineNums = newLineNum(histogramStart)
			currHistogram = scanner.Bytes()
		} else if strings.HasPrefix(line, histogramEndTag) {
			// Analyze entire histogram after histogram end tag is encountered
			if comment := checkHistogram(path, currHistogram, tagLineNums); comment != nil {
				comments = append(comments, comment...)
			}
			currHistogram = nil
		} else if strings.HasPrefix(line, ownerStartTag) {
			if tagLineNums.OwnerLineNum == histogramStart {
				tagLineNums.OwnerLineNum = lineNum
			}
		}
		lineNum++
	}
	return comments
}

func checkHistogram(path string, histBytes []byte, tagLineNums *LineNum) []*tricium.Data_Comment {
	var histogram Histogram
	if err := xml.Unmarshal(histBytes, &histogram); err != nil {
		log.Printf("WARNING: Failed to unmarshal histogram at line %d", tagLineNums.HistogramLineNum)
		return nil
	}
	var comments []*tricium.Data_Comment
	if comment := checkNumOwners(path, histogram, tagLineNums); comment != nil {
		comments = append(comments, comment)
	}
	if comment := checkNonTeamOwner(path, histogram, tagLineNums); comment != nil {
		comments = append(comments, comment)
	}
	return comments
}

func checkNumOwners(path string, histogram Histogram, tagLineNums *LineNum) *tricium.Data_Comment {
	if len(histogram.Owners) <= 1 {
		log.Printf("ADDING Comment for %s at line %d: One Owner", histogram.Name, tagLineNums.OwnerLineNum)
		comment := &tricium.Data_Comment{
			Category:  fmt.Sprintf("%s/%s", category, "Owners"),
			Message:   oneOwnerError,
			Path:      path,
			StartLine: int32(tagLineNums.OwnerLineNum),
		}
		return comment
	}
	return nil
}

func checkNonTeamOwner(path string, histogram Histogram, tagLineNums *LineNum) *tricium.Data_Comment {
	if len(histogram.Owners) > 0 && strings.Contains(histogram.Owners[0], "-") {
		log.Printf("ADDING Comment for %s at line %d: First Owner Team", histogram.Name, tagLineNums.OwnerLineNum)
		comment := &tricium.Data_Comment{
			Category:  fmt.Sprintf("%s/%s", category, "Owners"),
			Message:   firstOwnerTeamError,
			Path:      path,
			StartLine: int32(tagLineNums.OwnerLineNum),
		}
		return comment
	}
	return nil
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

// constructor for creating a LineNum struct with defaultLineNum
func newLineNum(defaultLineNum int) *LineNum {
	return &LineNum{
		HistogramLineNum: defaultLineNum,
		OwnerLineNum:     defaultLineNum,
	}
}
