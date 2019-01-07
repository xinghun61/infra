// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Command bqupload inserts rows in a BigQuery table.
//
// It is a lightweight alternative to 'bq insert' command from gcloud SDK.
//
// Inserts the records formatted as newline delimited JSON from file into
// the specified table. If file is not specified, reads from stdin. If there
// were any insert errors it prints the errors to stderr.
//
// Usage:
//    bqupload <project>.<dataset>.<table> [<file>]
package main

import (
	"bufio"
	"context"
	"crypto/rand"
	"encoding/base64"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"os"
	"strings"

	"cloud.google.com/go/bigquery"
	"golang.org/x/oauth2"
	"google.golang.org/api/option"

	"go.chromium.org/luci/auth"
	"go.chromium.org/luci/auth/client/authcli"
	"go.chromium.org/luci/common/data/rand/mathrand"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/logging/gologger"

	"go.chromium.org/luci/hardcoded/chromeinfra"
)

const userAgent = "bqupload v1.1"

func usage() {
	fmt.Fprintf(os.Stderr,
		`%s

Usage: bqupload <project>.<dataset>.<table> [<file>]

Inserts the records formatted as newline delimited JSON from file into
the specified table. If file is not specified, reads from stdin. If there
were any insert errors it prints the errors to stderr.

Optional flags:
`, userAgent)
	flag.PrintDefaults()
}

func main() {
	flag.CommandLine.Usage = usage
	mathrand.SeedRandomly()
	if err := run(gologger.StdConfig.Use(context.Background())); err != nil {
		fmt.Fprintf(os.Stderr, "bqupload: %s\n", err)
		os.Exit(1)
	}
}

type uploadOpts struct {
	project string
	dataset string
	table   string

	input        io.Reader
	auth         oauth2.TokenSource
	insertIDBase string

	ignoreUnknownValues bool
	skipInvalidRows     bool
}

func run(ctx context.Context) error {
	// BQ options.
	bqOpts := uploadOpts{}
	flag.BoolVar(&bqOpts.ignoreUnknownValues, "ignore-unknown-values", false,
		"Ignore any values in a row that are not present in the schema.")
	flag.BoolVar(&bqOpts.skipInvalidRows, "skip-invalid-rows", false,
		"Attempt to insert any valid rows, even if invalid rows are present.")

	// Auth options.
	defaults := chromeinfra.DefaultAuthOptions()
	defaults.Scopes = []string{
		"https://www.googleapis.com/auth/bigquery",
		"https://www.googleapis.com/auth/userinfo.email",
	}
	authFlags := authcli.Flags{}
	authFlags.Register(flag.CommandLine, defaults)

	flag.Parse()

	// Parse positional flags.
	args := flag.Args()
	if len(args) == 0 || len(args) > 2 {
		usage()
		os.Exit(2)
	}

	var err error
	bqOpts.project, bqOpts.dataset, bqOpts.table, err = parseTableRef(args[0])
	if err != nil {
		return err
	}

	bqOpts.input = os.Stdin
	if len(args) > 1 {
		f, err := os.Open(args[1])
		if err != nil {
			return err
		}
		defer f.Close()
		bqOpts.input = f
	}

	// Prepare random prefix to use for insert IDs uploaded by this process.
	rnd := make([]byte, 12)
	if _, err := rand.Read(rnd); err != nil {
		return err
	}
	bqOpts.insertIDBase = base64.RawURLEncoding.EncodeToString(rnd)

	// Get oauth2.TokenSource based on parsed auth flags.
	authOpts, err := authFlags.Options()
	if err != nil {
		return err
	}
	authenticator := auth.NewAuthenticator(ctx, auth.SilentLogin, authOpts)
	bqOpts.auth, err = authenticator.TokenSource()
	if err != nil {
		if err == auth.ErrLoginRequired {
			fmt.Fprintf(os.Stderr, "You need to login first by running:\n")
			fmt.Fprintf(os.Stderr, "  luci-auth login -scopes %q\n", strings.Join(defaults.Scopes, " "))
		}
		return err
	}

	// Report who we are running as, helps when debugging permissions. Carry on
	// on errors (there shouldn't be any anyway).
	email, err := authenticator.GetEmail()
	if err != nil {
		logging.Warningf(ctx, "Can't get an email of the active account - %s", err)
	} else {
		logging.Infof(ctx, "Running as %s", email)
	}

	return upload(ctx, &bqOpts)
}

func parseTableRef(ref string) (project, dataset, table string, err error) {
	chunks := strings.Split(ref, ".")
	if len(chunks) != 3 {
		err = fmt.Errorf("table reference should have form <project>.<dataset>.<table>, got %q", ref)
		return
	}
	return chunks[0], chunks[1], chunks[2], nil
}

func upload(ctx context.Context, opts *uploadOpts) error {
	client, err := bigquery.NewClient(ctx, opts.project,
		option.WithTokenSource(opts.auth),
		option.WithUserAgent(userAgent))
	if err != nil {
		return err
	}
	defer client.Close()

	inserter := client.Dataset(opts.dataset).Table(opts.table).Inserter()
	inserter.IgnoreUnknownValues = opts.ignoreUnknownValues
	inserter.SkipInvalidRows = opts.skipInvalidRows

	// Note: we may potentially read rows from 'input' and upload them at the same
	// time for true streaming uploads in case 'input' is stdin and it's produced
	// on the fly. This is not trivial though and isn't needed yet, so we read
	// everything at once.
	rows, err := readInput(opts.input, opts.insertIDBase)
	if err != nil {
		return err
	}

	logging.Infof(ctx,
		"Inserting %d rows into table `%s.%s.%s`",
		len(rows), opts.project, opts.dataset, opts.table)

	if err := inserter.Put(ctx, rows); err != nil {
		if merr, ok := err.(bigquery.PutMultiError); ok {
			fmt.Fprintf(os.Stderr, "Failed to upload some rows:\n")
			for _, rowErr := range merr {
				for _, valErr := range rowErr.Errors {
					fmt.Fprintf(os.Stderr, "row %d: %s\n", rowErr.RowIndex, valErr)
				}
			}
		}
		return err // this is e.g. "1 row insertion failed"
	}

	logging.Infof(ctx, "Done")
	return nil
}

func readInput(r io.Reader, insertIDBase string) (rows []bigquery.ValueSaver, err error) {
	line := 0
	scanner := bufio.NewScanner(r)
	for scanner.Scan() {
		line++
		if json := strings.TrimSpace(scanner.Text()); json != "" {
			row, err := parseRow([]byte(json), fmt.Sprintf("%s:%d", insertIDBase, line))
			if err != nil {
				return nil, fmt.Errorf("bad input line %d: %s", line, err)
			}
			rows = append(rows, row)
		}
	}
	err = scanner.Err()
	return
}

// tableRow implements bigquery.ValueSaver.
type tableRow struct {
	data     map[string]bigquery.Value
	insertID string
}

func parseRow(data []byte, insertID string) (*tableRow, error) {
	row := make(map[string]bigquery.Value)
	if err := json.Unmarshal(data, &row); err != nil {
		return nil, fmt.Errorf("bad JSON - %s", err)
	}
	return &tableRow{row, insertID}, nil
}

func (r *tableRow) Save() (map[string]bigquery.Value, string, error) {
	return r.data, r.insertID, nil
}
