# dhcp2csv Tool

## Intended Workflow

    go install infra/crimson/cmd/dhcp2csv
    dhcp2csv -boot-class <class> -site <site> -skip-header \
        dhcp-<something>.conf > hosts.csv
    
Check the errors / warnings on stderr, and check the resulting
hosts.csv for accuracy. (Yes, there may be errors in dhcp config!)
Then ingest the file into the database:

    crimson add-host -input-file-csv hosts.csv

## DEPRECATED: Do Not Depend

This tool is deprecated on creation, by design. It is intended to be
used once for migrating the source of truth from DHCP host files to
the database. Once DHCP host files are reliably generated from the
database, this tool will be deleted. Do not create any dependencies on
this tool.
