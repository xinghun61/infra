// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// TODO(sergeyberezin): delete when importing dhcp configs is not
// needed anymore.  This parser is not robust at all, it's designed
// for a one-shot migration.
package main

import (
	"bufio"
	"flag"
	"fmt"
	"os"
	"strings"

	"infra/crimson/cmd/cmdhelper"
	crimson "infra/crimson/proto"
)

func readDhcpFile(file *os.File, bootClass, site string) (crimson.HostList, error) {
	var hosts crimson.HostList

	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		text := strings.TrimSpace(scanner.Text())
		switch {
		case len(text) == 0:
			continue
		case strings.HasPrefix(text, "#"):
			continue
		case !strings.HasPrefix(text, "host"):
			continue
		}
		fields := strings.Fields(text)
		if len(fields) < 13 {
			fmt.Fprintf(os.Stderr, "WARNING: skipping '%s'\n", text)
			continue
		}
		host := crimson.Host{
			Hostname:  fields[1],
			Ip:        strings.TrimRight(fields[7], ";"),
			MacAddr:   strings.TrimRight(fields[5], ";"),
			BootClass: bootClass,
			Site:      site}

		// Consistency checks
		if host.Hostname != strings.Trim(fields[9], `";`) {
			fmt.Fprintf(os.Stderr, "WARNING: inconsistent hostname, using %s: '%s'\n",
				host.Hostname, text)
		}
		if host.Hostname != strings.Trim(fields[12], `";}`) {
			fmt.Fprintf(os.Stderr, "WARNING: inconsistent hostname, using %s: '%s'\n",
				host.Hostname, text)
		}
		hosts.Hosts = append(hosts.Hosts, &host)
	}
	return hosts, scanner.Err()
}

func readDhcpFileByName(file, bootClass, site string) (hosts crimson.HostList, err error) {
	fh, err := os.Open(file)
	if err != nil {
		return
	}
	defer fh.Close()
	return readDhcpFile(fh, bootClass, site)
}

func usage() {
	fmt.Fprintf(os.Stderr,
		"Usage: %s -boot-class <class> -site <site> <file1> [<file2> ...]\n"+
			" where <file*> is a dhcp-*-hosts file\n",
		os.Args[0])
	os.Exit(1)
}

func main() {
	var bootClass, site string
	var skipHeader bool

	flag.StringVar(&bootClass, "boot-class", "",
		"Boot class for all imported hosts")
	flag.StringVar(&site, "site", "", "Site name for all imported hosts")
	flag.BoolVar(&skipHeader, "skip-header", false,
		"Do not print column names as the first row")

	flag.Parse()
	files := flag.Args()

	var missingFlags []string

	if len(files) == 0 {
		missingFlags = append(missingFlags, "at least one input file name")
	}
	if bootClass == "" {
		missingFlags = append(missingFlags, "-boot-class")
	}
	if site == "" {
		missingFlags = append(missingFlags, "-site")
	}
	if len(missingFlags) > 0 {
		fmt.Fprintln(os.Stderr, "Missing required parameter(s):")
		for _, f := range missingFlags {
			fmt.Fprintln(os.Stderr, "  ", f)
		}
		usage()
	}

	var hosts crimson.HostList

	for _, file := range files {
		fmt.Fprintf(os.Stderr, "Importing %s...\n", file)
		entries, err := readDhcpFileByName(file, bootClass, site)
		if err != nil {
			fmt.Fprintf(os.Stderr, "ERROR reading %s: %s. Skipping this file.", file, err)
		} else {
			hosts.Hosts = append(hosts.Hosts, entries.Hosts...)
		}
	}
	fmt.Fprintln(os.Stderr, "Importing finished.")

	var csvFormat cmdhelper.FormatType
	csvFormat.Set("csv")
	cmdhelper.PrintHostList(&hosts, csvFormat, skipHeader)
}
