'''
function-context

generic tools for working in the context of a function.
'''

import __builtin__
import logging,re,itertools
import six,types

import database,structure,ui,internal
import instruction as _instruction
from internal import utils,interface

import idaapi

if False:
    class instance(object):
        # FIXME: finish this
        class chunk_t(object):
            pass

        @classmethod
        def by_address(cls, ea):
            n = idaapi.get_fchunk_num(ea)
            f = idaapi.getn_func(n)
            return cls.getIndex(n)

## searching
@utils.multicase()
def by_address():
    '''Return the function at the current address.'''
    return by_address(ui.current.address())
@utils.multicase(ea=six.integer_types)
def by_address(ea):
    '''Return the function containing the address ``ea``.'''
    ea = interface.address.within(ea)
    res = idaapi.get_func(ea)
    if res is None:
        raise LookupError("{:s}.by_address(0x{:x}) : Unable to locate function".format(__name__,ea))
    return res
byAddress = by_address

def by_name(name):
    '''Return the function with the name ``name``.'''
    ea = idaapi.get_name_ea(-1, name)
    if ea == idaapi.BADADDR:
        raise LookupError("{:s}.by_name({!r}) : Unable to locate function".format(__name__, name))
    return idaapi.get_func(ea)
byName = by_name

@utils.multicase()
def by(): return by_address(ui.current.address())
@utils.multicase(func=idaapi.func_t)
def by(func): return func
@utils.multicase(ea=six.integer_types)
def by(ea): return by_address(ea)
@utils.multicase(name=basestring)
def by(name): return by_name(name)

# FIXME: document this despite it being internal
def __addressOfRtOrSt(func):
    '''Returns (F,address) if a statically linked address, or (T,address) if a runtime-linked address'''
    try:
        fn = by(func)

    # otherwise, maybe it's an rtld symbol
    except LookupError, e:
        if not database.is_data(func): raise

        # ensure that we're an import, otherwise throw original exception
        try: database.imports.get(func)
        except LookupError: raise e

        # yep, we're an import
        return True,func
    return False,fn.startEA

@utils.multicase()
def address():
    '''Return the address of the current function.'''
    fn = ui.current.function()
    if fn is None: raise LookupError("{:s}.address(0x{:s}) : Not currently positioned within a function".format(__name__, ui.current.address()))
    return fn.startEA
@utils.multicase()
def address(func):
    '''Return the address of the function ``func``.'''
    res = by(func)
    return res.startEA

@utils.multicase()
def offset():
    '''Return the offset of the current function from the base of the database.'''
    ea = address()
    return database.getoffset(ea)
@utils.multicase()
def offset(func):
    '''Return the offset of the function ``func`` from the base of the database.'''
    ea = address(func)
    return database.getoffset(ea)

@utils.multicase()
def guess():
    '''Return the boundaries of the function chunk for the current address.'''
    return guess(ui.current.address())
@utils.multicase(ea=six.integer_types)
def guess(ea):
    '''Return the boundaries of the function chunk for the address ``ea``.'''
    ea = interface.address.within(ea)
    for left,right in chunks(ea):
        if left <= ea < right:
            return left,right
        continue
    raise LookupError("{:s}.guess : Unable to determine function chunk's bounds : 0x{:x}".format(__name__, ea))

## properties
@utils.multicase()
def get_comment(**repeatable):
    '''Return the comment for the current function.'''
    return get_comment(ui.current.function(), **repeatable)
@utils.multicase()
def get_comment(func, **repeatable):
    """Return the comment for the function ``func``.
    If the bool ``repeatable`` is specified, then return the repeatable comment.
    """
    fn = by(func)
    return idaapi.get_func_cmt(fn, repeatable.get('repeatable', 1))
@utils.multicase(comment=basestring)
def set_comment(comment, **repeatable):
    '''Set the comment for the current function to ``comment``.'''
    return set_comment(ui.current.function(), comment, **repeatable)
@utils.multicase(comment=basestring)
def set_comment(func, comment, **repeatable):
    """Set the comment for the function ``func`` to ``comment``.
    If the bool ``repeatable`` is specified, then modify the repeatable comment.
    """
    fn = by(func)
    return idaapi.set_func_cmt(fn, comment, repeatable.get('repeatable', 1))

@utils.multicase()
def comment(**repeatable):
    '''Return the comment for the current function.'''
    return get_comment(ui.current.function(), **repeatable)
@utils.multicase()
def comment(func, **repeatable):
    '''Return the comment for the function ``func``.'''
    return get_comment(func, **repeatable)
@utils.multicase(comment=basestring)
def comment(comment, **repeatable):
    '''Set the comment for the current function to ``comment``.'''
    return set_comment(ui.current.function(), comment, **repeatable)
@utils.multicase(comment=basestring)
def comment(func, comment, **repeatable):
    """Set the comment for the function ``func`` to ``comment``.
    If the bool ``repeatable`` is specified, then modify the repeatable comment.
    """
    return set_comment(func, comment, **repeatable)

@utils.multicase()
def get_name():
    '''Return the name of the current function.'''
    return get_name(ui.current.function())
@utils.multicase()
def get_name(func):
    '''Return the name of the function ``func``.'''
    rt,ea = __addressOfRtOrSt(func)
    if rt:
        res = idaapi.get_name(-1, ea)
        return internal.declaration.demangle(res) if internal.declaration.mangled(res) else res
        #return internal.declaration.extract.fullname(internal.declaration.demangle(res)) if internal.declaration.mangled(res) else res
    res = idaapi.get_func_name(ea)
    if not res: res = idaapi.get_name(-1, ea)
    if not res: res = idaapi.get_true_name(ea, ea)
    return res
    #return internal.declaration.extract.fullname(internal.declaration.demangle(res)) if internal.declaration.mangled(res) else res
    #return internal.declaration.extract.name(internal.declaration.demangle(res)) if internal.declaration.mangled(res) else res

@utils.multicase(none=types.NoneType)
def set_name(none):
    '''Remove the custom-name from the current function.'''
    return set_name(ui.current.function(), none or '')
@utils.multicase(name=basestring)
def set_name(name):
    '''Set the name of the current function to ``name``.'''
    # we use ui.current.address() instead of ui.current.function()
    # in case the user might be hovering over an import table
    # function and wanting to rename that instead.
    return set_name(ui.current.address(), name)
@utils.multicase(none=types.NoneType)
def set_name(func, none):
    '''Remove the custom-name from the function ``func``.'''
    return set_name(func, none or '')
@utils.multicase(string=basestring)
def set_name(func, string):
    '''Set the name of the function ``func`` to ``string``.'''
    rt,ea = __addressOfRtOrSt(func)

    res = idaapi.validate_name2(buffer(string)[:])
    if string and string != res:
        logging.warn('{:s}.set_name : Stripping invalid chars from function name {!r} at {:x}. : {!r}'.format(__name__, string, ea, res))
        string = res

    if rt:
        # FIXME: shuffle the new name into the prototype and then re-mangle it
        res, ok = get_name(ea), database.set_name(ea, string)
    else:
        res, ok = get_name(ea), idaapi.set_name(ea, string, idaapi.SN_PUBLIC)
    if not ok:
        raise AssertionError('{:s}.set_name : Unable to set function name for {:x} : {!r}'.format(__name__, ea, string))
    return res

@utils.multicase()
def name():
    '''Return the name of the current function.'''
    return get_name(ui.current.function())
@utils.multicase()
def name(func):
    '''Return the name of the function ``func``.'''
    return get_name(func)
@utils.multicase(none=types.NoneType)
def name(none):
    '''Remove the custom-name from the current function.'''
    return set_name(ui.current.function(), none or '')
@utils.multicase(string=basestring)
def name(string, *suffix):
    '''Set the name of the current function to ``string``.'''
    return name(ui.current.function(), string, *suffix)
@utils.multicase(none=types.NoneType)
def name(func, none):
    '''Remove the custom-name from the function ``func``.'''
    return set_name(func, none or '')
@utils.multicase(string=basestring)
def name(func, string, *suffix):
    '''Set the name of the function ``func`` to ``string``.'''
    res = (string,) + suffix
    res = ('{:x}'.format(_) if isinstance(_, six.integer_types) else _ for _ in res)
    return set_name(func, '_'.join(res))

@utils.multicase()
def prototype():
    '''Return the prototype of the current function if it has one.'''
    return prototype(ui.current.function())
@utils.multicase()
def prototype(func):
    '''Return the prototype of the function ``func`` if it has one.'''
    rt,ea = __addressOfRtOrSt(func)
    funcname = database.name(ea)
    try:
        res = internal.declaration.function(ea)
        idx = res.find('(')
        result = res[:idx] + ' ' + funcname + res[idx:]

    except ValueError:
        if not internal.declaration.mangled(funcname): raise
        result = internal.declaration.demangle(funcname)
    return result

@utils.multicase()
def frame():
    '''Return the frame of the current function.'''
    return frame(ui.current.function())
@utils.multicase()
def frame(func):
    '''Return the frame of the function ``func``.'''
    fn = by(func)
    res = idaapi.get_frame(fn.startEA)
    if res is not None:
        return structure.instance(res.id, offset=-fn.frsize)
    #logging.fatal("{:s}.frame : function does not have a frame : 0x{:x} : {:s}".format(__name__, fn.startEA, name(fn.startEA)))
    logging.info("{:s}.frame : function does not have a frame : 0x{:x} : {:s}".format(__name__, fn.startEA, name(fn.startEA)))
    return structure.instance(-1)

# FIXME: fix the naming
@utils.multicase()
def range():
    '''Return a tuple containing the bounds of the first chunk of the current function.'''
    return range(ui.current.function())
@utils.multicase()
def range(func):
    '''Return a tuple containing the bounds of the first chunk of the function ``func``.'''
    fn = by(func)
    if fn is None:
        raise ValueError("{:s}.range : address 0x{:x} is not contained in a function".format(__name__, ea))
    return fn.startEA,fn.endEA

@utils.multicase(none=types.NoneType)
def set_color(none):
    '''Remove the color from the current function.'''
    return set_color(ui.current.function(), None)
@utils.multicase(rgb=int)
def set_color(rgb):
    '''Set the color of the current function to ``rgb``.'''
    return set_color(ui.current.function(), rgb)
@utils.multicase(none=types.NoneType)
def set_color(func, none):
    '''Remove the color from the function ``func``.'''
    fn = by(func)
    fn.color = 0xffffffff
    return bool(idaapi.update_func(fn))
@utils.multicase(rgb=six.integer_types)
def set_color(func, rgb):
    '''Set the color of the function ``func`` to ``rgb``.'''
    r,b = (rgb&0xff0000)>>16, rgb&0x0000ff
    fn = by(func)
    fn.color = (b<<16)|(rgb&0x00ff00)|r
    return bool(idaapi.update_func(fn))

@utils.multicase()
def get_color():
    '''Return the color of the current function.'''
    return get_color(ui.current.function())
@utils.multicase()
def get_color(func):
    '''Return the color of the function ``func``.'''
    fn = by(func)
    b,r = (fn.color&0xff0000)>>16, fn.color&0x0000ff
    return None if fn.color == 0xffffffff else (r<<16)|(fn.color&0x00ff00)|b

@utils.multicase()
def color():
    '''Return the color of the current function.'''
    return get_color(ui.current.function())
@utils.multicase()
def color(func):
    '''Return the color of the function ``func``.'''
    return get_color(func)
@utils.multicase(none=types.NoneType)
def color(func, none):
    '''Remove the color for the function ``func``.'''
    return set_color(func, None)
@utils.multicase(rgb=six.integer_types)
def color(func, rgb):
    '''Set the color of the function ``func`` to ``rgb``.'''
    return set_color(func, rgb)
@utils.multicase(none=types.NoneType)
def color(none):
    '''Remove the color for the current function.'''
    return set_color(ui.current.function(), None)

@utils.multicase()
def top():
    '''Return the top of the current function.'''
    return top(ui.current.function())
@utils.multicase()
def top(func):
    '''Return the top of the function ``func``.'''
    return address(func)

@utils.multicase()
def bottom():
    '''Return the exit-points of the current function.'''
    return bottom(ui.current.function())
@utils.multicase()
def bottom(func):
    '''Return the exit-points of the function ``func``.'''
    fn = by(func)
    fc = idaapi.FlowChart(f=fn, flags=idaapi.FC_PREDS)
    fc = flow(fn)
    exit_types = (fc_block_type_t.fcb_ret,fc_block_type_t.fcb_cndret,fc_block_type_t.fcb_noret,fc_block_type_t.fcb_enoret,fc_block_type_t.fcb_error)
    return tuple(database.address.prev(n.endEA) for n in fc if n.type in exit_types)

@utils.multicase()
def marks():
    '''Return all the marks in the current function.'''
    return marks(ui.current.function())
@utils.multicase()
def marks(func):
    '''Return all the marks in the function ``func``.'''
    funcea = top(func)
    result = []
    for ea,comment in database.marks():
        try:
            if top(ea) == funcea:
                result.append( (ea,comment) )
        except Exception:
            pass
        continue
    return result

## functions
@utils.multicase()
def add():
    '''Make a function at the current address.'''
    return add(ui.current.address())
@utils.multicase(start=six.integer_types)
def add(start, **end):
    """Make a function at the address ``start``.
    If the address ``end`` is specified, then stop processing the function at it's address.
    """
    start = interface.address.inside(start)
    end = end.getattr('end', idaapi.BADADDR)
    return idaapi.add_func(start, end)
make = utils.alias(add)

@utils.multicase()
def remove():
    '''Remove the definition of the current function from the database.'''
    return remove(ui.current.function())
@utils.multicase()
def remove(func):
    '''Remove the definition of the function ``func`` from the database.'''
    fn = by(func)
    return idaapi.del_func(fn.startEA)

@utils.multicase(start=six.integer_types, end=six.integer_types)
def add_chunk(start, end):
    '''Add the chunk ``start`` to ``end`` to the current function.'''
    return add_chunk(ui.current.function(), start, end)
@utils.multicase(start=six.integer_types, end=six.integer_types)
def add_chunk(func, start, end):
    '''Add the chunk ``start`` to ``end`` to the function ``func``.'''
    fn = by(func)
    start, end = interface.address.inside(start, end)
    return idaapi.append_func_tail(fn, start, end)

@utils.multicase(ea=six.integer_types)
def remove_chunk(ea):
    '''Remove the chunk at ``ea`` it's function.'''
    return remove_chunk(ea, ea)
@utils.multicase(ea=six.integer_types)
def remove_chunk(func, ea):
    '''Remove the chunk at ``ea`` from the function ``func``.'''
    fn, ea = by(func), interface.address.within(ea)
    return idaapi.remove_func_tail(fn, ea)

@utils.multicase(ea=six.integer_types)
def assign_chunk(ea):
    '''Assign the chunk at ``ea`` to the current function.'''
    return assign_chunk(ui.current.function(), ea)
@utils.multicase(ea=six.integer_types)
def assign_chunk(func, ea):
    '''Assign the chunk at ``ea`` to the function ``func``.'''
    fn, ea = by(func), interface.address.within(ea)
    return idaapi.set_tail_owner(fn, ea)

@utils.multicase()
def within():
    '''Return True if the current address is within a function.'''
    return within(ui.current.address())
@utils.multicase(ea=six.integer_types)
def within(ea):
    '''Return True if the address ``ea`` is within a function.'''
    ea = interface.address.within(ea)
    return idaapi.get_func(ea) is not None

## operations
# Checks if ea is contained in function or in any of it's chunks
@utils.multicase()
def contains():
    '''Returns True if the current address is within a function.'''
    return contains(ui.current.function(), ui.current.address())
@utils.multicase(ea=six.integer_types)
def contains(ea):
    '''Returns True if the address ``ea`` is contained by the current function.'''
    return contains(ui.current.function(), ea)
@utils.multicase(ea=six.integer_types)
def contains(func, ea):
    '''Returns True if the address ``ea`` is contained by the function ``func``.'''
    try: fn = by(func)
    except LookupError:
        return False
    ea = interface.address.within(ea)
    return any(start <= ea < end for start,end in chunks(fn))

@utils.multicase()
def arguments():
    '''Returns the arguments for the current function.'''
    return arguments(ui.current.function())
@utils.multicase()
def arguments(func):
    """Yields the arguments for the function ``func`` in order.
    Each result is of the format (offset into stack, name, size).
    """
    try:
        fn = by(func)

    except Exception:
        target = func
        database.imports.get(target)

        # grab from declaration
        o = 0
        for arg in internal.declaration.arguments(target):
            sz = internal.declaration.size(arg)
            yield o,arg,sz
            o += sz
        return

    # grab from structure
    fr = idaapi.get_frame(fn)
    if fr is None:  # unable to figure out arguments
        raise LookupError("{:s}.arguments({!r}) : Unable to determine function frame.".format(__name__, func))
    if database.config.bits() != 32:
        raise RuntimeError("{:s}.arguments({!r}) : Unable to determine arguments for 0x{:x} due to {:d}-bit calling convention.".format(__name__, func, fn.startEA, database.config.bits()))

    base = get_vars_size(fn)+get_regs_size(fn)
    for (off,size),(name,cmt) in structure.fragment(fr.id, base, get_args_size(fn)):
        yield off-base,name,size
    return

@utils.multicase()
def chunk():
    '''Return a tuple containing the bounds of the function chunk at the current address.'''
    return chunk(ui.current.address())
@utils.multicase(ea=six.integer_types)
def chunk(ea):
    '''Return a tuple containing the bounds of the function chunk at the address ``ea``.'''
    fn = by_address(ea)
    for l, r in chunks(fn):
        if l <= ea < r:
            return l, r
        continue
    raise LookupError("{:s}.chunk(0x{:x}) : Unable to locate function chunk for function. : 0x{:x}".format(__name__, ea, address(func)))

@utils.multicase()
def chunks():
    '''Return all the chunks for the current function.'''
    return chunks(ui.current.function())
@utils.multicase()
def chunks(func):
    '''Return all the chunks for the function ``func``.'''
    fn = by(func)
    fci = idaapi.func_tail_iterator_t(fn, fn.startEA)
    if not fci.main():
        raise ValueError("{:s}.chunks({!r}) : Unable to create a func_tail_iterator_t".format(__name__, func))

    while True:
        ch = fci.chunk()
        yield ch.startEA, ch.endEA
        if not fci.next(): break
    return

# FIXME: would probably be better if we just trusted IDA's definition of a 
#        basic-block and used idaapi.FlowChart to return these bounds.

@utils.multicase()
def blocks():
    '''Return each basic-block for the current function.'''
    return blocks(ui.current.function())
@utils.multicase()
def blocks(func):
    '''Returns each basic-block for the function ``func``.'''
    for start,end in chunks(func):
        for r in database.blocks(start, end):
            yield r
        continue
    return

# function frame attributes
@utils.multicase()
def get_frameid():
    '''Returns the structure id for the current function's frame.'''
    return get_frameid(ui.current.function())
@utils.multicase()
def get_frameid(func):
    '''Returns the structure id for the function ``func``.'''
    fn = by(func)
    return fn.frame

@utils.multicase()
def get_args_size():
    '''Returns the size of the arguments for the current function.'''
    return get_args_size(ui.current.function())
@utils.multicase()
def get_args_size(func):
    '''Returns the size of the arguments for the function ``func``.'''
    fn = by(func)
    max = structure.size(get_frameid(fn))
    total = get_vars_size(fn) + get_regs_size(fn)
    return max - total

@utils.multicase()
def get_vars_size():
    '''Returns the size of the local variables for the current function.'''
    return get_vars_size(ui.current.function())
@utils.multicase()
def get_vars_size(func):
    '''Returns the size of the local variables for the function ``func``.'''
    fn = by(func)
    return fn.frsize

@utils.multicase()
def get_regs_size():
    '''Returns the number of bytes occupied by the saved registers in the current function.'''
    return get_regs_size(ui.current.function())
@utils.multicase()
def get_regs_size(func):
    '''Returns the number of bytes occupied by the saved registers for the function ``func``.'''
    fn = by(func)
    return fn.frregs + 4   # +4 for the pc because ida doesn't count it

@utils.multicase()
def get_spdelta():
    '''Returns the stack delta for the current address within it's function.'''
    return get_spdelta(ui.current.address())
@utils.multicase(ea=six.integer_types)
def get_spdelta(ea):
    '''Returns the stack delta for the address ``ea`` within it's given function.'''
    fn, ea = by_address(ea), interface.address.inside(ea)
    return idaapi.get_spd(fn, ea)
delta = get_sp = spdelta = utils.alias(get_spdelta)

## instruction iteration/searching
@utils.multicase()
def iterate():
    '''Iterate through all the instructions for each chunk in the current function.'''
    return iterate(ui.current.function())
@utils.multicase()
def iterate(func):
    '''Iterate through all the instructions for each chunk in the function ``func``.'''
    for start,end in chunks(func):
        for ea in itertools.ifilter(database.type.is_code, database.iterate(start, end)):
            yield ea
        continue
    return

# FIXME
@utils.multicase(match=(types.FunctionType,types.MethodType))
def search_instruction(match):
    '''Search through the current function for any instruction that matches with the callable ``match``.'''
    return search_instruction(ui.current.address(), match)
@utils.multicase(match=(types.FunctionType,types.MethodType))
def search_instruction(func, match):
    """Search through the function ``func`` for any instruction that matches with the callable ``match``.
    ``match`` is a callable that takes one argument which is the result of database.decode(ea).
    """
    for ea in iterate(func):
        if match( database.decode(ea) ):
            yield ea
        continue
    return

@utils.multicase(regex=basestring)
def search(regex):
    '''Return each instruction in the current function that matches the string ``regex``.'''
    return search(ui.current.function(), regex)
@utils.multicase(regex=basestring)
def search(func, regex):
    '''Return each instruction in the function ``func`` that matches the string ``regex``.'''
    pattern = re.compile(regex, re.I)
    for ea in iterate(func):
        insn = re.sub(' +', ' ', database.instruction(ea))
        if pattern.search(insn) is not None:
            yield ea
        continue
    return

# FIXME: rename this to something better or deprecate it
@utils.multicase(delta=six.integer_types)
def stackdelta(delta, **direction):
    '''Return the boundaries of current address that fit within the specified stack ``delta``.'''
    return stackdelta(ui.current.address(), delta, **direction)
@utils.multicase(delta=six.integer_types)
def stackdelta(ea, delta, **direction):
    """Return the boundaries of the address ``ea`` that fit within the specified stack ``delta``.
    If int ``direction`` is provided, search backwards if it's less than 0 or forwards if it's greater.
    """
    direction = direction.get('direction', -1)
    if direction == 0:
        raise AssertionError('you make no sense with your lack of direction')
    next = database.next if direction > 0 else database.prev

    sp, ea = get_spdelta(ea), interface.address.inside(ea)
    start = (ea,sp)
    while abs(sp - start[1]) < delta:
        sp = get_spdelta(ea)
        ea = next(ea)

    if ea < start[0]:
        return ea+idaapi.decode_insn(ea),start[0]+idaapi.decode_insn(start[0])
    return (start[0],ea)
stackwindow = stack_window = utils.alias(stackdelta)

## tagging
@utils.multicase()
def tag_read():
    '''Returns all the tags for the current function.'''
    return tag_read(ui.current.function())
@utils.multicase(key=basestring)
def tag_read(key):
    '''Returns the value for the tag ``key`` for the current function.'''
    return tag_read(ui.current.function(), key)
@utils.multicase()
def tag_read(func):
    '''Returns all the tags defined for the function ``func``.'''
    try:
        rt,ea = __addressOfRtOrSt(func)
    except LookupError:
        logging.warn('{:s}.tag_read : Attempted to read tag from a non-function. Falling back to a database tag. : {:x}'.format(__name__, func))
        return database.tag_read(func)

    if rt:
        logging.warn('{:s}.tag_read : Attempted to read tag from a runtime-linked address. Falling back to a database tag. : {:x}'.format(__name__, ea))
        return database.tag_read(ea)

    fn,repeatable = by_address(ea), True
    res = comment(fn, repeatable=repeatable)
    d1 = internal.comment.decode(res)
    res = comment(fn, repeatable=not repeatable)
    d2 = internal.comment.decode(res)
    if d1.viewkeys() & d2.viewkeys():
        logging.warn('{:s}.tag_read : Contents of both repeatable and non-repeatable comments conflict with one another. Giving the {:s} comment priority.'.format(__name__, 'repeatable' if repeatable else 'non-repeatable', d1 if repeatable else d2))
    res = {}
    map(res.update, (d1,d2))

    # add the function's name to the result
    fname = get_name(fn)
    if fname and (idaapi.getFlags(fn.startEA) & idaapi.FF_NAME): res.setdefault('__name__', fname)

    # ..and now hand it off.
    return res
@utils.multicase(key=basestring)
def tag_read(func, key):
    '''Returns the value for the tag ``key`` for the function ``func``.'''
    res = tag_read(func)
    return res[key]

@utils.multicase(key=basestring)
def tag_write(key, value):
    '''Set the tag ``key`` to ``value`` for the current function.'''
    return tag_write(ui.current.function(), key, value)
@utils.multicase(key=basestring, none=types.NoneType)
def tag_write(key, none):
    '''Removes the tag ``key`` from the current function.'''
    return tag_write(ui.current.function(), key, None)
@utils.multicase(key=basestring)
def tag_write(func, key, value):
    '''Set the tag ``key`` to ``value`` for the function ``func``.'''
    if value is None:
        raise AssertionError('{:s}.tag_write : Tried to set tag {!r} to an invalid value.'.format(__name__, key))

    # Check to see if function tag is being applied to an import
    try:
        rt,ea = __addressOfRtOrSt(func)
    except LookupError:
        # If we're not even in a function, then use a database tag.
        logging.warn('{:s}.tag_write : Attempted to set tag for a non-function. Falling back to a database tag. : {:x}'.format(__name__, func))
        return database.tag_write(func, key, value)

    # If so, then write the tag to the import
    if rt:
        logging.warn('{:s}.tag_write : Attempted to set tag for a runtime-linked symbol. Falling back to a database tag. : {:x}'.format(__name__, ea))
        return database.tag_write(ea, key, value)

    # Otherwise, it's a function.
    fn = by_address(ea)

    # if the user wants to change the '__name__' tag then update the function's name.
    if key == '__name__':
        return set_name(fn, value)

    state = internal.comment.decode(comment(fn, repeatable=1))
    res,state[key] = state.get(key,None),value
    comment(fn, internal.comment.encode(state), repeatable=1)

    if res is None:
        internal.comment.globals.inc(fn.startEA, key)

    return res
@utils.multicase(key=basestring, none=types.NoneType)
def tag_write(func, key, none):
    '''Removes the tag identified by ``key`` from the function ``func``.'''
    #fn = by(func)
    # Check to see if function tag is being applied to an import
    try:
        rt,ea = __addressOfRtOrSt(func)
    except LookupError:
        # If we're not even in a function, then use a database tag.
        logging.warn('{:s}.tag_write : Attempted to clear tag for a non-function. Falling back to a database tag. : {:x}'.format(__name__, func))
        return database.tag_write(func, key, none)

    # If so, then write the tag to the import
    if rt:
        logging.warn('{:s}.tag_write : Attempted to set tag for a runtime-linked symbol. Falling back to a database tag. : {:x}'.format(__name__, ea))
        return database.tag_write(ea, key, none)

    # Otherwise, it's a function.
    fn = by_address(ea)

    # if the user wants to remove the '__name__' tag then remove the name from the function.
    if key == '__name__':
        return set_name(fn, None)
    
    state = internal.comment.decode(comment(fn, repeatable=1))
    res = state.pop(key)
    comment(fn, internal.comment.encode(state), repeatable=1)

    internal.comment.globals.dec(fn.startEA, key)
    return res

#FIXME: define tag_erase

@utils.multicase()
def tag():
    '''Returns all the tags defined for the current function.'''
    return tag_read(ui.current.address())
@utils.multicase(key=basestring)
def tag(key):
    '''Returns the value of the tag identified by ``key`` for the current function.'''
    return tag_read(ui.current.address(), key)
@utils.multicase(key=basestring)
def tag(key, value):
    '''Sets the value for the tag ``key`` to ``value`` for the current function.'''
    return tag_write(ui.current.address(), key, value)
@utils.multicase(key=basestring)
def tag(func, key):
    '''Returns the value of the tag identified by ``key`` for the function ``func``.'''
    return tag_read(func, key)
@utils.multicase()
def tag(func):
    '''Returns all the tags for the function ``func``.'''
    return tag_read(func)
@utils.multicase(key=basestring)
def tag(func, key, value):
    '''Sets the value for the tag ``key`` to ``value`` for the function ``func``.'''
    return tag_write(func, key, value)
@utils.multicase(key=basestring, none=types.NoneType)
def tag(key, none):
    '''Removes the tag identified by ``key`` for the current function.'''
    return tag_write(ui.current.address(), key, None)
@utils.multicase(key=basestring, none=types.NoneType)
def tag(func, key, none):
    '''Removes the tag identified by ``key`` for the function ``func``.'''
    return tag_write(func, key, None)

# FIXME: this could be using the new reference counted tags
@utils.multicase()
def tags():
    '''Returns all the content tags for the current function.'''
    return tags(ui.current.function())
@utils.multicase()
def tags(func):
    '''Returns all the content tags for the function ``func``.'''
    ea = by(func).startEA
    return internal.comment.contents.name(ea)

# FIXME: consolidate this logic into the utils module
# FIXME: document this properly
@utils.multicase(tag=basestring)
def select(**boolean):
    return select(ui.current.function(), **boolean)
@utils.multicase(tag=basestring)
def select(tag, *tags, **boolean):
    tags = (tag,) + tags
    boolean['And'] = tuple(set(boolean.get('And',set())).union(tags))
    return select(ui.current.function(), **boolean)
@utils.multicase(tag=basestring)
def select(func, tag, *tags, **boolean):
    tags = (tag,) + tags
    boolean['And'] = tuple(set(boolean.get('And',set())).union(tags))
    return select(func, **boolean)
@utils.multicase(tag=(__builtin__.set,__builtin__.list))
def select(func, tag, *tags, **boolean):
    tags = set(__builtin__.list(tag) + __builtin__.list(tags))
    boolean['And'] = tuple(set(boolean.get('And',set())).union(tags))
    return select(func, **boolean)
@utils.multicase()
def select(func, **boolean):
    '''Fetch a list of addresses within the function that contain the specified tags.'''
    fn = by(func)
    boolean = dict((k,set(v if isinstance(v, (__builtin__.tuple,__builtin__.set,__builtin__.list)) else (v,))) for k,v in boolean.viewitems())

    if not boolean:
        for ea in internal.comment.contents.address(fn.startEA):
            res = database.tag(ea)
            if res: yield ea, res
        return

    for ea in internal.comment.contents.address(fn.startEA):
        res,d = {},database.tag(ea)

        Or = boolean.get('Or', set())
        res.update((k,v) for k,v in d.iteritems() if k in Or)

        And = boolean.get('And', set())
        if And:
            if And.intersection(d.viewkeys()) == And:
                res.update((k,v) for k,v in d.iteritems() if k in And)
            else: continue
        if res: yield ea,res
    return

## referencing
@utils.multicase()
def down():
    '''Return all the functions that are called by the current function.'''
    return down(ui.current.function())
@utils.multicase()
def down(func):
    '''Return all the functions that are called by the function ``func``.'''
    def codeRefs(func):
        resultData,resultCode = [],[]
        for ea in iterate(func):
            if len(database.down(ea)) == 0:
                insn = idaapi.ua_mnem(ea)
                if insn and insn.startswith('call'):
                    resultCode.append((ea, 0))
                continue
            resultData.extend( (ea,x) for x in database.dxdown(ea) )
            resultCode.extend( (ea,x) for x in database.cxdown(ea) if func.startEA == x or not contains(func,x) )
        return resultData,resultCode
    fn = by(func)
    return sorted(set(d for x,d in codeRefs(fn)[1]))

@utils.multicase()
def up():
    '''Return all the functions that call the current function.'''
    return up(ui.current.address())
@utils.multicase()
def up(func):
    '''Return all the functions that call the function ``func``.'''
    rt, ea = __addressOfRtOrSt(func)
    # runtime
    if rt:
        return database.up(ea)
    # regular
    return database.up(ea)

## switch stuff
# FIXME: document this
class switch_t(object):
    #x.defjump -- default case
    #x.jcases,x.jumps -- number of branches,address of branch data
    #x.ncases,x.lowcase -- number of cases,address of switch data
    #x.startea -- beginning of basicblock that is switch
    # get_jtable_element_size -- table entry size
    # need some way to get pointer size
    def __init__(self, switch_info_ex):
        self.object = switch_info_ex
    @property
    def default(self):
        # address of default case
        return self.object.defjump
    @property
    def ea(self):
        # address of beginning of switch code
        return self.object.startea
    @property
    def branch_ea(self):
        # address of branch table
        return self.object.jumps
    @property
    def table_ea(self):
        # address of case table
        return self.object.lowcase
    @property
    def branch(self):
        # return the branch table as an array
        pass
    @property
    def table(self):
        # return the index table as an array
        pass
    def get_case(self, case):
        # return the ea of the specified case number
        raise NotImplementedError

@utils.multicase()
def switches(): return switches(ui.current.function())
@utils.multicase()
def switches(func):
    for ea in iterate(func):
        res = idaapi.get_switch_info_ex(ea)
        if res: yield switch_t(res)
    return

## flags
@utils.multicase()
def has_noframe():
    '''Return True if the current function has no frame.'''
    return has_noframe(ui.current.function())
@utils.multicase()
def has_noframe(func):
    '''Return True if the function ``func`` has no frame.'''
    fn = by(func)
    return not is_thunk(fn) and (fn.flags & idaapi.FUNC_FRAME == 0)

@utils.multicase()
def has_noreturn():
    '''Return True if the current function does not return.'''
    return has_noreturn(ui.current.function())
@utils.multicase()
def has_noreturn(func):
    '''Return True if the function ``func`` does not return.'''
    fn = by(func)
    return not is_thunk(fn) and (fn.flags & idaapi.FUNC_NORET == idaapi.FUNC_NORET)

@utils.multicase()
def is_library():
    '''Return True if the current function is considered a library function.'''
    return is_library(ui.current.function())
@utils.multicase()
def is_library(func):
    '''Return True if the function ``func`` is considered a library function.'''
    fn = by(func)
    return fn.flags & idaapi.FUNC_LIB == idaapi.FUNC_LIB

@utils.multicase()
def is_thunk():
    '''Return True if the current function is considered a code thunk.'''
    return is_thunk(ui.current.function())
@utils.multicase()
def is_thunk(func):
    '''Return True if the function ``func`` is considered a code thunk.'''
    fn = by(func)
    return fn.flags & idaapi.FUNC_THUNK == idaapi.FUNC_THUNK

@utils.multicase(reg=basestring)
def register(reg, *regs, **modifiers):
    """Yield all the addresses within the current function that touches one of the registers identified by ``regs``.
    """
    return register(ui.current.function(), reg, *regs, **modifiers)

@utils.multicase(reg=basestring)
def register(func, reg, *regs, **modifiers):
    """Yield all the addresses within the function ``func`` that touches one of the registers identified by ``regs``.
    If the keyword ``write`` is True, then only return the address if it's writing to the register.
    """
    regs = (reg,) + regs
    write = (not modifiers.get('read',None)) if 'read' in modifiers else modifiers.get('write',None)
    def uses_register(ea, regs):
        res = [(_instruction.op_type(ea,x),_instruction.op_value(ea,x),_instruction.op_state(ea,x)) for x in xrange(_instruction.ops_count(ea)) if _instruction.op_type(ea,x) in ('opt_reg','opt_phrase')]
        match = lambda r,regs: itertools.imap(_instruction.reg.by_name(r).related,itertools.imap(_instruction.reg.by_name,regs))
        for t,p,st in res:
            if t == 'opt_reg' and any(match(p,regs)) and (('w' in st) if write else ('r' in st) if (write is not None and not write) else True):
                return True
            if t == 'opt_phrase' and (('w' in st) if write else ('r' in st) if (write is not None and not write) else True):
                _,(base,index,_) = p
                if (base and any(match(base,regs))) or (index and any(match(index,regs))):
                    return True
            continue
        return False

    for ea in iterate(func):
        if uses_register(ea, regs):
            yield ea
        continue
    return

## internal enumerations that idapython missed
class fc_block_type_t:
    fcb_normal = 0  # normal block
    fcb_indjump = 1 # block ends with indirect jump
    fcb_ret = 2     # return block
    fcb_cndret = 3  # conditional return block
    fcb_noret = 4   # noreturn block
    fcb_enoret = 5  # external noreturn block (does not belong to the function)
    fcb_extern = 6  # external normal block
    fcb_error = 7   # block passes execution past the function end

@utils.multicase()
def flow():
    '''Return a flow chart object for the current function.'''
    return flow(ui.current.function())
@utils.multicase()
def flow(func):
    '''Return a flow chart object for the function ``func``.'''
    fn = by(func)
    fc = idaapi.FlowChart(f=fn, flags=idaapi.FC_PREDS)
    return fc
