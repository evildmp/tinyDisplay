# -*- coding: utf-8 -*-
# Copyright (c) 2020 Ron Ritchey and contributors
# See License.rst for details

"""
Utility functions to support tinyDisplay

.. versionadded:: 0.0.1
"""

import builtins, os, time, json
from threading import Thread, Event, RLock
from queue import Queue, Empty
from copy import deepcopy
from collections import deque

from simple_pid import PID



class animate(Thread):
    def __init__(self, Kp=1, Ki=0.1, Kd=0.05, cps=1, function=None, queueSize=10, *args, **kwargs):
        Thread.__init__(self)
        assert function, 'You must supply a function to animate'
        self._speed = 1/cps
        self._pid = PID(Kp, Ki, Kd, setpoint = self._speed, sample_time=self._speed)

        self._function = function
        self._args = args
        self._kwargs = kwargs

        self.fps = 0
        self._running = True
        self._queue = Queue(maxsize=queueSize)
        self._event = Event()
        self._forceEvent = Event()

    @property
    def empty(self):
        return self._queue.empty()

    @property
    def full(self):
        return self._queue.full()

    @property
    def qsize(self):
        return self._queue.qsize()

    def pause(self):
        self._event.clear()

    def restart(self):
        self._event.set()

    def toggle(self):
        if self._event.isSet():
            self._event.clear()
        else:
            self._event.set()

    def stop(self):
        self._running = False
        self._event.set()
        self.get()
        self.join()

    def force(self, *args, **kwargs):
        self._Force = True

        # Set new arguments for animated function
        self._args = args
        self._kwargs = kwargs

        # If needed, unblock run if the queue if full
        try:
            self._queue.get_nowait()
            self._queue.task_done()
        except Empty:
            pass

        # Wait until animate confirms force is finished
        self._forceEvent.clear()
        self._forceEvent.wait()

    def get(self, wait=0):

        try:
            retval = self._queue.get(wait)
            self._queue.task_done()
        except Empty:
            retval = None

        return retval

    def _emptyQueue(self):
        while True:
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except Empty:
                break


    def _invoke(self, *args, **kwargs):
        # Invoke function
        if args and kwargs:
            retval = self._function(*args, **kwargs)
        elif args:
            retval = self._function(*args)
        elif kwargs:
            retval = self._function(**kwargs)
        else:
            retval = self._function()
        return retval


    def run(self):
          correction = 0
          loopTime = self._speed

          renderTimer = time.time()
          renderCounter = 0
          self._event.set()
          self._Force = False

          while self._running:

              # Compute current FPS every 5 seconds
              renderCounter += 1
              if renderTimer + 5 < time.time():
                  self.fps = renderCounter/5
                  renderCounter = 0
                  renderTimer = time.time()

              # Disable pid while waiting to be activated
              self._pid.set_auto_mode(False)
              self._event.wait()

              # Activated!  Re-enable PID, begin processing
              self._pid.set_auto_mode(True, last_output=correction)
              correction = self._pid(loopTime)
              startLoop = time.time()
              if self._speed + correction > 0:
                  time.sleep(self._speed + correction)


              # Disable PID while trying to place new render in queue
              self._pid.set_auto_mode(False)
              putStart = time.time()
              if self._Force:
                  self._Force = False
                  self._emptyQueue()

                  # Must put value in queue before clearing the forceRender Event
                  # so that the forced render receives the newly computed value
                  retval = self._invoke(*self._args, **self._kwargs)
                  self._queue.put( retval )
                  self._forceEvent.set()
              else:
                  retval = self._invoke(*self._args, **self._kwargs)
                  self._queue.put( retval )

              # Correct the loop timer if queue was blocked and restart the PID
              startLoop = startLoop + (time.time()-putStart)
              self._pid.set_auto_mode(True, last_output=correction)

              loopTime = time.time() - startLoop






class dataset():
    '''
    Used to manage data that tinyDisplay will use to render widgets and test conditions

    '''

    def __init__(self, data=None, dataset=None, suppressErrors=False, returnOnError='', historySize=100):
        '''
        Initialize the dataset with the dictionary provided in 'data' (or optionally 'dataset').
        All keys at the root of the data dictionary must be strings as they will become
        the names of the databases contained within the dataset
        '''

        if data and dataset:
            raise RuntimeError(f'You must provide data or a dataset but not both')

        dataset = data or dataset or {}
        for tk in ( (False, i) if type(i) is not str else (True, i) for i in dataset.keys() ):
            if not tk[0]:
                raise ValueError(f'All datasets within a database must use strings as names.  This dataset has a database named {tk[1]}')

        self._suppressErrors = suppressErrors
        self._returnOnError = returnOnError

        # Set the number updates that the dataset will store
        self._historySize = int(historySize)
        if self._historySize < 1:
            raise ValueError(f'Requested history size "{self._historySize}" is too small.  It must be at least one.')

        # Initialize empty dataset
        self._dataset = {}

        # Start the clock
        self._startedAt = time.time()

        ''' Initialize starting position.  This dictionary holds a version of the
            dataset that can be safely walked forward from through all of the updates
            in the ring buffer to get to current state '''
        self._dsStart = {}

        # Initialize ring buffer which will hold each update
        self._ringBuffer = deque(maxlen=self._historySize)

        # Set self.update to initial update method
        self.update = self._update

        # Initialize prev dataset
        self._prevDS = {}
#        self.__dict__['prev'] = self._Data(self._prevDS)

        # If data was provided during initialization, update the state of the dataset with it
        if dataset:
            for k in dataset:
                self.update(k, dataset[k])

        # Create evaluate object to evaluate statements for this dataset
        self._eval = evaluate(dataset = self)

    def eval(self, *args, **kwargs):
        if 'suppressErrors' not in kwargs:
            kwargs['suppressErrors'] = self._suppressErrors
        if 'returnOnError' not in kwargs:
            kwargs['returnOnError'] = self._returnOnError

        return self._eval.eval(*args, **kwargs)

    def compile(self, *args, **kwargs):
        return self._eval.compile(*args, **kwargs)

    def __getitem__(self, key):
        if key == 'prev':
            return self._Data(self.prev)
        return self._dataset[key]

    def __iter__(self):
        self._dataset['prev'] = self._Data(self.prev)
        return iter(self._dataset)

    def __len__(self):
        return len(self._dataset)

    def __repr__(self):
        return self._dataset.__repr__()

    def _checkForReserved(self, dbName):
        if dbName in self.__class__.__dict__:
            raise NameError(f'{dbName} is a reserved name and cannot be used witin a dataset')

    def keys(self):
        return self._dataset.keys()

    def add(self, dbName, db):
        '''
        Add a new database to the dataset
        '''
        # Make sure we don't overwrite existing database.
        # Use update instead to modify existing database
        if dbName in self._dataset:
            raise NameError(f'{dbName} already exists in dataset')

        self.update(dbName, db)

    def _baseUpdate(self, dbName, update):
        '''
        Update database named dbName using the dictionary contained within update.
        '''
        # Add timestamp to update
        update['__timestamp__'] = time.time()-self._startedAt

        if dbName not in self._dataset:
            self._checkForReserved(dbName)
            d = update
            # Initialize _prevDS with current values
            self._prevDS[dbName] = d
        else:
            # Update prevDS with the current values that are about to get updated
            self._prevDS[dbName]= { **self._prevDS[dbName], **self._dataset[dbName] }

            # Merge current db values with new values
            d = { **self._dataset[dbName], **update }

        self.__dict__[dbName] = d
        self._dataset[dbName] = d
        self._ringBuffer.append( { dbName: update })

    def _update(self, dbName, update):
        ''' Initial update method used when _ringBuffer is not full '''

        self._baseUpdate(dbName, update)

        # If the ringBuffer has become full switch to _updateFull from now on
        if len(self._ringBuffer) == self._ringBuffer.maxlen:
            self.update = self._updateFull


    def _updateFull(self, dbName, update):
        ''' Adds updating of starting position when the ring buffer has become full '''

        # Add databases from oldest ringbuffer entry into dsStart if dsStart does not already contain them
        for db in self._ringBuffer[0]:
            if db not in self._dsStart:
                self._dsStart[db] = self._ringBuffer[0][db]

        # Merge values that already exist in dsStart
        for db in self._dsStart:
            if db in self._ringBuffer[0]:
                self._dsStart[db] = { **self._dsStart[db], **self._ringBuffer[0][db] }

        self._baseUpdate(dbName, update)


    def save(self, filename):
        with open(filename, 'w') as fn:
            fn.write(f'# STARTED AT: {self._startedAt}\n{json.dumps(self._dsStart)}\n')
            fn.write('\n# UPDATES\n')
            for item in self._ringBuffer:
                fn.write(json.dumps(item))
                fn.write('\n')

    def history(self, dbName, back):
        '''
        Returns the version of the database {versions} back from the current one
        If version does not exist, return the oldest version that does.

        Note: history(0) would return the current version and history(1) is equivelant to prev()
        '''
        dbUpdates = [v for v in self._ringBuffer if dbName in v]

        d = deepcopy(self._dsStart[dbName]) if dbName in self._dsStart else {}
        for i in range(len(dbUpdates)-abs(back)):
            d = { **d, **dbUpdates[i] }
        return self._Data(d)

    class _Data(dict):
        def __init__(self, *args, **kwargs):
            self.update(dict(*args, **kwargs))
            for k, v in self.items():
                self.__dict__[k] = v


    @property
    def prev(self):
        '''
        Returns a dataset composed of the version of the databases that is one update behind the current versions
        '''
        return self._Data(self._prevDS)




class evaluate():

    __allowedBuiltIns = {
        '__import__': builtins.__import__,
        'abs': builtins.abs,
        'bin': builtins.bin,
        'bool': builtins.bool,
        'bytes': builtins.bytes,
        'chr': builtins.chr,
        'dict': builtins.dict,
        'float': builtins.float,
        'format': builtins.format,
        'hex': builtins.hex,
        'int': builtins.int,
        'len': builtins.len,
        'list': builtins.list,
        'max': builtins.max,
        'min': builtins.min,
        'oct': builtins.oct,
        'ord': builtins.ord,
        'round': builtins.round,
        'str': builtins.str,
        'sum': builtins.sum,
        'tuple': builtins.tuple,
        'time': time
    }
    __allowedMethods = [
        'get',
        'lower',
        'upper',
        'capitalize',
        'title',
        'find',
        'strftime',
        'gmtime',
        'localtime',
        'timezone'
    ]

    def __init__(self, dataset = None):
        self._dataset = dataset
        self._allowedBuiltIns = dict(self.__allowedBuiltIns)
        self._changed = {}
        self._allowedBuiltIns['changed'] = self._isChanged
        self._allowedBuiltIns['select'] = self._select
        self._allowedBuiltIns['history'] = self._dataset.history
        self._allowedMethods = list(self.__allowedMethods)

        ''' Used to support methods that will be called by eval but need to be
            able to distinguish which object is calling it (e.g. changed)
            _evalLock protects usage of _currentCodeID if this code is used
            in a multithreaded application.  '''
        self._currentCodeID = None
        self._evalLock = RLock()

    def _isChanged(self, value):
        ret = False if self._currentCodeID not in self._changed else True if self._changed.get(self._currentCodeID) != value else False
        self._changed[self._currentCodeID] = value
        return ret

    @staticmethod
    def _select(value, *args, **kwargs):
        if len(args)%2 !=0:
            raise TypeError('TypeError: {args} is not an even number of arguments which is required for select transformations')
        for i in range(0, len(args), 1):
            if value == args[i]:
                return args[i+1]
        return ''


    def compile(self, input, dataset=None, data=None):
        if data and dataset:
            raise RuntimeError(f'You can provide data or a dataset but not both')

        dataset = dataset if dataset else data if data else {}
        code = compile(input, "<string>", "eval")
        for name in code.co_names:
            if name not in self._allowedBuiltIns and name not in self._allowedMethods and name not in self._dataset and name not in dataset:
                raise NameError(f'While compiling \'{input}\' discovered {name} which is not a valid function or variable')
        return (code, input)


    def eval(self, f, dataset=None, data=None, suppressErrors=False, returnOnError=''):
        if data and dataset:
            raise RuntimeError(f'You can provide data or a dataset but not both')
        dataset = dataset if dataset else data if data else None

        d = { **self._dataset, **dataset } if dataset else self._dataset

        # If we've receive a tuple it was hopefully produced by evaluate.compile
        f, s = f if type(f) == tuple else (f, None)

        # If we've received a compilation from evaluate.compile, evaluate it and return the answer
        if f.__class__.__name__ == 'code':
            retval = self._eval(f, d, s, suppressErrors=suppressErrors, returnOnError=returnOnError)
            return retval
        # If we've received a method or function, execute it and return the answer
        elif f.__class__.__name__ in ['method', 'function']:
            return f(self._dataset)
        else:
        # If we've received anything else, it could be from a variable that is only optionally dynamic (e.g. evaluatable)
        # In this case, the value did not need to be calculated so return it back to the calling method
            return f


    def _eval(self, code, variables, input, suppressErrors=True, returnOnError=''):

        ''' If suppressErrors set, return returnOnError value when KeyError or TypeError is thrown.
            This in effect causes widgets to be blank when there is an error in the evaluated statement
            (such as a missing key in the dataset) '''

        # Need to protect evaluation due to shared self._currentCodeID possibility
        self._evalLock.acquire()
        self._currentCodeID = id(code)
        try:
            return eval(code, { '__builtins__': self._allowedBuiltIns }, variables )
        except KeyError as e:
            if suppressErrors:
                return returnOnError
            raise KeyError(f'KeyError: {e} while trying to evaluate {input}')
        except TypeError as e:
            if suppressErrors:
                return returnOnError
            raise TypeError(f'Type Error: {e} while trying to evalute {input}')
        except AttributeError as e:
            raise AttributeError(f'Attribute Error: {e} while trying to evalute {input}')
        finally:
            self._evalLock.release()


def printImage(img):
    print ('-'*(img.size[0]+2))
    for j in range(img.size[1]):
        s = ''
        for i in list(img.crop( (0, j, img.size[0], j+1)).tobytes()):
            s += f'{i:>08b}'.replace('0', ' ').replace('1', '*')
        print (f'|{s[0:img.size[0]]}|')
    print ('-'*(img.size[0]+2))
