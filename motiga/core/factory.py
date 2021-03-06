'''
A collection of helper functions to construct pymel node factories (i.e. custom pynodes).

The main appeal is providing direct access (via *Access) instead of get/set, so it only
makes sense if the attribute isn't animatable.

Additionally there is a helper that allows connecting a single object and another
for automatically deserializing json strings.

ex:

    class MySpecialJoint(nt.Joint):
        
        @classmethod
        def _isVirtual(cls, obj, name):
            fn = pymel.api.MFnDependencyNode(obj)
            try:
                if fn.hasAttribute('motigaMirror'):
                    return True
            except:  # .hasAttribute doesn't actually return False but errors, lame.
                pass
            return False

        mirror  = SingleConnectionAccess('motigaMirror')
        data    = JsonAccess('motigaData')
        
    pymel.internal.factories.registerVirtualClass( MySpecialJoint )
    
    j = joint()
    j.addAttr('motigaMirror', at='message')
    j.addAttr('motigaData', dt='string')
    j = PyNode(j)  # Must recast to get identified as a MySpecialJoint
    
    someOtherJoint = joint()
    print j.mirror
    # Result: None
    
    j.mirror = someOtherJoint
    print j.mirror
    # Result: joint2
    
    j.mirror = None
    print j.mirror
    # Result: None
    
    print j.data
    # Result: {}
    
    j.data = {'canned': 'goods' }
    print j.data, type(j.data)
    # Result: {'canned': 'goods' } <type 'dict'>
    
    print j.motigaData.get(), type(j.motigaData.get())
    # Result: {"canned": "goods"} <type 'unicode'>

'''

import collections
import json

from pymel.core import hasAttr
from pymel.core.general import PyNode

# Attribute access utilities --------------------------------------------------
# They all have to use .node() in case it's a sub attr, like sequence[0].data


def _getSingleConnection(obj, attrName):
    '''
    If connected, return the single entry, otherwise none.
    '''
    if not obj.node().hasAttr(attrName):
        return None
    
    connections = obj.attr(attrName).listConnections()
    if connections:
        return connections[0]
    else:
        return None


def _setSingleConnection(obj, attrName, value):
    if value:
        if isinstance(value, basestring):
            PyNode(value).message >> messageAttr( obj, attrName )
        else:
            value.message >> messageAttr( obj, attrName )
    else:
        if hasAttr(obj.node(), attrName):
            obj.attr(attrName).disconnect()


def _getSingleStringConnection(obj, attrName):
    '''
    If connected, return the single entry, otherwise checks if a string val is set, returning that.
    '''
    if not obj.node().hasAttr(attrName):
        return ''
    
    connections = obj.attr(attrName).listConnections()
    if connections:
        return connections[0]
    else:
        return obj.attr(attrName).get()


def _setSingleStringConnection(obj, attrName, value):
    if value:
        if isinstance(value, basestring):
            if obj.node().hasAttr(attrName) and obj.attr(attrName).listConnections():
                obj.attr(attrName).disconnect()
                
            _setStringAttr(obj, attrName, value)
        else:
            _setStringAttr(obj, attrName, None)
            value.message >> obj.attr( attrName )
    else:
        if hasAttr(obj.node(), attrName):
            obj.attr(attrName).disconnect()
            obj.attr(attrName).set('')


def _getStringAttr(obj, attrName):
    if obj.node().hasAttr(attrName):
        return obj.attr(attrName).get()
    return ''


def _setStringAttr(obj, attrName, val):
    if not obj.node().hasAttr(attrName):
        obj.addAttr( attrName, dt='string' )
    if val is not None:
        obj.attr(attrName).set(val)
    
    
def _getIntAttr(obj, attrName):
    if obj.node().hasAttr(attrName):
        return obj.attr(attrName).get()
    return -666


def _setIntAttr(obj, attrName, val):
    if not obj.node().hasAttr(attrName):
        obj.addAttr( attrName, dt='long' )
    if val is not None:
        obj.attr(attrName).set(val)
    
    
def _getFloatAttr(obj, attrName):
    if obj.node().hasAttr(attrName):
        return obj.attr(attrName).get()
    return -666.666


def _setFloatAttr(obj, attrName, val):
    if not obj.node().hasAttr(attrName):
        obj.addAttr( attrName, dt='double' )
    if val is not None:
        obj.attr(attrName).set(val)
    
    
def messageAttr( obj, name ):
    '''
    Make the attribute if it doesn't exist and return it.
    '''
    
    if not obj.hasAttr( name ):
        obj.addAttr( name, at='message' )
    return obj.attr(name)


class FakeAttribute(object):
    
    def __init__(self, obj, getter, setter):
        self.obj = obj
        self.getter = getter
        self.setter = setter
    
    def get(self):
        return self.getter(self.obj)
        
    def set(self, val):
        self.setter(self.obj, val)


# Descriptors -----------------------------------------------------------------
class DeprecatedAttr(object):
    '''
    When a regular attribute has been replaced by something, allow for not
    fixing every code reference but route to the new data location.
    '''
    
    def __init__(self, getter, setter, mayaAttr=True):
        self.getter = getter
        self.setter = setter
        self.mayaAttr = mayaAttr
    
    def __get__(self, instance, owner):
        if self.mayaAttr:
            return FakeAttribute(instance, self.getter, self.setter)
        else:
            return self.getter(instance)

    def __set__(self, instance, value):
        # This is never legitimately called for maya attrs
        if not self.mayaAttr:
            self.setter(instance, value)


class StringAccess(object):
    '''
    Provides access to the attribute of the given name, defaulting to an
    empty string if the attribute doesn't exist.
    '''
    def __init__(self, attrname):
        self.attr = attrname
    
    def __get__(self, instance, owner):
        return _getStringAttr(instance, self.attr)
    
    def __set__(self, instance, value):
        _setStringAttr(instance, self.attr, value)
        

class SingleConnectionAccess(object):
    '''
    Returns the object connected to the given attribute, or None if the attr
    doesn't exist or isn't connected.
    '''
    def __init__(self, attrname):
        self.attr = attrname
    
    def __get__(self, instance, owner):
        return _getSingleConnection(instance, self.attr)

    def __set__(self, instance, value):
        _setSingleConnection(instance, self.attr, value)
            
            
class SingleStringConnectionAccess(object):
    '''
    Just like SingleConnection but is also a string for alternate values
    '''
    def __init__(self, attrname):
        self.attr = attrname
    
    def __get__(self, instance, owner):
        return _getSingleStringConnection(instance, self.attr)

    def __set__(self, instance, value):
        _setSingleStringConnection(instance, self.attr, value)

       
class JsonAccess(object):
    '''
    Auto tranform json data to/from a string.  Provides an actual dictionary so
    you have to reassign the entire dict back if you want to make edits.  It
    might be more streamlined to use `JsonAccessDirect` instead.
    '''
    def __init__(self, attrname):
        self.attr = attrname
    
    def __get__(self, instance, owner):
        res = _getStringAttr(instance, self.attr)
        if not res:
            return {}
        return json.loads(res, object_pairs_hook=collections.OrderedDict)
            
    def __set__(self, instance, value):
        v = json.dumps(value)
        _setStringAttr(instance, self.attr, v)


class ProxyDict(object):
    def __init__(self, d, inst, attr):
        self.d = d
        self.inst = inst
        self.attr = attr

    def __getattr__(self, a):
        return self.d[a]
    
    def __setattr__(self, a, v):
        self.d[a] = v
        _setStringAttr(self.inst, self.attr, json.dumps(self.d) )
    

class JsonAccessDirect(object):
    '''
    Auto tranform json data to/from a string.  Returns a `ProxyDict`, which
    manages updating values when the first level of keys is updated.
    '''
    def __init__(self, attrname, defaults):
        self.attr = attrname
        self.defaults = defaults
    
    def __get__(self, instance, owner):
        res = _getStringAttr(instance, self.attr)
        d = self.defaults.copy()
        if res:
            d.update(json.loads(res, object_pairs_hook=collections.OrderedDict))
            
        return ProxyDict(d, instance, self.attr)
            
    def __set__(self, instance, value):
        v = json.dumps(value)
        _setStringAttr(instance, self.attr, v)


class IntAccess(object):
    '''
    Provides access to the attribute of the given name, defaulting to an
    empty string if the attribute doesn't exist.
    '''
    def __init__(self, attrname):
        self.attr = attrname
    
    def __get__(self, instance, owner):
        return _getIntAttr(instance, self.attr)
    
    def __set__(self, instance, value):
        _setIntAttr(instance, self.attr, value)
        
        
class FloatAccess(object):
    '''
    Provides access to the attribute of the given name, defaulting to an
    empty string if the attribute doesn't exist.
    '''
    def __init__(self, attrname):
        self.attr = attrname
    
    def __get__(self, instance, owner):
        return _getFloatAttr(instance, self.attr)
    
    def __set__(self, instance, value):
        _setFloatAttr(instance, self.attr, value)