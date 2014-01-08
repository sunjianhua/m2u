"""
the main module to do operations with UnrealText.

The main task here is to convert a copied UnrealText into representations
for all of the contained objects and the reverse, creating UnrealText from
those objects. For the other way around, see :mod:`udkComposer`


The average UrealText is constructed in the following manner::

    Begin Map
        Begin Level
            Begin Actor
                ...
                Begin Object
                    ...
                End Object
                ...
                Location =
                ...
            End Actor
        End Level
    End Map

there may be multiple Actors in each Level and each Actor may have multiple
sub Object components.

The part we are most interested in are the Actors. We have one function to
strip away the Map and Level parts and send every Actor block to a function
which will create an ObjectInfo of that Actor. All the returned Infos will
create a list of Actors of that Level and be returned.


Why do we parse into ObjectInfos only to translate back into text when sending
stuff back to UDK, wouldn't it be faster if we simply did in-text replacement?
It might be faster in some instances where only short snippets in the text are
replaced. But i guess if you would for example extract the static-mesh
signature from an actor, the underlying regexp would have to search through
the whole string anyway. Why only get one information if you could get all
the information without much of an overhead?

But the main argument is, that it makes the implementation independent
from the used program and editor combination, we have only one place to look at
if something for the parsing process changes. And it is much easier to work with
objects in all the other functions than to fiddle with text-parsing everywhere.

.. note: Information that is present in the header (the line containing
`Begin...`), speaking `Name`, `Class`, `Archetype` takes always precedence over
the same attribute's assignment in the body.
For Object Components, the `ObjName` specified in the header will be the name
of the object, not the `Name` in header or body.

(I think we generally do not need to fiddle with renaming object components,
because the name is only unique inside the parent objects namespace.
If we do, we need to make sure that the correct name is assigned to stuff
like `CollisionComponent` of the Actor too.)

"""

import re

from m2u.helper.ObjectInfo import ObjectInfo
from m2u.udk.udkTypes import getCommonTypeFromInternal

from m2u import logger as _logger
_lg = _logger.getLogger(__name__)

def parseActors(unrtext):
    """ parse UnrealText and return a list of ObjectInfos of the Actors in
    the Level.

    :param unrtext: the unreal text for the level
    :return: list of :class:`m2u.helper.ObjectInfo.ObjectInfo`

    Use this function to convert a complete level or multi-selection. 
    """
    objList = list()

    sindex = 0
    while True:
        sindex = unrtext.find("Begin Actor", sindex)
        if sindex == -1:
            break
        eindex = unrtext.find("End Actor", sindex) 
        actorText = unrtext[sindex:eindex]
        obj = parseActor(actorText, True)
        objList.append(obj)
    return objList
    

def parseActor(unrtext, safe=False):
    """ parse UnrealText of a single Actor into an ObjectInfo representation.

    :param unrtext: the unreal text for the level
    :param safe: the first line in unrtext is the Begin Actor line
    and the End Actor line is not present
    
    :return: instance of :class:`m2u.helper.ObjectInfo.ObjectInfo`

    .. note: if you provide text with more than one Actor in it, only the first
    Actor will be converted.
    If you have a multi-selection, use :func:`parseActors`
    
    """
    # to keep it simple we currently only get the entries we are interested
    # in and pile everything else up to a text, so we do no sub-object parsing
    # this may change in the future!
    
    sindex = 0
    # split every line and erase leading whitespaces, removes empty lines
    lines = re.split("\n+\s*", unrtext)
    # find the first line that begins the Actor (most likely the first line)
    if not safe: # no preprocessing was done, most likely the third line then
        for i in range(len(lines)):
            if lines[i].startswith("Begin Actor"):
                sindex = i
                break
    g = re.search("Class=(.+?) Name=(.+?)\s+", lines[sindex])
    if not g: # no name? invalid text, obviously
        _lg.error( "no name and type found for object")
        return None
    objtype = g.group(1)
    objname = g.group(2)
    objtypecommon = getCommonTypeFromInternal(objtype)
    objInfo = ObjectInfo(objname, objtype, objtypecommon)
    textblock = ""
    for line in lines[sindex+1:]:
        # add jumping over sub-object groups (skip lines inbetween or so)
        # if line startswith "Begin Object"
        # dumb copy lines until
        # line startswith "End Object" is found
        # keep track of depth (begin obj,begin obj, end obj ->)
        if not safe and line.startswith("End Actor"):
            break # done reading actor
        elif line.startswith("Location="):
            objInfo.position = _getFloatTuple(line)
        elif line.startswith("Rotation="):
            rot = _getFloatTuple(line)
            objInfo.rotation = _convertRotationFromUDK(rot)
        elif line.startswith("DrawScale3D="):
            objInfo.scale = _getFloatTuple(line)
        else:
            textblock += ("\n"+line)
    objInfo.attrs["textblock"]=textblock
    return objInfo


float3Match = re.compile("=\(.+?=(.+?),.+?=(.+?),.+?=(.+?)\)")
def _getFloatTuple(text):
    """ get the float tuples from location, rotation etc. in unrtext """
    g = float3Match.search(text)
    a = [0.0, 0.0, 0.0] 
    for i in range(3):
        try:
            a[i] = float(g.group(i+1))
        except ValueError:
            pass
            # TODO: maybe do some information stuff here
    return (a[0],a[1],a[2])



def _convertRotationFromUDK(rotTuple):
    """ converts udk's 65536 for a full rotation format into 360deg format """
    # 0.0054931640625 is 360.0/65536
    newrot=((rotTuple[0]*0.0054931640625),
            (rotTuple[1]*0.0054931640625),
            (rotTuple[2]*0.0054931640625))
    return newrot