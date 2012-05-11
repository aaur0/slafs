#copyright (c) 2010, Matteo Bertozzi <theo.bertozzi@gmail.com>
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#    * Redistributions of source code must retain the above copyright
#      notice, this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above copyright
#      notice, this list of conditions and the following disclaimer in the
#      documentation and/or other materials provided with the distribution.
#    * Neither the name of the Matteo Bertozzi nor the
#      names of its contributors may be used to endorse or promote products
#      derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY Matteo Bertozzi ``AS IS'' AND ANY
# EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL Matteo Bertozzi BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
# ----------------------------------------------------------------------------
# How to mount the File-System:
#   python htfs.py mnt
#
# How to umount the File-System?
#   fusermount -u mnt

import os, sys, stat, errno, time
import fuse

# Specify what Fuse API use: 0.2
fuse.fuse_python_api = (0, 2)

import logging
LOG_FILENAME = 'htfs.log'
logging.basicConfig(filename=LOG_FILENAME,level=logging.DEBUG, format="%(asctime)s %(lineno)d %(module)s %(message)s")

class Item(object):
    """
    An Item is an Object on Disk, it can be a Directory, File, Symlink, ...
    """
    def __init__(self, mode, uid, gid):
        logging.info("inside Item __init__ method with mode = %s, uid = %s, gid = %s", mode, uid, gid)
	# ----------------------------------- Metadata --
        self.atime = time.time()   # time of last acces
        self.mtime = self.atime    # time of last modification
        self.ctime = self.atime    # time of last status change

        self.dev  = 0        # device ID (if special file)
        self.mode = mode     # protection and file-type
        self.uid  = uid      # user ID of owner
        self.gid  = gid      # group ID of owner

        # ------------------------ Extended Attributes --
        self.xattr = {}

        # --------------------------------------- Data --
        if stat.S_ISDIR(mode):
            self.data = set()
        else:
            self.data = ''

	#------------------------ hotspot related data -----------------
	self.hitcount = 0

    def read(self, offset, length):
	logging.info("inside Item: read method with param offset = %s, length = %s", str(offset), str(length))
        return self.data[offset:offset+length]

    def write(self, offset, data):
	logging.info("inside Item:write - offset = %s , length_of_data = %s", str(offset), str(len(data)))
        length = len(data)
        self.data = self.data[:offset] + data + self.data[offset+length:]
        return length

    def truncate(self, length):
	logging.info("inside Item:Truncate method :: length = %s" , str(length))
        if len(self.data) > length:
            self.data = self.data[:length]
        else:
            self.data += '\x00'# (length - len(self.data))

def zstat(stat):
    stat.st_mode  = 0
    stat.st_ino   = 0
    stat.st_dev   = 0
    stat.st_nlink = 2
    stat.st_uid   = 0
    stat.st_gid   = 0
    stat.st_size  = 0
    stat.st_atime = 0
    stat.st_mtime = 0
    stat.st_ctime = 0
    return stat

class HTFS(fuse.Fuse):
    def __init__(self, *args, **kwargs):
	logging.info("inside HTFS:__init__ method")
        fuse.Fuse.__init__(self, *args, **kwargs)

        self.uid = os.getuid()
        self.gid = os.getgid()

        self._storage = {'/': Item(0755 | stat.S_IFDIR, self.uid, self.gid)}

    # --- Metadata -----------------------------------------------------------
    def getattr(self, path):
	logging.info("inside getattr method with path = %s",path)
        if not path in self._storage:
            return -errno.ENOENT
	logging.debug(self._storage)
        # Lookup Item and fill the stat struct
        item = self._storage[path]
        st = zstat(fuse.Stat())
        st.st_mode  = item.mode
        st.st_uid   = item.uid
        st.st_gid   = item.gid
        st.st_dev   = item.dev
        st.st_atime = item.atime
        st.st_mtime = item.mtime
        st.st_ctime = item.ctime
        st.st_size  = len(item.data)
        return st

    def chmod(self, path, mode):
        logging.info("inside HTFS:chmod :: path  = %s, mode = %s", str(path), str(mode))
	item = self._storage[path]
        item.mode = mode

    def chown(self, path, uid, gid):
	logging.info("inside HTFS:chown :: path = %s, uid = %s, gid = %s", str(path), str(uid), str(gid))
        item = self._storage[path]
        item.uid = uid
        item.gid = gid

    def utime(self, path, times):
	logging.info("inside HTFS:utime :: path = %s, times = %s", str(path), str(times))
        item = self._storage[path]
        item.ctime = item.mtime = times[0]
	item.hitcount+=1
	logging.info("HTFS:utime :: the item has been accessed %s times ", item.hitcount)

    # --- Namespace ----------------------------------------------------------
    def unlink(self, path):
	logging.info("inside HTFS:unlink :: path = %s", str(path))
        self._remove_from_parent_dir(path)
        del self._storage[path]

    def rename(self, oldpath, newpath):
	logging.info("inside HTFS:rename :: oldpath = %s, newpath = %s", newpath, oldpath)
        item = self._storage.pop(oldpath)
        self._storage[newpath] = item

    # --- Links --------------------------------------------------------------
    def symlink(self, path, newpath):
	logging.info("inside HTFS:symlink :: path = %s, newpath = %s", str(path), str(newpath))
        item = Item(0644 | stat.S_IFLNK, self.uid, self.gid)
        item.data = path
        self._storage[newpath] = item
        self._add_to_parent_dir(newpath)

    def readlink(self, path):
	logging.info("inside HTFS:readlink :: path = %s" ,str(path))
        return self._storage[path].data

    # --- Extra Attributes ---------------------------------------------------
    def setxattr(self, path, name, value, flags):
	logging.info("inside HTFS:setxattr :: path = %s, name = %s, value = %s, flags = %s", str(path), str(name), str(value), str(flags))
        self._storage[path].xattr[name] = value

    def getxattr(self, path, name, size):
	logging.info("inside HTFS: getxattr :: path = %s, name = %s, size = %s", str(path), str(name), str(size))
        value = self._storage[path].xattr.get(name, '')
        if size == 0:   # We are asked for size of the value
            return len(value)
        return value

    def listxattr(self, path, size):
	logging.info("inside HTFS:listxattr :: path = %s, size = %s", str(path), str(size))
        attrs = self._storage[path].xattr.keys()
        if size == 0:
            return len(attrs) + len(''.join(attrs))
        return attrs

    def removexattr(self, path, name):
	logging.info("inside HTFS:removexattr :: path = %s, name = %s", str(path), name)
        if name in self._storage[path].xattr:
            del self._storage[path].xattr[name]

    # --- Files --------------------------------------------------------------
    def mknod(self, path, mode, dev):
	logging.info("HTFS:mknod :: path = %s, mode = %s, dev = %s", str(path), str(mode), str(dev))
        item = Item(mode, self.uid, self.gid)
        item.dev = dev
        self._storage[path] = item
        self._add_to_parent_dir(path)

    def create(self, path, flags, mode):
	logging.info("HTFS:create :: path = %s, flags = %s, mode = %s", str(path), str(flags), str(mode))
	try:
		# always create file on the disk first
		if not (os.access(path, os.W_OK)):
			logging.error("Write permisson doesn't exist for path = %s " ,path)
		else:	
			fd = os.open(path, flags, os.O_CREAT)
			os.close(fd)
        		self._storage[path] = Item(mode | stat.S_IFREG, self.uid, self.gid)
			self._add_to_parent_dir(path)
	except Exception,e:
		logging.error("HTFS:create failed with error : %s",str(e))

    def open(self, path, flags):
	logging.info("HTFS:open :: path = %s and flags = %s", str(path), str(flags))
	return 0
	pass
	(self._storage[path])[hitcount]+=1

    def truncate(self, path, len):
	logging.info("HTFS:trucate :: path = %s, len = %s", path , str(len))
        self._storage[path].truncate(len)

    def read(self, path, size, offset):
	logging.info("HTFS:read :: path = %s, size = %s, offset = %s", str(path), str(size), str(offset))
	(self._storage[path]).hitcount+=1
	logging.info("the path = %s has been read %s times", path, (self._storage[path]).hitcount)
        return self._storage[path].read(offset, size)

    def write(self, path, buf, offset):
	logging.info("HTFS:write :: path = %s, length_of_buf = %s, offset = %s", str(path), str(len(buf)), str(offset))
        (self._storage[path]).hitcount=0
        return self._storage[path].write(offset, buf)

    # --- Directories --------------------------------------------------------
    def mkdir(self, path, mode):
	logging.info("HTFS:mkdir :: path = %s, mode = %s", str(path), str(mode))
        self._storage[path] = Item(mode | stat.S_IFDIR, self.uid, self.gid)
        self._add_to_parent_dir(path)

    def rmdir(self, path):
	logging.info("HTFS:rmdir :: path = %s", path)
        if self._storage[path].data:
            return -errno.ENOTEMPTY

        self._remove_from_parent_dir(path)
        del self._storage[path]

    def readdir(self, path, offset):
	logging.info("HTFS:readdir :: path = %s, offset = %s", path, offset)
        dir_items = self._storage[path].data
        for item in dir_items:
            yield fuse.Direntry(item)
	#for entry in os.listdir("/home/anand/os/fs/slafs/src/mnt" + path):
	   # yield fuse.Direntry(entry)	

    def _add_to_parent_dir(self, path):
	logging.info("HTFS:_add_to_parent_dir :: path = %s", path)
        parent_path = os.path.dirname(path)
        filename = os.path.basename(path)
        self._storage[parent_path].data.add(filename)

    def _remove_from_parent_dir(self, path):
	logging.info("HTFS:_remove_from_parent_dir :: path = %s", path)
        parent_path = os.path.dirname(path)
        filename = os.path.basename(path)
        self._storage[parent_path].data.remove(filename)

def main():
	try:
	         logging.info("main method invoked")
		 usage=""" HTFS - HashTable File-System  """ + fuse.Fuse.fusage
		 server = HTFS(version="%prog " + fuse.__version__,  usage=usage, dash_s_do='setsingle')
		 server.parse(errex=1)
		 server.main()
	except Exception, e:
		logging.error("main failed with error : %s " ,str(e))

if __name__ == '__main__':
    main()


