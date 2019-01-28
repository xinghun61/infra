#include <iostream>
#include <unordered_map>

#include "test.h"

namespace flint {

	/**
	* Prints the usage information for the program, then exits.
	*/
	void printHelp() {
		printf("Usage: flint++ [options:] [files:]\n\n"
			   "\t-r, --recursive		: Search subfolders for files.\n"
			   "\t-c, --cmode			: Only perform C based lint checks.\n"
			   "\t-j, --json			: Output report in JSON format.\n"
			   "\t-v, --verbose		: Print full file paths.\n"
			   "\t-l, --level [def=3] : Set the lint level.\n"
			   "			          1 : Errors only\n"
			   "			          2 : Errors & Warnings\n"
			   "			          3 : All feedback\n\n"
			   "\t-h, --help		    : Print usage.\n\n");
#ifdef _DEBUG
		// Stop visual studio from closing the window...
		system("PAUSE");
#endif
		exit(1);
	};
};
