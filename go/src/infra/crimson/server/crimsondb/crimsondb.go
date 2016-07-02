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
	"strings"

	"github.com/luci/luci-go/common/logging"
	"golang.org/x/net/context"

	"github.com/go-sql-driver/mysql"

	crimson "infra/crimson/proto"
)

// IPRange describes a row in the vlan table.
type IPRange struct {
	Site      string
	VlanId    uint32
	VlanAlias string
	StartIP   string
	EndIP     string
}

func (row IPRange) String() string {
	return fmt.Sprintf("%s/%d: %s-%s (%s)",
		row.Site, row.VlanId, row.StartIP, row.EndIP, row.VlanAlias)
}

func logAndErrorf(ctx context.Context, format string, params ...interface{}) error {
	logging.Errorf(ctx, format, params...)
	return fmt.Errorf(format, params...)
}

func logAndUserErrorf(ctx context.Context, code int, format string, params ...interface{}) error {
	logging.Errorf(ctx, format, params...)
	return UserErrorf(code, format, params...)
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

// MacAddrStringToHexString turns a mac address into a hex string.
func MacAddrStringToHexString(macAddr string) (string, error) {
	mac, err := net.ParseMAC(macAddr)
	if err != nil {
		return "", err
	}
	return "0x" + hex.EncodeToString(mac), nil
}

// HexStringToHardwareAddr turns an hex string into a hardware address.
func HexStringToHardwareAddr(hexMac string) (net.HardwareAddr, error) {
	// 6 bytes in hex + leading '0x'
	if len(hexMac) < 14 {
		err := fmt.Errorf("parsing of hex string failed (too short: %d characters)",
			len(hexMac))
		return net.HardwareAddr{}, err
	}
	if hexMac[:2] != "0x" {
		return net.HardwareAddr{}, fmt.Errorf("parsing of hex string failed: %s", hexMac)
	}
	hwAddrRaw, err := hex.DecodeString(hexMac[2:])
	if err != nil {
		return net.HardwareAddr{}, err
	}
	hwAddr := make(net.HardwareAddr, len(hwAddrRaw))
	for n := 0; n < len(hwAddrRaw); n++ {
		hwAddr[n] = hwAddrRaw[n]
	}
	return hwAddr, nil
}

// HexStringToIP converts an hex string returned by MySQL into a net.IP structure.
func HexStringToIP(hexIP string) (net.IP, error) {
	// TODO(pgervais): Add decent error checking. Ex: check hexIP starts with '0x'.
	ip, err := hex.DecodeString(hexIP[2:])
	if err != nil {
		return net.IP{}, err
	}
	length := 4
	if len(ip) > 4 {
		length = 16
	}
	netIP := make(net.IP, length)
	for n := 1; n <= len(ip); n++ {
		netIP[length-n] = ip[len(ip)-n]
	}
	return netIP, nil
}

// scanIPRanges is a low-level function to scan sql results.
// Rows must contain site, vlan_id, start_ip, end_ip, vlan_alias in that order.
func scanIPRanges(ctx context.Context, rows *sql.Rows) ([]IPRange, error) {
	var ipRanges []IPRange

	for rows.Next() {
		var startIP, endIP string
		var ip net.IP
		ipRange := IPRange{}
		err := rows.Scan(&ipRange.Site, &ipRange.VlanId, &startIP, &endIP, &ipRange.VlanAlias)
		if err != nil { // Users can't trigger that.
			cols, _ := rows.Columns()
			err = logAndErrorf(ctx, "%s. Columns: %v", err, cols)
			return nil, err
		}
		ip, err = HexStringToIP(startIP)
		if err != nil {
			return nil, err
		}
		ipRange.StartIP = ip.String()

		ip, err = HexStringToIP(endIP)
		if err != nil {
			return nil, err
		}
		ipRange.EndIP = ip.String()
		ipRanges = append(ipRanges, ipRange)
	}
	err := rows.Err()
	if err != nil {
		logging.Errorf(ctx, "%s", err)
		return nil, err
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

	// [a,b] and [c,d] overlap iff a<=d and b>=c
	statement := ("SELECT site, vlan_id, start_ip, end_ip, vlan_alias FROM ip_range\n" +
		"WHERE site=? AND start_ip<=? AND end_ip>=?")
	rows, err := tx.Query(statement, row.Site, endIP, startIP)
	if err != nil {
		logging.Errorf(ctx, "IP range query failed. %s", err)
		return
	}
	defer rows.Close()
	var ipRanges []IPRange
	ipRanges, err = scanIPRanges(ctx, rows)
	if err != nil {
		logging.Errorf(ctx, "scanIPRangeRows has failed. %s", err)
		return
	}
	if len(ipRanges) > 0 {
		err = UserErrorf(
			AlreadyExists,
			"overlapping range(s) have been found: %s, not inserting new one", ipRanges)
		logging.Infof(ctx, "%s", err)
		return
	}

	// No overlapping ranges have been found, insert the new one.
	logging.Infof(ctx, "No overlapping ranges have been found, proceeding.")
	statement = ("INSERT INTO ip_range (site, vlan_id, start_ip, end_ip, vlan_alias)\n" +
		"VALUES (?, ?, ?, ?, ?)")
	_, err = tx.Exec(statement, row.Site, row.VlanId, startIP, endIP, row.VlanAlias)
	if err != nil {
		logging.Errorf(ctx, "IP range insertion failed. %s", err)
		return
	}
	return
}

// DeleteIPRange deletes an IP range from the database.
func DeleteIPRange(ctx context.Context, deleteList *crimson.IPRangeDeleteList) error {
	db := DB(ctx)

	if len(deleteList.Ranges) == 0 {
		return logAndUserErrorf(ctx, InvalidArgument,
			"Received an empty list of IP ranges to delete.")
	}

	statement := bytes.Buffer{}
	params := []interface{}{}

	statement.WriteString("DELETE FROM ip_range\nWHERE ")
	delimiter := ""

	for i, r := range deleteList.Ranges {
		if len(r.Site) == 0 {
			return logAndUserErrorf(ctx, InvalidArgument,
				"Received empty site value in range %d: %s", i, r)
		}

		// IEEE 802.1Q supports VLAN IDs 1-4094
		if r.VlanId == 0 || r.VlanId > 4094 {
			return logAndUserErrorf(ctx, InvalidArgument,
				"vlan ID is invalid in range %d: must be between 1-4094; received %s", i, r)
		}

		statement.WriteString(delimiter)
		statement.WriteString("(site=? AND vlan_id=?)")
		params = append(params, r.Site, r.VlanId)
		delimiter = "\nOR "
	}
	s := statement.String()
	// Defense in depth. We *really* don't want to drop every row at the same time.
	if strings.Index(s, "WHERE") == -1 {
		panic("Query generated does not contain a WHERE clause. " +
			"Aborting before doing something wrong.")
	}
	_, err := db.Query(s, params...)
	if err != nil {
		logging.Errorf(ctx, "Deletion of IP ranges failed: %s", err)
		return err
	}
	return nil
}

// SelectIPRange returns ip ranges filtered by values in req.
func SelectIPRange(ctx context.Context, req *crimson.IPRangeQuery) ([]IPRange, error) {
	db := DB(ctx)
	var rows *sql.Rows
	var err error
	delimiter := ""

	statement := bytes.Buffer{}
	params := []interface{}{}

	statement.WriteString("SELECT site, vlan_id, start_ip, end_ip, vlan_alias FROM ip_range")
	delimiter = "\nWHERE "

	if req.Site != "" {
		statement.WriteString(delimiter)
		delimiter = "\nAND "
		statement.WriteString("site=?")
		params = append(params, req.Site)
	}

	if req.VlanId != 0 {
		statement.WriteString(delimiter)
		delimiter = "\nAND "
		statement.WriteString("vlan_id=?")
		params = append(params, req.VlanId)
	}

	if req.VlanAlias != "" {
		statement.WriteString(delimiter)
		delimiter = "\nAND "
		statement.WriteString("vlan_alias=?")
		params = append(params, req.VlanAlias)
	}

	if req.Ip != "" {
		statement.WriteString(delimiter)
		delimiter = "\nAND "
		ip, err := IPStringToHexString(req.Ip)
		if err != nil {
			return nil, UserErrorf(
				InvalidArgument,
				"parsing of IP address failed: %s", req.Ip)
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
		logging.Errorf(ctx, "%s", err)
		return nil, err
	}
	defer rows.Close()

	var ipRanges []IPRange
	ipRanges, err = scanIPRanges(ctx, rows)
	if err != nil {
		logging.Errorf(ctx, "%s", err)
		return nil, err
	}
	return ipRanges, nil
}

// scanHosts is a low-level function to scan sql results.
// Rows must contain site, hostname, mac_addr, ip, boot_class in that order.
func scanHosts(ctx context.Context, rows *sql.Rows) (*crimson.HostList, error) {
	hostList := crimson.HostList{}

	for rows.Next() {
		var ipString, macString string
		var hw net.HardwareAddr
		var ip net.IP
		var bootClass sql.NullString

		host := crimson.Host{}
		err := rows.Scan(&host.Site, &host.Hostname, &macString, &ipString,
			&bootClass)
		if bootClass.Valid {
			host.BootClass = bootClass.String
		}
		if err != nil { // Users can't trigger that.
			logging.Errorf(ctx, "%s", err)
			return nil, err
		}
		if macString != "" {
			hw, err = HexStringToHardwareAddr(macString)
			if err != nil {
				return nil, err
			}
			host.MacAddr = hw.String()
		}

		if ipString != "" {
			ip, err = HexStringToIP(ipString)
			if err != nil {
				return nil, err
			}
			host.Ip = ip.String()
		}
		hostList.Hosts = append(hostList.Hosts, &host)
	}
	err := rows.Err()
	if err != nil {
		logging.Errorf(ctx, "%s", err)
		return nil, err
	}
	return &hostList, nil
}

// InsertHost adds new hosts in the corresponding table.
func InsertHost(ctx context.Context, req *crimson.HostList) (err error) {
	db := DB(ctx)

	if len(req.Hosts) == 0 {
		logging.Errorf(ctx, "Received empty list of hosts to create.")
		return UserErrorf(InvalidArgument,
			"Received empty list of hosts to create.")
	}

	statement := bytes.Buffer{}
	params := []interface{}{}

	statement.WriteString("INSERT INTO host " +
		"(site, hostname, mac_addr, ip, boot_class) VALUES ")
	delimiter := ""

	// Check that all required fields have been provided.
	// TODO(pgervais): autogenerate missing values instead.
	for i, host := range req.Hosts {
		if host.Site == "" {
			err = UserErrorf(InvalidArgument,
				"Received empty host in entry #%s", i+1)
			return
		}
		if host.MacAddr == "" {
			err = UserErrorf(InvalidArgument,
				"Received empty MAC address in entry #%s", i+1)
			return
		}
		if host.Ip == "" {
			err = UserErrorf(InvalidArgument,
				"Received empty IP address in entry #%s", i+1)
			return
		}
		if host.Hostname == "" {
			err = UserErrorf(InvalidArgument,
				"Received empty hostname in entry #%s", i+1)
			return
		}

		// Compose query
		var ip, macAddr string
		statement.WriteString(delimiter)
		delimiter = ", \n"
		statement.WriteString("(?, ?, ?, ?, ?)")

		ip, err = IPStringToHexString(host.Ip)
		if err != nil {
			return
		}

		macAddr, err = MacAddrStringToHexString(host.MacAddr)
		if err != nil {
			return
		}

		if host.BootClass == "" {
			params = append(
				params,
				host.Site, host.Hostname, macAddr, ip, nil)
		} else {
			params = append(
				params,
				host.Site, host.Hostname, macAddr, ip, host.BootClass)
		}
	}

	_, err = db.Exec(statement.String(), params...)
	if err != nil {
		// MySQL error 1062 is 'duplicate entry'.
		if mysqlErr, ok := err.(*mysql.MySQLError); ok && mysqlErr.Number == 1062 {
			logging.Warningf(ctx, "Insertion of new hosts failed. %s", err)
			err = UserErrorf(AlreadyExists,
				"Hosts couldn't be created because some entries already exist.")
		}
		logging.Errorf(ctx, "Insertion of new hosts failed. %s", err)
		return
	}

	return
}

func SelectHost(ctx context.Context, req *crimson.HostQuery) (*crimson.HostList, error) {
	var err error

	db := DB(ctx)
	delimiter := ""

	statement := bytes.Buffer{}
	params := []interface{}{}

	statement.WriteString("SELECT site, hostname, mac_addr, ip, boot_class FROM host")
	delimiter = "\nWHERE "

	if req.Site != "" {
		statement.WriteString(delimiter)
		delimiter = "\nAND "
		statement.WriteString("site=?")
		params = append(params, req.Site)
	}

	if req.Hostname != "" {
		statement.WriteString(delimiter)
		delimiter = "\nAND "
		statement.WriteString("hostname=?")
		params = append(params, req.Hostname)
	}

	if req.MacAddr != "" {
		statement.WriteString(delimiter)
		delimiter = "\nAND "
		hw, err := MacAddrStringToHexString(req.MacAddr)
		if err != nil {
			return nil, UserErrorf(
				InvalidArgument,
				"parsing of Mac address failed: %s", req.MacAddr)
		}
		statement.WriteString("mac_addr=?")
		params = append(params, hw)
	}

	if req.Ip != "" {
		statement.WriteString(delimiter)
		delimiter = "\nAND "
		ip, err := IPStringToHexString(req.Ip)
		if err != nil {
			return nil, UserErrorf(
				InvalidArgument,
				"parsing of IP address failed: %s", req.Ip)
		}
		statement.WriteString("ip=?")
		params = append(params, ip)
	}

	if req.BootClass != "" {
		statement.WriteString(delimiter)
		delimiter = "\nAND "
		statement.WriteString("boot_class=?")
		params = append(params, req.BootClass)
	}

	if req.Limit > 0 {
		statement.WriteString("\nLIMIT ?")
		params = append(params, req.Limit)
	}

	sqlRows, err := db.Query(statement.String(), params...)

	if err != nil {
		logging.Errorf(ctx, "%s", err)
		return nil, err
	}
	defer sqlRows.Close()

	var rows *crimson.HostList
	rows, err = scanHosts(ctx, sqlRows)
	if err != nil {
		logging.Errorf(ctx, "%s", err)
		return nil, err
	}
	return rows, nil
}

// DeleteHost drops hosts whose name match criteria in req.
func DeleteHost(ctx context.Context, req *crimson.HostDeleteList) error {
	var err error

	db := DB(ctx)
	delimiter := ""

	statement := bytes.Buffer{}
	params := []interface{}{}

	// Having a 'WHERE' in this string is very important to avoid issuing
	// 'DELETE FROM host;' by mistake ;-)
	statement.WriteString("DELETE FROM host\nWHERE ")
	delimiter = "("

	for _, host := range req.Hosts {
		if host.Hostname == "" && host.MacAddr == "" {
			return fmt.Errorf("Host must be selected by either hostname or mac " +
				"address. Got empty strings in both cases.")
		}

		if host.Hostname != "" {
			statement.WriteString(delimiter)
			delimiter = " AND "
			statement.WriteString("hostname=?")
			params = append(params, host.Hostname)
		}
		if host.MacAddr != "" {
			statement.WriteString(delimiter)
			delimiter = " AND "
			statement.WriteString("mac_addr=?")
			mac, err := MacAddrStringToHexString(host.MacAddr)
			if err != nil {
				return UserErrorf(InvalidArgument, "Invalid MAC address: %s", host.MacAddr)
			}
			params = append(params, mac)
		}

		statement.WriteString(")")
		delimiter = "\nOR ("
	}

	// Defense in depth. We *really* don't want to drop every row at the same time.
	s := statement.String()
	if strings.Index(s, "WHERE") == -1 {
		panic("Query generated does not contain a WHERE clause. " +
			"Aborting before doing something wrong.")
	}
	_, err = db.Exec(statement.String(), params...)
	// TODO(pgervais): return the number of rows affected.
	if err != nil {
		logging.Errorf(ctx, "Deletion of hosts failed. %s", err)
		return err
	}
	return nil
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
