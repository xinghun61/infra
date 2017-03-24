package main

import (
	"flag"
)

// Flags holds flag values for this tool
type Flags struct {
	dirs                string
	bucket              string
	dest                string
	serviceAccountCreds string
}

// NewFlags returns a new Flags structure ready to be registered with a flag.FlagSet
func NewFlags() *Flags {
	return &Flags{}
}

// Register registers the flags for this tool into the given flag.Flagset
func (f *Flags) Register(fs *flag.FlagSet) {
	fs.StringVar(&f.dirs, "dirs", "", "List of directories to backup, delimited by ':'")
	fs.StringVar(&f.bucket, "bucket", "", "Bucket where backup should be stored")
	fs.StringVar(&f.dest, "dest", "",
		"Prefix for name of object to create in GCS. The provided string will be joined "+
			"to the start of each directory in <dirs> (using a '/' as a separator). "+
			"Any leading '/' on each <dir> will be stripped prior to joining with the prefix. "+
			"The suffix '.tar.bz2' will also be appended to the name of each dir. "+
			"Thus, with the arguments 'dirs=/etc:/bin:/usr/local:some/path dest=/backup', the resulting objects in GCS will be named "+
			"'/backup/etc.tar.bz2', '/backup/bin.tar.bz2', '/backup/usr/local.tar.bz2', '/backup/some/path.tar.bz2'",
	)
	fs.StringVar(&f.serviceAccountCreds, "credsfile", "", "Location of credentials file for Google Cloud Storage")
}
