from snakemake.io import expand 
from snakemake.utils import format
from snakemake.workflow import config

import re, os
import textwrap
from subprocess import check_output

def get_ncbi_root():
    root = check_output("""
    module load sratoolkit
    vdb-config /repository/user/main/public/root/
    """, shell=True)
#    root = re.sub("</?root>", "", root).trim()
    return root


def read_propfiles(files):
    if isinstance(files, str):
        files=[files]
    props = {}
    for file in files:
        with open(file, "r") as f:
            props.update(
                {key: int(float(value))
                     for line in f
                     for key, value in [line.strip().split(maxsplit=1)]}
            )
    return props


def glob_wildcards(pattern, files=None):
    from itertools import chain
    from snakemake.io import _wildcard_regex, namedtuple, regex
    import regex as re
    
    """
    Glob the values of the wildcards by matching the given pattern to the filesystem.
    Returns a named tuple with a list of values for each wildcard.
    """
    pattern = os.path.normpath(pattern)
    first_wildcard = re.search("{[^{]", pattern)
    dirname = os.path.dirname(pattern[:first_wildcard.start(
    )]) if first_wildcard else os.path.dirname(pattern)
    if not dirname:
        dirname = "."

    names = [match.group('name')
             for match in _wildcard_regex.finditer(pattern)]
    Wildcards = namedtuple("Wildcards", names)
    wildcards = Wildcards(*[list() for name in names])

    pattern = regex(pattern)
    # work around partial matching bug in python regex module
    # by replacing matches for "\" with "[/\0]" (0x0 can't occur in filenames)
    pattern = re.sub('\\\\/','[/\0]', pattern)
    pattern = re.compile(pattern)

    def walker():
        for dirpath, dirnames, filenames in os.walk(dirname):
            for f in filenames:
                if dirpath != ".":
                    f=os.path.join(dirpath, f)
                yield f
            for i in range(len(dirnames)-1, -1, -1):
                d = dirnames[i]
                if dirpath != ".":
                    d=os.path.join(dirpath, d)
                if not pattern.match(os.path.join(d,""), partial=True):
                    del dirnames[i]
                else:
                    yield d
    
    if files is None:
        files = walker()

    for f in files:
        match = re.match(pattern, os.path.normpath(f))
        if match:
            for name, value in match.groupdict().items():
                getattr(wildcards, name).append(value)
    return wildcards


from rpy2.robjects import default_converter, conversion, sequence_to_vector
from rpy2.robjects import conversion
from rpy2 import robjects, rinterface


@default_converter.py2ri.register(dict)
def _(obj):
    keys = list(obj.keys())
    res = rinterface.ListSexpVector([conversion.py2ri(obj[x]) for x in keys])
    res.do_slot_assign('names',rinterface.StrSexpVector(keys))
    return res

@default_converter.py2ri.register(tuple)
def _(obj):
    return conversion.py2ri(list(obj))

@default_converter.py2ri.register(list)
def _(obj):
    #return sequence_to_vector(obj)
    obj = rinterface.ListSexpVector([conversion.py2ri(x) for x in obj])
    return robjects.r.unlist(obj, recursive=False)


from snakemake.io import Namedlist
def R(code="", **kwargs):
    """Execute R code

    This function executes the R code given as a string. Additional arguments are injected into
    the R environment. The value of the last R statement is returned. 

    The function requires rpy2 to be installed.

    .. code:: python
        R(input=input)

    Args:
        code (str): R code to be executed
        **kwargs (dict): variables to inject into R globalenv
    Yields:
        value of last R statement
        
    """
    try:
        import rpy2.robjects as robjects
        from rpy2.rlike.container import TaggedList
        from rpy2.rinterface import RNULLType
    except ImportError:
        raise ValueError(
            "Python 3 package rpy2 needs to be installed to use the R function.")
    
    # translate Namedlists into rpy2's TaggedList to have named lists in R
    for key in kwargs:
        value = kwargs[key]
        if isinstance(value, Namedlist):
            kwargs[key] = TaggedList([y for x,y in value.allitems()],
                                     [x for x,y in value.allitems()])

    code = format(textwrap.dedent(code), stepout=2)
    # wrap code in function to preserve clean global env and execute
    rval = robjects.r("function({}){{ {} }}".format(",".join(kwargs), code))(**kwargs)

    # Reduce vectors of length 1 to scalar, as implicit in R.
    if isinstance(rval, RNULLType):
        
        rval = None
    if rval and len(rval) == 1:
        return rval[0]
    return rval
            
