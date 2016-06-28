// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package crimsondb

import (
	"bytes"
	"database/sql"
	"encoding/hex"
	"fmt"
	"net"

	"github.com/luci/luci-go/common/logging"
	"golang.org/x/net/context"

	// This simply registers the mysql driver.
	_ "github.com/go-sql-driver/mysql"

	"infra/crimson/proto"
)

// IPRangeRow describes a row in the ip_range table.
type IPRangeRow struct {
	Site    string
	Vlan    string
	StartIP string
	EndIP   string
}

func (row IPRangeRow) String() string {
	return fmt.Sprintf("%s/%s: %s-%s",
		row.Site, row.Vlan, row.StartIP, row.EndIP)
}

// IPStringToHexString converts an IP address into a hex string suitable for MySQL.
func IPStringToHexString(ip string) (string, error) {
	ipb := net.ParseIP(ip)
	if ipb == nil {
		return "", fmt.Errorf("parsing of IP address failed: %s", ip)
	}
	if ipb.DefaultMask() != nil {
		ipb = ipb.To4()
	}
	return "0x" + hex.EncodeToString(ipb), nil
}

// HexStringToIP converts an hex string returned by MySQL into a net.IP structure.
func HexStringToIP(hexIP string) net.IP {
	// TODO(pgervais): Add decent error checking. Ex: check hexIP starts with '0x'.
	ip, _ := hex.DecodeString(hexIP[2:])
	length := 4
	if len(ip) > 4 {
		length = 16
	}
	netIP := make(net.IP, length)
	for n := 1; n <= len(ip); n++ {
		netIP[length-n] = ip[len(ip)-n]
	}
	return netIP
}

// scanIPRangeRows is a low-level function to scan sql results.
// Rows must contain site, vlan, start_ip, end_ip in that order.
func scanIPRangeRows(ctx context.Context, rows *sql.Rows) ([]IPRangeRow, error) {
	var ipRanges []IPRangeRow

	for rows.Next() {
		var startIP, endIP string
		ipRange := IPRangeRow{}
		err := rows.Scan(&ipRange.Site, &ipRange.Vlan, &startIP, &endIP)
		if err != nil {
			logging.Errorf(ctx, "%s", err)
			return ipRanges, err
		}
		ipRange.StartIP = HexStringToIP(startIP).String()
		ipRange.EndIP = HexStringToIP(endIP).String()
		ipRanges = append(ipRanges, ipRange)
	}
	err := rows.Err()
	if err != nil {
		logging.Errorf(ctx, "%s", err)
		return ipRanges, err
	}
	return ipRanges, nil
}

// InsertIPRange adds a new IP range in the corresponding table.
func InsertIPRange(ctx context.Context, row *crimson.IPRange) (err error) {
	db := DB(ctx)

	if len(row.Site) == 0 {
		logging.Errorf(ctx, "Received empty site value.")
		return fmt.Errorf("Received empty site value.")
	}

	var startIP, endIP string
	startIP, err = IPStringToHexString(row.StartIp)
	if err != nil {
		return
	}
	endIP, err = IPStringToHexString(row.EndIp)
	if err != nil {
		return
	}

	// Open Transaction
	var tx *sql.Tx
	tx, err = db.Begin()
	if err != nil {
		logging.Errorf(ctx, "Opening transaction failed. %s", err)
		return
	}
	defer func() {
		if err == nil {
			err = tx.Commit()
			if err != nil {
				logging.Errorf(ctx, "Committing transaction failed. %s", err)
			}
		} else {
			tx.Rollback()
		}
	}()

	// Lock the whole table because we must be sure no new ip ranges are inserted
	// before we insert ours. This unfortunately also blocks read access for other
	// connections.
	_, err = tx.Exec("LOCK TABLES ip_range WRITE")
	if err != nil {
		logging.Errorf(ctx, "Locking table ip_range failed. %s", err)
		return
	}

	// Look for existing overlapping ranges.
	// [a,b] and [c,d] overlap iff a<=d and b>=c
	statement := ("SELECT site, vlan, start_ip, end_ip FROM ip_range\n" +
		"WHERE site=? AND start_ip<=? AND end_ip>=?")
	rows, err := tx.Query(statement, row.Site, endIP, startIP)
	if err != nil {
		logging.Errorf(ctx, "IP range query failed. %s", err)
		return
	}
	defer rows.Close()
	ipRanges, err := scanIPRangeRows(ctx, rows)
	if err != nil {
		logging.Errorf(ctx, "scanIPRangeRows has failed. %s", err)
		return
	}
	if len(ipRanges) > 0 {
		err = fmt.Errorf(
			"overlapping ranges have been found: %s, not inserting new one", ipRanges)
		logging.Infof(ctx, "%s", err)
		return
	}

	// No overlapping ranges have been found, insert the new one.
	logging.Infof(ctx, "No overlapping ranges have been found, proceeding.")
	statement = ("INSERT INTO ip_range (site, vlan, start_ip, end_ip)\n" +
		"VALUES (?, ?, ?, ?)")
	_, err = tx.Exec(statement, row.Site, row.Vlan, startIP, endIP)
	if err != nil {
		logging.Errorf(ctx, "IP range insertion failed. %s", err)
		return
	}
	return
}

// SelectIPRange returns ip ranges filtered by values in req.
func SelectIPRange(ctx context.Context, req *crimson.IPRangeQuery) []IPRangeRow {
	// TODO(pgervais): Add error reporting.
	db := DB(ctx)
	var rows *sql.Rows
	var err error
	delimiter := ""

	vlan := req.Vlan
	site := req.Site

	statement := bytes.Buffer{}
	params := []interface{}{}

	statement.WriteString("SELECT site, vlan, start_ip, end_ip FROM ip_range")
	delimiter = "\nWHERE "

	if site != "" {
		statement.WriteString(delimiter)
		delimiter = "\nAND "
		statement.WriteString("site=?")
		params = append(params, site)
	}

	if vlan != "" {
		statement.WriteString(delimiter)
		delimiter = "\nAND "
		statement.WriteString("vlan=?")
		params = append(params, vlan)
	}

	if req.Ip != "" {
		statement.WriteString(delimiter)
		delimiter = "\nAND "
		ip, err := IPStringToHexString(req.Ip)
		if err != nil {
			return nil
		}
		statement.WriteString("start_ip<=? AND ?<=end_ip")
		params = append(params, ip, ip)
	}

	if req.Limit > 0 {
		statement.WriteString("\nLIMIT ?")
		params = append(params, req.Limit)
	}

	rows, err = db.Query(statement.String(), params...)

	if err != nil {
		// TODO(pgervais): propagate the error up the stack.
		logging.Errorf(ctx, "%s", err)
		return []IPRangeRow{}
	}
	defer rows.Close()

	var ipRanges []IPRangeRow
	ipRanges, err = scanIPRangeRows(ctx, rows)
	if err != nil {
		logging.Errorf(ctx, "%s", err)
		return nil
	}
	return ipRanges
}

// UseDB stores a db handle into a context.
func UseDB(ctx context.Context, db *sql.DB) context.Context {
	return context.WithValue(ctx, "dbHandle", db)
}

// DB gets the current db handle from the context.
func DB(ctx context.Context) *sql.DB {
	return ctx.Value("dbHandle").(*sql.DB)
}

// GetDBHandle returns a handle to the Cloud SQL instance used by this deployment.
func GetDBHandle() (*sql.DB, error) {
	// TODO(pgervais): do not hard-code the name of the database.
	return sql.Open("mysql", "root@cloudsql(crimson-staging:crimson-staging)/crimson")
}
