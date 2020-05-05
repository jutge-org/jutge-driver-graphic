
##############################################################################
# Importations
##############################################################################

import base64
import subprocess
import fcntl
import getpass
import glob
import grp
import grp
import logging
import optparse
import os
import pwd
import resource
import shutil
import signal
import socket
import stat
import sys
import tarfile
import tempfile
import time
import traceback
import yaml


##############################################################################
# Init logging
##############################################################################


def init_logging():
    '''Configures basic logging options.'''

    logging.basicConfig(
        format='%s@%s ' % (username(), hostname())
        + '%(asctime)s %(levelname)s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )
    logging.getLogger('').setLevel(logging.NOTSET)


##############################################################################
# System utilites
##############################################################################


def username():
    '''Returns the username of the process owner.'''
    return getpass.getuser()


def hostname():
    '''Returns the hostname of this computer.'''
    return socket.gethostname()


def exit(msg, err=1):
    '''Prints msg to stderr and exits program with code err.'''
    print(os.path.basename(sys.argv[0]) + ': ' + msg, sys.stderr)
    sys.exit(err)


def flush():
    '''Flushes stdout and stderr.'''
    sys.stdout.flush()
    sys.stderr.flush()


##############################################################################
# File utilites
##############################################################################

def llegir_fitxer_propietats(nom):
    '''Retorna un diccionari amb les propietats llegides del fitxer nom.'''
    dic = {}
    f = open(nom)
    for l in f.readlines():
        k, v = l.split(":", 1)
        dic[k.strip()] = v.strip()
    return dic


def write_file(name, txt=''):
    '''Writes the file name with contents txt.'''
    f = open(name, 'w')
    f.write(txt)
    f.close()


def append_file(name, txt=''):
    '''Adds to file name the contents of txt.'''
    try:
        f = open(name, 'a')
        f.write(txt)
        f.close()
    except UnicodeDecodeError:
        f = open(name, 'a', encoding='latin-1')
        f.write(txt)
        f.close()


def read_file(name):
    '''Returns a string with the contents of the file name.'''
    try:
        f = open(name, 'r')
        r = f.read()
        f.close()
        return r
    except UnicodeDecodeError:
        f = open(name, 'r', encoding='latin-1')
        r = f.read()
        f.close()
        return r


def del_file(name):
    '''Deletes the file name. Does not complain on error.'''
    try:
        os.remove(name)
    except OSError:
        pass


def file_size(name):
    '''Returns the size of file name in bytes.'''
    return os.stat(name)[6]


def tmp_dir():
    '''Creates a temporal directory and returns its name.'''
    return tempfile.mkdtemp()


def tmp_file():
    '''Creates a temporal file and returns its name.'''
    return tempfile.mkstemp()[1]


def file_exists(name):
    '''Tells wether file name exists.'''
    return os.path.exists(name)


def copy_file(src, dst):
    '''Copies a file from src to dst.'''
    shutil.copy(src, dst)


def copy_dir(src, dst):
    '''Copies a tree from src to dst.'''
    shutil.copytree(src, dst)


def move_file(src, dst):
    '''Moves a file from src to dst.'''
    shutil.move(src, dst)


def read_t64(src):
    '''Returns the t64 of directory src.'''
    tmp = tmp_file()
    create_tgz(tmp, ['.'], src)
    r = read_file(tmp)
    del_file(tmp)
    return base64.b64encode(r)


def write_t64(dst, t64):
    '''Writes in directory dst the t64 contents.'''
    tmp = tmp_file()
    write_file(tmp, base64.b64decode(t64))
    tar = tarfile.open(tmp, 'r:gz')
    mkdir(dst)
    cwd = os.getcwd()
    os.chdir(dst)
    for x in tar:
        tar.extract(x)
    tar.close()
    os.chdir(cwd)
    del_file(tmp)


def create_tar(name, filenames, path=None):
    '''Creates a tar file name with the contents given in the list of filenames.
    Uses path if given.'''
    if name == '-':
        tar = tarfile.open(mode='w|', fileobj=sys.stdout)
    else:
        tar = tarfile.open(name, 'w')
    if path:
        cwd = os.getcwd()
        os.chdir(path)
    for x in filenames:
        tar.add(x)
    if path:
        os.chdir(cwd)
    tar.close()


def create_tgz(name, filenames, path=None):
    '''Creates a tgz file name with the contents given in the list of filenames.
    Uses path if given.'''
    if name == '-':
        tar = tarfile.open(mode='w|gz', fileobj=sys.stdout)
    else:
        tar = tarfile.open(name, 'w:gz')
    if path:
        cwd = os.getcwd()
        os.chdir(path)
    for x in filenames:
        tar.add(x)
    if path:
        os.chdir(cwd)
    tar.close()


def extract_tar(name, path):
    '''Extracts a tar file in the given path.'''
    if name == '-':
        tar = tarfile.open(mode='r|', fileobj=sys.stdin)
    else:
        tar = tarfile.open(name)
    for x in tar:
        tar.extract(x, path)
    tar.close()


def extract_tgz(name, path):
    '''Extracts a tgz file in the given path.'''
    if name == '-':
        tar = tarfile.open(mode='r|gz', fileobj=sys.stdin)
    else:
        tar = tarfile.open(name, 'r:gz')
    for x in tar:
        tar.extract(x, path)
    tar.close()


def get_from_tgz(tgz, name):
    '''Returns the contents of file name inside a tgz or tar file.'''
    tar = tarfile.open(tgz)
    f = tar.extractfile(name)
    r = f.read()
    f.close()
    tar.close()
    return r


_dirs = []      # direectory stack for pushd and popd


def pushd(path=None):
    '''Pushes the current directory to the stack and cds to path if given.'''
    global _dirs
    _dirs.append(os.getcwd())
    if path:
        os.chdir(path)


def popd():
    global _dirs
    _dirs.append(os.getcwd())
    os.chdir(_dirs[-1])
    del _dirs[-1]


##############################################################################
# Property files
##############################################################################


def write_props(path, dic):
    '''Writes dictionary dic to file path as properties file.'''
    txt = ''
    for k, v in dic.iteritems():
        txt += "%s: %s\n" % (k, str(v))
    write_file(path, txt)


def read_props(path):
    '''Returns a dictionary with the properties of the file at path.'''
    dic = {}
    f = open(path)
    for l in f.readlines():
        try:
            k, v = l.split(":", 1)
            dic[k.strip()] = v.strip()
        except:
            pass
    return dic


##############################################################################
# YML utilites
##############################################################################


def print_yml(inf):
    print(yaml.dump(inf, indent=4, width=1000, default_flow_style=False))


def write_yml(path, inf):
    yaml.dump(inf, open(path, 'w'), indent=4, width=1000, default_flow_style=False)


def read_yml(path):
    return yaml.load(open(path, encoding='utf-8'), Loader=yaml.FullLoader)


##############################################################################
# Utilies on directories
##############################################################################


def del_dir(name):
    '''Deletes the directory name. Does not complain on error.'''
    try:
        shutil.rmtree(name)
    except OSError:
        pass


def mkdir(name):
    '''Makes the directory name. Does not complain on error.'''
    try:
        os.makedirs(name)
    except OSError:
        pass


def globd(path, pattern='*'):
    '''As glob.glob but given a directory path.'''
    cwd = os.getcwd()
    os.chdir(path)
    r = glob.glob(pattern)
    os.chdir(cwd)
    return r


##############################################################################
# Utilities on dates and times
##############################################################################


def current_time():
    '''Returns a string with out format for times.'''
    return time.strftime('%Y-%m-%d %H:%M:%S')


def current_date():
    '''Returns a string with out format for dates.'''
    return time.strftime('%Y-%m-%d')


##############################################################################
# Others
##############################################################################


def system(cmd):
    '''As os.system(cmd) but writes cmd.'''
    print(cmd)
    return os.system(cmd)


def cd_system(path, cmd):
    '''As os.system(cmd) but executes from directory path.'''
    print(cmd)
    pushd(path)
    r = os.system(cmd)
    popd()
    return r


def command(cmd):
    '''As os.system(cmd) but returns stdout as an string.'''
    return subprocess.getoutput(cmd)


def sort(L):
    '''Returns a copy of L in sorted order.'''
    C = L[:]
    C.sort()
    return C


def myprint(msg):
    '''Print the message msg in log format and flushes.'''
    print(current_time(), '-', msg)
    sys.stderr.flush()
    sys.stdout.flush()


def exc_traceback():
    '''Similar to traceback.print_exc but return a string rather than printing it.'''

    path = tmp_file()
    f = open(path, 'w')
    traceback.print_exc(file=f)
    f.close()
    r = read_file(path)
    del_file(path)
    return r


##############################################################################
# A class to lock files
##############################################################################

class Lock:

    def __init__(self, filename, shared=False, timeout=5, step=0.2):
        '''
        Create a lock object with a file filename

        timeout is the time in seconds to wait before timing out, when
        attempting to acquire the lock.
        step is the number of seconds to wait in between each attempt to
        acquire the lock.

        '''
        self.locked = False
        t = 0
        while True:
            t += step
            self.lockfile = open(filename, 'w')
            try:
                if shared:
                    fcntl.flock(self.lockfile.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB)
                else:
                    fcntl.flock(self.lockfile.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except IOError:
                if t < timeout:
                    time.sleep(step)
                else:
                    raise IOError('Failed to acquire lock on %s' % filename)
            else:
                self.locked = True
                return

    def unlock(self):
        '''
            Release the lock.
        '''
        if self.locked:
            fcntl.flock(self.lockfile.fileno(), fcntl.LOCK_UN)
            self.locked = False
            self.lockfile.close()

    def __del__(self):
        '''
            Auto unlock when object is deleted.
        '''
        self.unlock()


###########################################################################
# Daemon class.
# Adapted from http://www.livinglogic.de/Python/daemon/index.html
# jpetit: add handlers
# TODO: the pidfile should be checked with locks
###########################################################################


class Daemon(object):
    '''

    The Daemon class provides methods for starting and stopping a
    daemon process as well as handling command line arguments.

    This class is adapted from http://www.livinglogic.de/Python/daemon/index.html
    '''

    def __init__(self, stdin='/dev/null', stdout='/dev/null', stderr='/dev/null', pidfile=None, user=None, group=None):
        '''
        The stdin, stdout, and stderr arguments are file
        names that will be opened and be used to replace the standard file
        descriptors in sys.stdin, sys.stdout, and sys.stderr.
        These arguments are optional and default to '/dev/null'. Note that
        stderr is opened unbuffered, so if it shares a file with stdout then
        interleaved output may not appear in the order that you expect.

        pidfile must be the name of a file. :meth:start will write
        the pid of the newly forked daemon to this file. :meth:stop uses this
        file to kill the daemon.

        user can be the name or uid of a user. :meth:start will switch
        to this user for running the service. If user is None no
        user switching will be done.

        In the same way group can be the name or gid of a group.
        :meth:start will switch to this group.
        '''
        options = dict(
            stdin=stdin,
            stdout=stdout,
            stderr=stderr,
            pidfile=pidfile,
            user=user,
            group=group,
        )

        self.options = optparse.Values(options)

    def openstreams(self):
        '''
        Open the standard file descriptors stdin, stdout and stderr as specified
        in the constructor.
        '''
        si = open(self.options.stdin, 'r')
        so = open(self.options.stdout, 'a+')
        se = open(self.options.stderr, 'a+', 0)
        os.dup2(si.fileno(), sys.stdin.fileno())
        os.dup2(so.fileno(), sys.stdout.fileno())
        os.dup2(se.fileno(), sys.stderr.fileno())

    def handlesighup(self, signum, frame):
        '''
        Handle a SIG_HUP signal: Reopen standard file descriptors.
        '''
        self.openstreams()

    def handlesigterm(self, signum, frame):
        '''
        Handle a SIG_TERM signal: Remove the pid file and exit.
        '''
        if self.options.pidfile is not None:
            try:
                os.remove(self.options.pidfile)
            except Exception:
                pass
        self.handle_stop()
        sys.exit(0)

    def switchuser(self, user, group):
        '''
        Switch the effective user and group. If user and group are
        both None nothing will be done. user and group
        can be an :class:int (i.e. a user/group id) or :class:str
        (a user/group name).
        '''
        if group is not None:
            if isinstance(group, basestring):
                group = grp.getgrnam(group).gr_gid
            os.setegid(group)
        if user is not None:
            if isinstance(user, basestring):
                user = pwd.getpwnam(user).pw_uid
            os.seteuid(user)
            if 'HOME' in os.environ:
                os.environ['HOME'] = pwd.getpwuid(user).pw_dir

    def start(self):
        '''
        Daemonize the running script. When this method returns the process is
        completely decoupled from the parent environment.
        '''
        # Finish up with the current stdout/stderr
        sys.stdout.flush()
        sys.stderr.flush()

        # Do first fork
        try:
            pid = os.fork()
            if pid > 0:
                sys.exit(0)  # Exit first parent
        except OSError as exc:
            sys.exit('%s: fork #1 failed: (%d) %s\n' % (sys.argv[0], exc.errno, exc.strerror))

        # Decouple from parent environment
        os.chdir('/')
        os.umask(0)
        os.setsid()

        # Do second fork
        try:
            pid = os.fork()
            if pid > 0:
                sys.exit(0)  # Exit second parent
        except OSError as exc:
            sys.exit('%s: fork #2 failed: (%d) %s\n' % (sys.argv[0], exc.errno, exc.strerror))

        # Now I am a daemon!

        # Switch user
        self.switchuser(self.options.user, self.options.group)

        # Redirect standard file descriptors (will belong to the new user)
        self.openstreams()

        # Write pid file (will belong to the new user)
        if self.options.pidfile is not None:
            open(self.options.pidfile, 'wb').write(str(os.getpid()))

        # Reopen file descriptors on SIGHUP
        signal.signal(signal.SIGHUP, self.handlesighup)

        # Remove pid file and exit on SIGTERM
        signal.signal(signal.SIGTERM, self.handlesigterm)

        self.handle_start()

    def stop(self):
        '''
        Send a SIGTERM signal to a running daemon. The pid of the daemon
        will be read from the pidfile specified in the constructor.
        '''
        if self.options.pidfile is None:
            sys.exit('no pidfile specified')
        if not file_exists(self.options.pidfile):
            sys.exit('Cannot find pidfile. The daemon is not running?')
        try:
            pidfile = open(self.options.pidfile, 'rb')
        except IOError as exc:
            sys.exit('cannot open pidfile %s: %s' % (self.options.pidfile, str(exc)))
        data = pidfile.read()
        try:
            pid = int(data)
        except ValueError:
            sys.exit('mangled pidfile %s: %r' % (self.options.pidfile, data))
        os.kill(pid, signal.SIGTERM)

        self.handle_stop()

    def optionparser(self):
        '''
        Return an optparse parser for parsing the command line options.
        This can be overwritten in subclasses to add more options.
        '''
        p = optparse.OptionParser(usage='usage: %prog [options] (start|stop|restart|run)')
        p.add_option('--pidfile', dest='pidfile', help='PID filename (default %default)', default=self.options.pidfile)
        p.add_option('--stdin', dest='stdin', help='stdin filename (default %default)', default=self.options.stdin)
        p.add_option('--stdout', dest='stdout', help='stdout filename (default %default)', default=self.options.stdout)
        p.add_option('--stderr', dest='stderr', help='stderr filename (default %default)', default=self.options.stderr)
        p.add_option('--user', dest='user', help='user name or id (default %default)', default=self.options.user)
        p.add_option('--group', dest='group', help='group name or id (default %default)', default=self.options.group)
        return p

    def service(self, args=None):
        '''
        Handle command line arguments and start or stop the daemon accordingly.

        args must be a list of command line arguments (including the
        program name in args[0]). If args is None or
        unspecified sys.argv is used.

        The return value is true when a starting option has been specified as the
        command line argument, i.e. if the daemon should be started.

        The optparse options and arguments are available
        afterwards as self.options and self.args.
        '''
        p = self.optionparser()
        if args is None:
            args = sys.argv
        (self.options, self.args) = p.parse_args(args)
        if len(self.args) != 2:
            p.error('incorrect number of arguments')
            sys.exit(1)
        if self.args[1] == 'run':
            if file_exists(self.options.pidfile):
                sys.exit('Pidfile exists. The daemon is already running?')
                return False
            return True
        elif self.args[1] == 'restart':
            self.stop()
            self.start()
            return True
        elif self.args[1] == 'start':
            if file_exists(self.options.pidfile):
                sys.exit('Pidfile exists. The daemon is already running?')
                return False
            self.start()
            return True
        elif self.args[1] == 'stop':
            self.stop()
            return False
        else:
            p.error('incorrect argument %s' % self.args[1])
            sys.exit(1)

    def go(self):
        if self.service():
            self.work()

    def handle_start(self):
        pass

    def handle_stop(self):
        pass

    def work(self):
        pass
