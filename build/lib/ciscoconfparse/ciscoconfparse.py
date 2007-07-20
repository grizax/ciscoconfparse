#!/usr/bin/env python

import sys
import re
import os

### CiscoConfParse.py
### Version 0.41

class CiscoConfigParse(object):
   """Parses Cisco IOS configurations and answers queries about the configs"""
   
   def __init__(self, config):
      """Initialize the class, read the config, and spawn the parser"""
      self.config = config
      if type(self.config) == type([ 'a', 'b' ]):
         # we already have a list object, simply call the parser
         iosconfig = self.config
         self.parse(iosconfig)
      elif type(self.config) == type("ab"):
         try:
            # string - assume a filename... open file, split and parse
            f = open(self.config)
            text = f.read()
            rgx = re.compile("\r*\n+")
            iosconfig = rgx.split(text)
         except IOError:
            # string - perhaps an IOS config... split and parse
            text = self.config
            rgx = re.compile("\r*\n+")
            iosconfig = rgx.split(text)
         self.parse(iosconfig)
      else:
         print "FATAL: CiscoConfigParse() received an invalid argument\n"
         sys.exit(0)

   def parse(self, iosconfig):
      """Iterate over the configuration and generate a linked list of IOS commands."""
      self.iosconfig = iosconfig
      # Dictionary mapping line number to objects
      self.lineObjDict = {}
      # List of all parent objects
      self.allparentobjs = []
      ## Generate a (local) indentation list
      indentation = []
      for ii in range(len(self.iosconfig)):
         # indentation[ii] is the number of leading spaces in the line
         indentation.append( len(self.iosconfig[ii]) - len( self.iosconfig[ii].lstrip() ) )
         # Build an IOSConfigLine object for each line, associate with a config dictionary
         lineobject = IOSConfigLine(ii)
         lineobject.add_text = self.iosconfig[ii]
         self.lineObjDict[ii] = lineobject
      ## Walk through the config and look for the "first" child
      for ii in range(len(self.iosconfig)):
         # skip any IOS config comments
         if ( not re.search("^\s*!", self.iosconfig[ii] ) ):
            current_indent = indentation[ii]
            # Determine if this is the "first" child...
            #   Note: other children will be orphaned until we walk the config again.
            if ( ( ii + 1 ) < len( self.iosconfig ) ):
               if ( indentation[ii + 1] > current_indent ):
                  if( not re.search("!", self.iosconfig[ii + 1] ) ):
                     # Add child to the parent's object
                     lineobject = self.lineObjDict[ii]
                     lineobject.add_child( self.lineObjDict[ii + 1], indentation[ii + 1] )
                     if current_indent == 0:
                        lineobject.assert_oldest_ancestor
                     self.allparentobjs.append(lineobject)
                     # Add parent to the child's object
                     lineobject = self.lineObjDict[ii + 1]
                     lineobject.add_parent( self.lineObjDict[ii] )
      ## Look for orphaned children, these SHOULD be indented the same
      ##  number of spaces as the "first" child.  However, we must only
      ##  look inside our "extended family"
      self.mark_family_endpoints( self.allparentobjs, indentation )
      for lineobject in self.allparentobjs:
         if indentation[lineobject.linenum] == 0:
            self.find_unknown_children( lineobject, self.lineObjDict, indentation )
            ## this SHOULD find all children in the family...
            candidate_children = lineobject.children
            for child in candidate_children:
               if self.find_unknown_children( child, self.lineObjDict, indentation ):
                  # Appending any new children to candidate_children as
                  #  we find new children
                  for new in child.children:
                     candidate_children.append(new)
      ## Make adjustments to the IOS banners because these currently show up as
      ##  individual lines, instead of a parent / child relationship.  This
      ##  means finding each banner statement, and associating the  subsequent
      ##  lines as children.
      self.find_banner( "login", indentation )
      self.find_banner( "motd", indentation )
      self.find_banner( "exec", indentation )
      self.find_banner( "incoming", indentation )

   def find_banner( self, banner_str, indentation ):
      """Identify all multiline entries matching the mlinespec (this is
      typically used for banners).  Associate parent / child relationships, as
      well setting the oldest_ancestor."""
      ## mlinespec must be in the form:
      ##  ^banner\slogin\.+?(\^\S*)
      ##   Note: the text in parenthesis will be used as the multiline-end delimiter
      start_banner = False
      end_banner = False
      ii = 0
      while ( start_banner == False ) & ( ii < len(self.iosconfig) ):
         if re.search("banner\s+"+banner_str+"\s+\^\S+", self.iosconfig[ii] ):
            # Found the start banner at ii
            start_banner = True
            kk = ii + 1
         else:
            ii += 1
      if ( start_banner == True ):
         while ( end_banner == False ) & ( kk < len(self.iosconfig) ) :
            if re.search( "^\s*!", self.iosconfig[kk] ):
               # Note: We are depending on a "!" after the banner... why can't
               #       a normal regex work with IOS banners!?
               #       Therefore the endpoint is at ( kk - 1)
               # print "found endpoint: line %s, text %s" % (kk - 1, self.iosconfig[kk - 1])
               
               # Set oldest_ancestor on the parent
               self.lineObjDict[ii].assert_oldest_ancestor()
               for mm in range( ii + 1, ( kk ) ):
                  # Associate parent with the child  
                  self.lineObjDict[ii].add_child( self.lineObjDict[mm], indentation[ii] )
                  # Associate child with the parent
                  self.lineObjDict[mm].add_parent( self.lineObjDict[ii] )
               end_banner = True
            else:
               kk += 1
      # Return our success or failure status
      return end_banner

   def find_multiline_entries( self, re_code, indentation ):
      """Identify all multiline entries matching the mlinespec (this is
      typically used for banners).  Associate parent / child relationships, as
      well setting the oldest_ancestor."""
      ##
      ## Note: I wanted this to work for banners, but have never figured out
      ##       how to make the re_compile code set re_code.group(1).
      ##       Right now, I'm using find_banner()
      ##
      ## re_code should be a lambda function such as:
      ##  re.compile("^banner\slogin\.+?(\^\S*)"
      ##  The text in parenthesis will be used as the multiline-end delimiter
      for ii in range(len(self.iosconfig)):
         ## submitted code will pass a compiled regular expression
         if re_code.search( self.iosconfig[ii] ):
            end_string = re_code.group(1)
            print "Got end_string = %s" % end_string
            for kk in range( (ii + 1), len(self.iosconfig) ):
               if re.search( end_string, iosconfig[kk] ) == True:
                  print "found endpoint: %s" % iosconfig[kk]
                  # Set the parent attributes
                  self.lineObjDict[ii].assert_oldest_ancestor()
                  for mm in range( ii + 1, ( kk + 1 ) ):
                     # Associate parent with the child
                     self.lineObjDict[ii].add_child( self.lineObjDict[mm], indentation[ii] )
                     # Associate child with the parent
                     self.lineObjDict[mm].add_parent( self.lineObjDict[ii] )


   def find_unknown_children( self, lineobject, lineObjDict, indentation ):
      """Walk through the configuration and look for configuration child lines
      that have not already been identified"""
      found_unknown_child = False
      for ii in range( lineobject.linenum, self.find_family_endpoint(lineobject, len(self.iosconfig) ) ):
         child_indent = lineobject.child_indent
         if not re.search( "^\s*!", self.iosconfig[ii] ):
            if indentation[ii] == child_indent:
               # we have found a potential orphan... also could be the first child
               self.lineObjDict[ii].add_parent( lineobject )
               found_unknown_child = lineobject.add_child( self.lineObjDict[ii], indentation[ii] )
               #if found_unknown_child == True:
               #   print "Parent: %s" % self.iosconfig[lineobject.linenum]
               #   print "Found child: %s" % self.iosconfig[ii]
      return found_unknown_child

   def find_family_endpoint(self, lineobject, last_config_line ):
      """This method can start with any child object, and traces through its parents to the oldest_ancestor.
      When it finds the oldest_ancestor, it looks for the family_endpoint attribute."""
      ii = 0
      source_linenum = lineobject.linenum
      while ( ii < last_config_line ) & ( lineobject.oldest_ancestor == False ):
         # Find the parent, try again...
         lineobject = lineobject.parent
         ii += 1
      if ii == last_config_line:
         # You have now searched to the end of the configuration and did not find a valid family endpoint.
         #  This is bad, there is something wrong with IOSConfigLine relationships if you get this message.
         print "FATAL: Could not resolve family endpoint while starting from configuration line number %s" % source_linenum
         sys.exit(0)
      if lineobject.family_endpoint > 0:
         return lineobject.family_endpoint
      else:
         print "FATAL: While considering: '%s'" % self.iosconfig[lineobject.linenum]
         print "       Found invalid family endpoint.  Validate IOSConfigLine relationships"
         sys.exit(0)
   
   def mark_family_endpoints(self, parents, indentation):
      """Find the endpoint of the config 'family'
      A family starts when a config line with *no* indentation spawns 'children'
      A family ends when there are no more children.  See class IOSConfigLine for an example
      This method modifies attributes inside the IOSConfigLine class"""
      for parent in parents:
         ii = parent.linenum
         current_indent = indentation[ii]
         if current_indent == 0:
            # we are at the oldest ancestor
            parent.assert_oldest_ancestor()
            # start searching for the family endpoint
            ii += 1
            # reject endpoints in IOS comments
            if not re.search("^\s*!", self.iosconfig[ii]):
               found_endpoint = False
               while found_endpoint == False:
                  if indentation[ii] == 0:
                     found_endpoint = True
                     parent.set_family_endpoint( ii )
                  else:
                     ii += 1

   def find_lines( self, linespec ):
      """This method is the equivalent of a simple configuration grep
      (Case-sensitive)."""
      retval = []
      for line in self.iosconfig:
         if re.search( linespec, line ):
            retval.append(line)
      if len(retval) > 0:
         return retval
      else:
         return False

   def find_children( self, linespec ):
      """Returns the parents matching the linespec, and their immediate
      children"""
      parentobjs = self.find_line_objects( linespec )
      allobjs = []
      for parent in parentobjs:
         childobjs = self.find_child_objects( parent )
         if parent.has_children == True:
            for child in childobjs:
               allobjs.append(child)
         allobjs.append(parent)
      allobjs = self.unique_objects( allobjs )
      return self.objects_to_lines( allobjs )

   def find_all_children( self, linespec ):
      """Returns the parents matching the linespec, and all children of them."""
      parentobjs = self.find_line_objects( linespec )
      allobjs = []
      for parent in parentobjs:
         childobjs = self.find_all_child_objects( parent )
         if parent.has_children == True:
            for child in childobjs:
               allobjs.append(child)
         allobjs.append(parent)
      allobjs = self.unique_objects( allobjs )
      return self.objects_to_lines( allobjs )

   def find_blocks( self, blockspec ):
      """Find all siblings of the blockspec, and then find all parents of those
      siblings. Return a list of config lines sorted by line number, lowest
      first.  Note: any children of the siblings should NOT be returned."""
      dct = {}
      retval = []
      # Find lines maching the spec
      lines = self.find_line_objects( blockspec )
      for line in lines:
         dct[line.linenum] = line
         # Find the siblings of this line
         alist = self.find_sibling_objects(line)
         for this in alist:
            dct[this.linenum] = this
      # Find the parents for everything
      for (line, lineobject) in dct.items():
         alist = self.find_parent_objects(lineobject)
         for this in alist:
            dct[this.linenum] = this
      for line in sorted(dct.keys()):
         retval.append(self.iosconfig[line])
      return retval

   def find_parents_w_child( self, parentspec, childspec ):
      """Parse through all children matching childspec, and return a list of
      parents that matched the parentspec."""
      retval = []
      childobjs = self.find_line_objects( childspec )
      for child in childobjs:
         parents = self.find_parent_objects( child )
         match_parentspec = False
         for parent in parents:
            if re.search( parentspec, self.iosconfig[parent.linenum] ):
               match_parentspec = True
         if match_parentspec == True:
            for parent in parents:
               retval.append( parent )
      retval = self.unique_objects( retval )
      retval = self.objects_to_lines( retval )
      return retval

   def find_parents_wo_child( self, parentspec, childspec ):
      """Parse through all parents matching parentspec, and return a list of
      parents that did NOT have children match the childspec.  For simplicity,
      this method only finds oldest_ancestors without immediate children that
      match."""
      retval = []
      ## Iterate over all parents, find those with non-matching children
      for parentobj in self.allparentobjs:
         if parentobj.oldest_ancestor == True:
            if re.search( parentspec, self.iosconfig[parentobj.linenum] ):
               ## Now determine whether the child matches
               match_childspec = False
               childobjs = self.find_child_objects( parentobj )
               for childobj in childobjs:
                  if re.search( childspec, self.iosconfig[childobj.linenum] ):
                     match_childspec = True
               if match_childspec == False:
                  ## We found a parent without a child matching the childspec
                  retval.append( parentobj )
      retval = self.objects_to_lines( self.unique_objects( retval ) )
      return retval

   ### The methods below are marked SEMI-PRIVATE because they return an object
   ###  or list of objects instead of the configuration text itself.
   def find_line_objects( self, linespec ):
      """SEMI-PRIVATE: Find objects whose text matches the linespec"""
      retval = []
      for ii in self.lineObjDict:
         if re.search( linespec, self.iosconfig[ii] ):
            retval.append( self.lineObjDict[ ii ] )
      return retval
   
   def find_sibling_objects( self, lineobject ):
      """SEMI-PRIVATE: Takes a singe object and returns a list of sibling
      objects"""
      siblings = lineobject.parent.children
      return siblings
   
   def find_child_objects( self, lineobject):
      """SEMI-PRIVATE: Takes a single object and returns a list of immediate children"""
      retval = lineobject.children
      return retval
   
   def find_all_child_objects( self, lineobject ):
      """SEMI-PRIVATE: Takes a single object and returns a list of decendants in all
      'children' / 'grandchildren' / etc... after it.  It should NOT return the children of siblings"""
      retval = lineobject.children
      retval = self.unique_objects( retval )   # sort the list, and get unique objects
      for candidate in retval:
         if len(candidate.children) > 0:
            for child in candidate.children:
               retval.append( child )
      retval = self.unique_objects( retval )   # ensure there are no duplicates, belt & suspenders style
      return retval

   def find_parent_objects( self, lineobject ):
      """SEMI-PRIVATE: Takes a singe object and returns a list of parent objects"""
      retval = []
      me = lineobject
      while me.parent != me:
         retval.append(me.parent)
         me = me.parent
      return retval
   
   def unique_objects( self, objectlist ):
      """SEMI-PRIVATE: Returns a list of unique objects (i.e. with no duplicates).
      The returned value is sorted by configuration line number (lowest first)"""
      dct = {}
      retval = []
      for object in objectlist:
         dct[object.linenum] = object
      for ii in sorted(dct.keys()):
         retval.append(dct[ii])
      return retval
   
   def objects_to_lines( self, objectlist ):
      """SEMI-PRIVATE: Accept a list of objects and return a list of lines.
      NOTE: The lines will NOT be reordered by this method.  Always call
      unique_objects() before this method."""
      retval = []
      for obj in objectlist:
         retval.append( self.iosconfig[obj.linenum] )
      return retval


class IOSConfigLine(object):
   """Manage IOS Config line parent / child relationships"""
   ### Example of family relationships
   ###
   #Line01:policy-map QOS_1
   #Line02: class GOLD
   #Line03:  priority percent 10
   #Line04: class SILVER
   #Line05:  bandwidth 30
   #Line06:  random-detect
   #Line07: class default
   #Line08:!
   #Line09:interface Serial 1/0
   #Line10: encapsulation ppp
   #Line11: ip address 1.1.1.1 255.255.255.252
   #Line12:!
   #Line13:access-list 101 deny tcp any any eq 25 log
   #Line14:access-list 101 permit ip any any
   #
   # parents: 01, 02, 04, 09
   # children: of 01 = 02, 04, 07
   #           of 02 = 03
   #           of 04 = 05, 06
   #           of 09 = 10, 11
   # siblings: 05 and 06
   #           10 and 11
   # oldest_ancestors: 01, 09
   # families: 01, 02, 03, 04, 05, 06, 07
   #           09, 10, 11
   # family_endpoints: 07, 11

   #
   def __init__(self, linenum ):
      """Accept an IOS line number and initialize family relationship attributes"""
      self.parent = self
      self.child_indent = 0
      self.children = []
      self.has_children = False
      self.oldest_ancestor = False
      self.family_endpoint = 0
      self.linenum = linenum
   
   def add_parent(self, parentobj):
      ## In a perfect world, I would check parentobj's type
      self.parent = parentobj
      return True
      
   def add_child(self, childobj, indent):
      ## In a perfect world, I would check childobj's type
      ##
      ## Add the child, unless we already know it
      already_know_child = False
      for child in self.children:
         if child == childobj:
            already_know_child = True
      if already_know_child == False:
         self.children.append( childobj )
         self.child_indent = indent
         self.has_children = True
         return True
      else:
         return False

   def add_text(self, text):
      self.text = text   

   def assert_oldest_ancestor(self):
      self.oldest_ancestor = True
   
   def set_family_endpoint(self, endpoint):
      # SHOULD only be set non-zero on an oldest_ancestor
      self.family_endpoint = endpoint
   
   def parent(self):
      return self.parent
   
   def children(self):
      return self.children
   
   def has_children(self):
      return self.has_children
   
   def child_indent(self):
      return self.child_indent
   
   def oldest_ancestor(self):
      return self.oldest_ancestor
   
   def family_endpoint(self):
      return self.family_endpoint
   
   def linenum(self):
      return self.linenum 

   def text(self):
      return self.text

### TODO: Add unit tests below
if __name__ == '__main__':
   parse = CiscoConfigParse("cisco_conf/config_01.conf")
   results = parse.find_blocks( "banner" )
   results1 = parse.find_parents_w_child( "policy", "bandwidth" )
   #results2 = parse.find_parents_w_child("interface", "trunk")
   # intersection, union,  & difference all require a "set"
   #results = sorted(set(results2).difference(set(results1)))
   for line in results1:
      print line