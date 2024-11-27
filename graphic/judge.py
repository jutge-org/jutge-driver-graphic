#!/usr/bin/env python3

import subprocess
import os
import os.path
import sys
import glob
import logging
import math
import re
import traceback
import json

import compilers
import checkers

import util
import monitor


class Judge:

    def go(self):
        logging.info('<<<< start >>>>')
        self.init_phase()
        self.solution_phase()
        self.correction_phase()
        logging.info('<<<< end with veredict %s >>>>' % self.cor.veredict)

    def init_phase(self):
        """Initializes the data structures of the Judge object."""

        logging.info('**** init phase ****')

        self.dir = os.getcwd()

        self.env = Record()
        self.env.hostname = util.get_hostname()
        self.env.username = util.get_username()
        self.env.slave_id = sys.argv[1]
        self.env.time_beg = util.current_time()
        self.env.uname = ' '.join(os.uname())
        self.env.loadavg = '%.2f %.2f %.2f' % os.getloadavg()
        self.env.cwd = os.getcwd()

        self.sub = util.read_yml('submission/submission.yml')
        self.pbm = util.read_yml('problem/problem.yml')
        self.drv = util.read_yml('driver/driver.yml')
        self.hdl = util.read_yml('problem/handler.yml')
        self.sco = util.read_yml('problem/scores.yml') if util.file_exists('problem/scores.yml') else None

        self.tests = self.get_tests()

        self.cor = Record()
        self.sol = Record()
        self.pha = None  # will point to self.cor or self.sol latter on
        self.phase = None  # will be 'solution' or 'correction' latter on

        for x in [self.cor, self.sol]:
            x.veredict = 'IE'
            x.environment = self.env
            x.submission = self.sub
            x.problem = self.pbm
            x.driver = self.drv
            x.handler = self.hdl
            x.scores = self.sco
            x.preprocess = Record()
            x.compilation = Record()
            x.execution = Record()
            x.checking = Record()
            x.evaluation = Record()
            x.postprocess = Record()
            x.tests = {}
            for t in self.tests:
                x.tests[t] = {}

    def solution_phase(self):
        """Judges the reference solution."""

        logging.info('**** solution phase ****')

        os.chdir(self.dir + '/solution')
        self.phase = 'solution'
        self.pha = self.sol

        self.preprocess_step()
        if self.compilation_step():
            self.execution_step()
            self.checking_step()
            self.evaluation_step()
            self.postprocess_step()
        self.output_step()

    def correction_phase(self):
        """Judges the candidate solution."""

        logging.info('**** correction phase ****')

        os.chdir(self.dir + '/correction')
        self.phase = 'correction'
        self.pha = self.cor

        if self.sol.veredict != 'AC':
            self.cor.veredict = 'SE'
            # we create a directory with all the content to retrieve it latter and simplify debugging
            os.mkdir(self.dir + '/correction/setter.error')
            os.system("cp -r %s %s" % (self.dir + '/solution/*', self.dir + '/correction/setter.error'))
        else:
            self.preprocess_step()
            if self.compilation_step():
                self.execution_step()
                self.checking_step()
                self.evaluation_step()
                self.postprocess_step()
        self.output_step()

    def output_step(self):
        self.env.time_end = util.current_time()
        data = todict(self.pha)
        path = '%s/%s/%s.yml' % (self.dir, self.phase, self.phase)
        util.write_yml(path, data)

    def preprocess_step(self):
        logging.info('---- preprocess step ----')

        if not monitor.is_suid_root():
            self.pha.preprocess.vinga64suid = False
            raise Exception('vinga64 is not suid root')
        else:
            self.pha.preprocess.vinga64suid = True

    def compilation_step(self):
        logging.info('---- compilation step ----')

        inf = self.pha.compilation

        inf.compilers = cpls = self.get('compilers', 'any')
        inf.compiler = cpl = self.get('compiler_id')

        if cpls != 'any' and cpl not in cpls:
            raise Exception('invalid compiler_id (%s)' % cpl)

        if self.phase == 'correction':
            # estudiant
            com = compilers.compiler(cpl, self.hdl)
        else:
            # professor
            com = self.choose_solution_compiler()
            # hack for MyPy
            if cpl == 'MyPy' and util.file_exists('../problem/solution.py'):
                logging.info('MyPy hack')
                com = compilers.compiler('Python3', self.hdl)

        choosen_compiler = str(com.__class__).split("_")[1][:-2]
        self.pha.compilation.choosen_compiler = choosen_compiler
        self.cor.compilation.versus_compiler = choosen_compiler
        logging.info('---> chosen compiler: %s' % choosen_compiler)

        inf.language = com.language()
        inf.version = com.version()
        inf.flags1 = com.flags1()
        inf.flags2 = com.flags2()
        inf.extension = ext = com.extension()

        if util.file_exists('../problem/judge.hs'):
            util.copy_file('../problem/judge.hs', '.')
        if util.file_exists('../problem/judge.py'):
            util.copy_file('../problem/judge.py', '.')

        if self.phase == 'correction':
            # estudiant
            util.copy_file('../submission/program.' + ext, '.')
        else:
            # professor
            if cpl == 'PRO2':
                if util.file_exists('../problem/solution.cc'):
                    util.copy_file('../problem/solution.cc', 'program.cc')
                elif util.file_exists('../problem/solution.hh'):
                    util.copy_file('../problem/solution.hh', 'program.cc')
                else:
                    raise Exception('cannot find solution.hh|.cc')
            elif cpl == 'MakePRO2':
                if util.file_exists('../problem/solution.tar'):
                    util.copy_file('../problem/solution.tar', 'program.tar')
                else:
                    raise Exception('cannot find solution.tar')
            elif util.file_exists('../problem/solution.' + ext):
                util.copy_file('../problem/solution.' + ext, 'program.' + ext)
            else:
                raise Exception('cannot find solution.' + ext)

        ok = com.compile()
        if not ok:
            self.pha.veredict = 'CE'
        return ok

    def choose_solution_compiler(self):
        """Returns the best matched compiler among the possible ones in the solution for the compiler selected in the submission."""

        # get requested compiler and its entension
        cpl = self.get('compiler_id')
        com = compilers.compiler(cpl, self.hdl)
        ext = com.extension()

        # see if there is just one possible compiler
        comps = self.get('compilers', '').split()
        if len(comps) == 1:
            self.sol.compilation.match = 'only one possible'
            return compilers.compiler(comps[0], self.hdl)

        # test if there is a solution with the same extension
        if util.file_exists('../problem/solution.%s' % ext):
            # yes, there is a solution for the same compiler
            self.sol.compilation.match = 'exact'
            return com
        else:
            # no, we need to find another one, at this point we choose according to three categoiries
            slows = 'bf erl js lisp lua php pl py R rb ws'.split()
            mediums = 'bas cs java scm'.split()
            fasts = 'ada c cc d f go hs pas'.split()

            if ext in fasts and util.file_exists('../problem/solution.cc'):
                self.sol.compilation.match = 'fast'
                return compilers.compiler('GXX11', self.hdl)
            if (ext in fasts or ext in mediums) and util.file_exists('../problem/solution.java'):
                self.sol.compilation.match = 'medium'
                return compilers.compiler('JDK', self.hdl)
            if util.file_exists('../problem/solution.cc'):
                self.sol.compilation.match = 'c++ fallback'
                return compilers.compiler('GXX11', self.hdl)
            if util.file_exists('../problem/solution.java'):
                self.sol.compilation.match = 'java fallback'
                return compilers.compiler('JDK', self.hdl)
            if util.file_exists('../problem/solution.py'):
                self.sol.compilation.match = 'py fallback'
                return compilers.compiler('Python3', self.hdl)

            raise Exception('Could not find suitable compiler')

    def execution_step(self):
        logging.info('---- execution step ----')

        self.pha.execution.continue_on_ee = self.get('continue_on_ee', False) or self.pha.scores is not None

        for test in self.tests:
            os.chdir(self.dir + '/' + self.phase)
            exe = {}
            self.execution_one_test(exe, test)
            self.pha.tests[test] = exe
            if exe['execution'] != 'OK' and not self.pha.execution.continue_on_ee:
                break

    def execution_one_test(self, exe, test):
        com = compilers.compiler(self.pha.compilation.choosen_compiler)

        # Create the subdirectory and copy .inp and .ops files
        testdir = test + '.dir'
        util.mkdir(testdir)
        os.chdir(testdir)
        util.copy_file('../../problem/%s.inp' % test, '.')
        for f in glob.glob('../../problem/%s.ops' % test):
            util.copy_file(f, '.')
        for f in glob.glob('../../problem/%s.*.ops' % test):
            util.copy_file(f, '.')

        # Get execution options
        if util.file_exists('%s.ops' % test):
            ops = util.read_file('%s.ops' % test).strip()
        else:
            ops = ''

        # In the case of correction step, limit ressources with values from solution step
        if self.phase == 'correction':
            cputime = float(self.sol.tests[test]['cputime'])
            clktime = float(self.sol.tests[test]['clktime'])
            filesze = util.file_size('../../problem/%s.cor' % test) / (1024.0 * 1024.0)
            # !!! A generic way to fix new relative limits should exist
            cputime = max(0.1, 2.0 * cputime + 0.1)
            if self.pha.compilation.choosen_compiler == 'JDK':
                cputime = max(0.5, cputime)
            limtime = int(cputime + 1.5)
            clktime = max(3 * limtime, 2.0 * clktime)

            jdelgado = self.get('author') == "U24827"
            if jdelgado:
                logging.info('**** Jordi Delgado detected ****')

            filesze = max(1, int(math.ceil(2.0 * filesze)))
            ops += ' --maxtime=%f:%i:%i --maxoutput=%i' % (cputime, limtime, clktime, filesze)

            if jdelgado:
                cputime = 40
                limtime = 60
                clktime = 70
                ops = ' --maxtime=%f:%i:%i --maxoutput=%i' % (cputime, limtime, clktime, filesze)

            util.write_file('%s.ops' % test, ops)

        # Create the required files (i.e. executable)
        com.prepare_execution('..')

        # Execute the program on the test
        try:
            com.execute(test)
        except compilers.ExecutionError:
            success = False
        else:
            success = True

        # Move the files up
        for ext in ('inp', 'out', 'err', 'log', 'res'):
            # the following check is due to a difficult bug we once had
            if not util.file_exists(test + '.' + ext):
                raise Exception('%s missing!!!' % (test + '.' + ext,))
            else:
                util.move_file(test + '.' + ext, '..')
        if not util.file_exists('output.png'):
            util.copy_file(self.dir + '/driver/etc/notfound.png', '../'+test+'.out')
        else:
            util.move_file('output.png', '../'+test+'.out')
        if util.file_exists(test+'.dif.png'):
            util.move_file(test+'.dif.png', '..')
        if util.file_exists('exception.txt'):
            util.del_file('../%s.exc' % test)
            util.move_file('exception.txt', '../%s.exc' % test)

        # Remove the subdirectory
        os.chdir('..')
        util.del_dir(testdir)

        # Update exe with the execution result and add the options
        res = util.read_yml(test + '.res')
        for k, v in res.items():
            exe[k] = v
        exe['monitor_options'] = ops

    def checking_step(self):

        logging.info('---- checking step ----')
        logging.info(subprocess.run("ls -laR", capture_output=True, text=True, shell=True).stdout)
        logging.info(subprocess.run("ls -laR %s'/problem" % self.dir, capture_output=True, text=True, shell=True).stdout)

        self.pha.checking.checker = checker = self.get('checker', 'std')
        self.pha.checking.presentation_error = presentation_error = self.get('presentation_error', True)
        t = None
        try:
            t = self.get('tolerance', None)
        except:
            pass
        self.pha.checking.tolerance = tolerance = t

        for test in self.tests:
            logging.info('---- checking step %s ----', test)
            inf = self.pha.tests[test]
            logging.info(str(inf))
            out = test + '.out'
            dif = test + '.dif.png'
            cor = self.dir + '/problem/' + test + '.cor'
            inp = '../problem/' + test + '.inp'
            if 'execution' not in inf:
                inf['veredict'] = '??'
            elif util.file_exists(test + ".exc"):
                inf['veredict'] = 'EE'
                inf['veredict_info'] = "Uncaught exception " + open(test + ".exc").readline().strip()
            elif inf['execution'] == 'EE':
                inf['veredict'] = 'EE'
                inf['veredict_info'] = inf['execution_error']
            else:
                if not os.path.exists(out):
                    out = test + '.workdir/output.png'
                logging.info('using %s %s', out, cor)
                ver = checkers.graphic(out, cor, dif, tolerance)
                logging.info('   = veredict for %s: %s' % (test, ver))
                inf['veredict'] = ver

    def evaluation_step(self):
        logging.info('---- evaluation step ----')
        if self.pha.scores is None:
            ver, ver_info = self.standard_evaluation()
            self.pha.veredict = ver
            if ver_info:
                self.pha.veredict_info = ver_info
        else:
            ver, score, scores = self.scores_evaluation()
            self.pha.veredict = ver
            self.pha.scores = tweak(scores)
            self.pha.score = score

    def standard_evaluation(self):
        logging.info('.... standard_evaluation ....')
        return self.eval_veredict(self.tests)

    def eval_veredict(self, tests):
        inf = self.pha.tests
        # Search if IE
        for test in tests:
            if inf[test]['veredict'] == 'IE':
                return ('IE', None)
        # Search if SE
        for test in tests:
            if inf[test]['veredict'] == 'SE':
                return ('SE', None)
        # Search if EE
        for test in tests:
            if inf[test]['veredict'] == 'EE':
                return ('EE', inf[test]['veredict_info'])
        # Search WAs
        for test in tests:
            if inf[test]['veredict'] == 'WA':
                return ('WA', None)
        # Search ICs
        for test in tests:
            if inf[test]['veredict'] == 'IC':
                return ('IC', None)
        # Search PEs
        for test in tests:
            if inf[test]['veredict'] == 'PE':
                return ('PE', None)
        # AC!
        return ('AC', None)

    def scores_evaluation(self):
        logging.info('.... scores_evaluation ....')
        parts = []
        points = 0
        total_points = 0
        for part in self.pha.scores:
            s = {}
            s['part'] = part['part']
            s['prefix'] = part['prefix']
            s['tests'] = []
            s['points'] = 0
            total_points += part['points']
            for test in self.tests:
                if test.startswith(part['prefix']):
                    s['tests'].append(test)
            ver, ver_info = self.eval_veredict(s['tests'])
            s['veredict'] = ver
            s['veredict_info'] = ver_info
            if ver == 'AC':
                s['points'] = part['points']
                points += part['points']
            parts.append(s)
        score = '%i/%i' % (points, total_points)
        if points == total_points:
            return ('AC', score, parts)
        else:
            return ('SC', score, parts)

    def postprocess_step(self):
        logging.info('---- postprocess step ----')

        os.chdir(self.dir + '/' + self.phase)
        self.pha.postprocess.del_files = self.get('del_files', True)
        if self.pha.postprocess.del_files:
            util.del_file('program.exe')
            # TBD: other program files as *.class should be deleted
            for f in glob.glob('*.inp'):
                util.del_file(f)
            for f in glob.glob('*.wrk'):
                util.del_file(f)
            for f in glob.glob('*.res'):
                util.del_file(f)
            for f in glob.glob('*.err'):
                if util.file_size(f) == 0:
                    util.del_file(f)
            for f in glob.glob('compilation[12].txt'):
                if util.file_size(f) == 0:
                    util.del_file(f)
            if self.pha.veredict == 'AC':
                for f in glob.glob('*.out'):
                    util.del_file(f)

    def get_tests(self):
        """Returns the list of tests, in sorted order, with sample* first."""

        # get the tests without extensions nor paths
        tests = [
            t.replace('.inp', '').replace(self.dir + '/problem/', '')
            for t in glob.glob(self.dir + '/problem/*.inp')
        ]

        # sort the tests
        publics = []
        privates = []
        for t in tests:
            if re.match('^sample', t):
                publics.append(t)
            else:
                privates.append(t)

        # return sorted tests
        return sorted(publics) + sorted(privates)

    def get(self, opt, default=None):
        val = None
        if opt in self.sub:
            val, whe = self.sub[opt], 'submission'
        elif opt in self.pbm:
            val, whe = self.pbm[opt], 'problem'
        elif opt in self.drv:
            val, whe = self.drv[opt], 'driver'
        elif opt in self.hdl:
            val, whe = self.hdl[opt], 'handler'
        else:
            val, whe = default, 'default'
        if val is None:
            raise Exception('missing option (%s)' % opt)
        info = str(val) + ' (' + whe + ')'
        # if opt not in self.wrk['used_options'] or self.wrk['used_options'][opt] != info:
        # self.wrk['used_options'][opt] = info
        logging.info('   > using %s for %s from %s' % (str(val), opt, whe))
        return val


def tweak(xs):
    # resulta que el yaml del php no enten les seqs com les escriu el yaml del python
    # aixi que passo la seq a dic, que si que van be
    r = {}
    c = 0
    for x in xs:
        r[c] = x
        c = c + 1
    return r


def todict(obj, classkey=None):
    # http://stackoverflow.com/questions/1036409/recursively-convert-python-object-graph-to-dictionary
    if isinstance(obj, dict):
        data = {}
        for (k, v) in obj.items():
            data[k] = todict(v, classkey)
        return data
    elif hasattr(obj, "_ast"):
        return todict(obj._ast())
    elif hasattr(obj, "__iter__") and not isinstance(obj, str):
        return [todict(v, classkey) for v in obj]
    elif hasattr(obj, "__dict__"):
        data = dict([(key, todict(value, classkey))
                     for key, value in obj.__dict__.items()
                     if not callable(value) and not key.startswith('_')])
        if classkey is not None and hasattr(obj, "__class__"):
            data[classkey] = obj.__class__.__name__
        return data
    else:
        return obj


class Record:
    """Just to have an object to fill with fields."""
    pass


###########################################################################################################
# main
###########################################################################################################

if __name__ == '__main__':
    try:
        d = os.getcwd()
        util.write_file(d + '/correction/correction.yml', 'veredict: IE\ninternal_error: very severe\n')
        util.init_logging()
        judge = Judge()
        judge.go()
        # print json.dumps(judge, default=lambda obj: vars(obj), indent=4)
        sys.exit(0)
    except Exception as e:
        util.write_file(d + '/correction/correction.yml', 'veredict: IE\ninternal_error: %s\n' % e)
        logging.info('!!!! exception caught !!!!')
        logging.info(e)
        print(e, file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        print(json.dumps(judge, default=lambda obj: vars(obj), indent=4), file=sys.stderr)
        sys.exit(1)
