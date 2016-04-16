from sys import version_info
import dis

PY3 = version_info[0] == 3

if PY3:
    xrange = range


def rebuild_code(func_code, mapping):
    co_argcount = func_code.co_argcount
    co_nlocals = func_code.co_nlocals
    co_stacksize = func_code.co_stacksize
    co_flags = func_code.co_flags
    co_code = func_code.co_code
    co_consts = func_code.co_consts
    co_names = func_code.co_names
    co_varnames = func_code.co_varnames
    co_filename = func_code.co_filename
    co_name = func_code.co_name
    co_firstlineno = func_code.co_firstlineno
    co_lnotab = func_code.co_lnotab
    co_freevars = func_code.co_freevars
    co_cellvars = func_code.co_cellvars

    if PY3:
        code = (b for b in co_code)
        co_kwonlyargcount = func_code.co_kwonlyargcount
    else:
        code = (ord(b) for b in co_code)

    code_list = []
    names = list(co_names)
    names_consts = {}
    consts = list(co_consts)
    while True:
        # fetch next opcode. stop if we already at the end
        try:
            opcode, arg = next(code), None
        except StopIteration:
            break

        # skip functions with unknown opcodes
        if opcode == dis.EXTENDED_ARG:
            code_list.append(opcode)
            if arg is not None:
                code_list.extend(arg)

            code_list.extend(list(code))
            break

        # fetch argument
        elif opcode >= dis.HAVE_ARGUMENT:
            arg = [next(code) for _ in range(2)]

        # interesting opcode
        if opcode == dis.opmap['LOAD_GLOBAL']:
            # arg is an index in co_names list
            name_pos = arg[0] + arg[1]*256
            name = names[name_pos]
            # map only requested names
            if name in mapping:
                # create const for name if its not created yet
                if name not in names_consts:
                    # put the value from global scope to const
                    consts.append(mapping[name])
                    # ...and save index for future use
                    names_consts[name] = len(consts) - 1
                # change opcode and arg to const
                opcode = dis.opmap['LOAD_CONST']
                arg = reversed(divmod(names_consts[name], 256))

        # append opcode, with args if any, to new codestring
        code_list.append(opcode)
        if arg is not None:
            code_list.extend(arg)

    # construct new code string
    if PY3:
        byte_code = bytes(code_list)
    else:
        byte_code = ''.join(map(chr, code_list))

    # prepare arguments to the function object
    fc_args = [co_argcount]
    if PY3:
        fc_args.append(co_kwonlyargcount)

    fc_args.extend([
        co_nlocals, co_stacksize,  co_flags, byte_code, tuple(consts),
        co_names, co_varnames, co_filename, co_name, co_firstlineno,
        co_lnotab, co_freevars, co_cellvars
    ])

    # construct function object
    return type(func_code)(*fc_args)


def constantize(*dargs, **dkwargs):
    dkwargs.update({k.__name__: k for k in dargs})

    def constantize_decorator(f):
        if PY3:
            func_closure = f.__closure__
            func_defaults = f.__defaults__
            func_doc = f.__doc__
            func_name = f.__name__
            func_code = f.__code__
            func_dict = f.__dict__
            func_globals = f.__globals__
        else:
            func_closure = f.func_closure
            func_defaults = f.func_defaults
            func_doc = f.func_doc
            func_name = f.func_name
            func_code = f.func_code
            func_dict = f.func_dict
            func_globals = f.func_globals

        return type(f)(rebuild_code(func_code, dkwargs), func_globals,
                       func_name, func_defaults, func_closure)

    return constantize_decorator


if __name__ == '__main__':
    def test(b):
        res = []
        for c in b:
            if isinstance(c, (tuple, list)):
                res.append(len(c))

    ctest = constantize(*(len, isinstance, list, tuple))(test)

    # you should use it like written below
    # I use another style here to be sure that functions are the same

    # @constantize(*(len, isinstance, list, tuple))
    # def ctest(b):
    #     res = []
    #     for c in b:
    #         if isinstance(c, (tuple, list)):
    #             res.append(len(c))

    # display bytecode of functions
    print("==== original code ====")
    dis.dis(test)
    print("==== patched code  ====")
    dis.dis(ctest)

    # sanity check before timeit
    assert test != ctest
    test([[]])
    ctest([[]])

    import timeit
    timeit_setup = """from __main__ import test, ctest
param = sum(([(),None,[]] for _ in range(100)), [])"""
    avg = lambda x: sum(x)/len(x)
    single_run = lambda x: timeit.timeit(x, timeit_setup, number=10000)
    batch_run = lambda x, y: [single_run(x) for _ in xrange(y)]

    # remove best/worst time from batch_run and get avg
    stat_run = lambda x, y: avg(sorted(batch_run(x, y))[1:-1])
    original = stat_run('test(param)', 10)
    patched = stat_run('ctest(param)', 10)
    print('%s/%s=%s' % (patched, original, patched/original))
