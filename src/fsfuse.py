#! /usr/bin/env python

# the above line is written for three reasons
# 1. to specify that the file is to be interperted. The character "#!" a.k.a shebang is an indication to the shell that the file is a script and has to be interpreted
# 2. the next part is to invoke the interpreter and also specify the interpretor type. Interpreter is invoked using the "env" command which resides in the /usr/bin/ directory.
#    this command spawn a new process of type python which would do the interpretation of the file.

import sys
if sys.version_info[:2] != (2,6):
	msg = "This code has been tested on python version 2.6 only. You are running it on %s.%s\n"
	sys.stderr.write(msg % (sys.version_info[0],sys.version_info[1])) 

try:
	from fuse import Fuse
	import fuse
	import stat,os
except ImportError,ierror:
	sys.stderr.write("unable to load module %s" % str(ierror))
	sys.exit(1)
#loading fuse version
fuse.fuse_python_api = (0, 2)

class fs(Fuse):
	''' This class inherits from python fuse class. Complete documentation on the use of this library can be found at http://sourceforge.net/apps/mediawiki/fuse/index.php?title=FUSE_Python_Reference '''
	def __init__(self,*args, **kwargs):
		Fuse.__init__(self,*args, **kwargs)
	
	def getattr(self, path):
	      print 'called getattr:', path
	      if (path == '/'):
	         t = [0,]*10
        	 t[0] = stat.S_IFDIR | 0755
	         t[3] = 2; t[6] = 2048
	         return t
	      else: return -ENOENT		

if __name__ == "__main__":
	server = fs()
	
