-- Copyright 2016 The Chromium Authors. All Rights Reserved.
--
-- Use of this source code is governed by a BSD-style
-- license that can be found in the LICENSE file or at
-- https://developers.google.com/open-source/licenses/bsd

-- Create tables in the crimson DB.

CREATE TABLE ip_range (
  site varchar(20) NOT NULL,
  vlan varchar(20),
  start_ip varchar(34) NOT NULL,
  end_ip varchar(34) NOT NULL
) ENGINE=INNODB;

CREATE index ip_range_start_ip_idx ON ip_range(start_ip);
CREATE index ip_ragne_start_ip_idx ON ip_range(end_ip);

CREATE TABLE host (
  site varchar(20) NOT NULL,
  hostname varchar(63) NOT NULL,
  mac_addr varchar(14) NOT NULL,
  ip varchar(34) NOT NULL,
  boot_class varchar(20),
  PRIMARY KEY (mac_addr)
) ENGINE=INNODB;

CREATE index host_site_hostname_idx ON host(site, hostname);
CREATE index host_site_ip_idx ON host(site, ip);
