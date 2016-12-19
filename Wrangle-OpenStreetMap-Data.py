
# coding: utf-8

# # Wrangle-OpenStreetMap-Data

# ___

# On the particular project, I am using data mungling techniques to assess the quality of OpenStreetMap’s (OSM) data for the center of Singapore regarding their consistency and uniformity.
# The data wrangling takes place programmatically, using **Python** for the most of the process and **SQL** for items that need further attention while in the **PostgreSQL**.

# The dataset describes the center of Singapore, covering an area from Clementi on the west, to
# Bedok on the east and from Serangoon on the north, to Sentosa Island on the south. The size of the dataset is 96 MB and can can be downloaded from [here](http://overpass-api.de/api/map?bbox=103.7651,1.2369,103.9310,1.3539)

# ## About the project

# ### Scope

# OpenStreetMap (OSM) is a collaborative project to create a free editable map of the world. The creation and growth of OSM have been motivated by restrictions on use or availability of map information across much of the world, and the advent of inexpensive portable satellite navigation devices.  
# 
# 
# On the specific project, I am using data from https://www.openstreetmap.org and data mungling techniques, to assess the quality of their validity, accuracy, completeness, consistency and uniformity.  
# The biggest part of the wrangling takes place programmatically using Python and then the dataset is entered into a PostgreSQL database for further examination of any remaining elements that need attention. Finally, I perform some basic exploration and express some ideas for additional improvements.

# ### Skills demonstrated

# * Assessment of the quality of data for validity, accuracy, completeness, consistency and uniformity.
# * Parsing and gathering data from popular file formats such as .xml and .csv.
# * Processing data from very large files that cannot be cleaned with spreadsheet programs.
# * Storing, querying, and aggregating data using SQL.

# ### The Dataset

# OpenStreetMap's data are structured in well-formed XML documents (.osm files) that consist of the following elements:
# * **Nodes**: "Nodes" are individual dots used to mark specific locations (such as a postal box). Two or more nodes are used to draw line segments or "ways".
# * **Ways**: A "way" is a line of nodes, displayed as connected line segments. "Ways" are used to create roads, paths, rivers, etc.  
# * **Relations**: When "ways" or areas are linked in some way but do not represent the same physical thing, a "relation" is used to describe the larger entity they are part of. "Relations" are used to create map features, such as cycling routes, turn restrictions, and areas that are not contiguous. The multiple segments of a long way, such as an interstate or a state highway are grouped into a "relation" for that highway. Another example is a national park with several locations that are separated from each other. Those are also grouped into a "relation".
# 
# All these elements can carry tags describing the name, type of road, and other attributes. 
# 
# For the particular project, I am using a custom .osm file for the center of Singapore which I exported by using the overpass API. The  dataset has a volume of 96 MB and can be downloaded from this [link](http://overpass-api.de/api/map?bbox=103.7651,1.2369,103.9310,1.3539)  

# ___

# ## Data Preparation

# ### Imports and Definitions

# In[1]:

get_ipython().magic(u'matplotlib inline')

import xml.etree.cElementTree as ET
from collections import defaultdict
import re
import pprint
from operator import itemgetter
from difflib import get_close_matches

#For export to csv and data validation
import csv
import codecs
import cerberus

#For reverse geocoding
from geopy.geocoders import GoogleV3
geolocator = GoogleV3()
from geopy.exc import GeocoderTimedOut


# In[2]:

#OSM downloaded from openstreetmap
SG_OSM = '../Helper/Singapore.osm'
#The following .csv files will be used for data extraction from the XML.
NODES_PATH = "../Helper/nodes.csv"
NODE_TAGS_PATH = "../Helper/nodes_tags.csv"
WAYS_PATH = "../Helper/ways.csv"
WAY_NODES_PATH = "../Helper/ways_nodes.csv"
WAY_TAGS_PATH = "../Helper/ways_tags.csv"


# In[3]:

#Regular expressions
PROBLEMCHARS = re.compile(r'[=\+/&<>;\'\"\?%#$@\,\.\t\r\n]')


# In[4]:

#A list to save elements need further attention
PROBLEMATICS = []


# ### Parsing the Data

# The size of the dataset allows me to parse it to memory to speed up the processing.  
# In the case of a significant bigger XML, I would have to use the [iterparse()](https://docs.python.org/2/library/xml.etree.elementtree.html#xml.etree.ElementTree.iterparse) function instead.  

# In[51]:

tree = ET.parse(SG_OSM)
root = tree.getroot()


# ___

# ## Data Assessment

# An initial exploration of the dataset revealed the following problems:  
# - Abbreviations of street types like ‘Av’ instead of ‘Avenue’ and ‘Rd’ instead of ‘Road’.
# - All lowercase letters like ‘street’ instead of ‘Street’.
# - Postcodes including the first letter (S xxxxxx) or the whole name (Singapore xxxxxx) of the
# country.
# - Postcodes omitting the leading ‘0’ (probably because of declared as integers at some point
# before their import to OpenStreetMap.)
# - Multi-abbreviated amenity names.
# 
# The problems in the amenity names were to a small extent, and they were corrected directly in
# the database, the rest resolved programmatically using Python on the biggest part and a subtle portion of them needed further assessment, resolven in the database.

# ### Auditing Street Types

# To audit the street names I should extract them from the XML.  
# The street names appear in two forms in the dataset:  
# In *Node* and *Way* elements, in the form of: "*< tag k="addr:street" v="**street_name**"/>*"

# ```python
# <node id="337171253" lat="1.3028023" lon="103.8599300" version="3" timestamp="2015-08-01T01:38:25Z" changeset="33022579" uid="741163" user="JaLooNz">
#     <tag k="addr:city" v="Singapore"/>
#     <tag k="addr:country" v="SG"/>
#     <tag k="addr:housenumber" v="85"/>
#     <tag k="addr:postcode" v="198501"/>
#     <tag k="addr:street" v="Sultan Gate"/>
#     <tag k="fax" v="+65 6299 4316"/>
#     <tag k="name" v="Malay Heritage Centre"/>
#     <tag k="phone" v="+65 6391 0450"/>
#     <tag k="tourism" v="museum"/>
#     <tag k="website" v="http://malayheritage.org.sg/"/>
# </node>
# ```

# In *Way* elements that have the "*< tag k="highway" ..../>*", and the '*v*' attribute is one of ['living_street', 'motorway', 'primary', 'residential', 'secondary', 'tertiary'], as "*< tag k="name" v="**street_name**"/>*".

# ```python
# <way id="4386520" version="23" timestamp="2016-11-07T12:03:39Z" changeset="43462870" uid="2818856" user="CitymapperHQ">
#     <nd ref="26778964"/>
#     <nd ref="247749632"/>
#     <nd ref="1275309736"/>
#     <nd ref="1275309696"/>
#     <nd ref="462263980"/>
#     <nd ref="473019059"/>
#     <nd ref="4486796339"/>
#     <nd ref="1278204303"/>
#     <nd ref="3689717007"/>
#     <nd ref="246494174"/>
#     <tag k="highway" v="primary"/>
#     <tag k="name" v="Orchard Road"/>
#     <tag k="oneway" v="yes"/>
# </way>
# ```

# In[7]:

def chk_for_street(element):
    '''Extracts adrresses from elements.
    
    Args:
        element (element): An element of the XML tree
        
    Returns:
        str: If the element has an address it returns it as a string , otherwise it returns nothing.
        
    '''
    highway_types = [
        'living_street', 'motorway', 'primary', 'residential', 'secondary',
        'tertiary'
    ]
    tag = element.find("./tag[@k='addr:street']")
    if tag is None:
        if element.tag == 'way':
            tag = element.find("./tag[@k='highway']")
            try:
                if tag.get('v') in highway_types:
                    return element.find("./tag[@k='name']")
            except AttributeError:
                return
    else:
        return tag
    return


# In[8]:

def get_street_names(tree):
    '''Creates a dictionary for all elements in a given tree.
    
    Args:
        tree (ElementTree): An ElementTree object for which I want to find the street names
        
    Returns
        dict: A dictionary with the following stracture: {element_id:street_name}
        
    '''
    result = {}
    for path in ["./node", "./way"]:
        for element in tree.findall(path):
            try:
                result[element.get('id')] = chk_for_street(element).get('v')
            except (AttributeError):  #chk_for_street() returns nothing
                continue
    return result


# In[9]:

street_names = get_street_names(root)


# In[10]:

#Sample of the dictionary
pprint.pprint(dict(street_names.items()[:10]))


# I am searching for multiple versions of the same street type. The different versions include different abbreviations, like Street/St, or different letter cases, like Avenue/avenue.

# Although most of the Singaporean street names end with the street type (e.g., “Serangoon Road” or “Arab Street”) it is also common to end with a number instead (e.g. “Bedok North Avenue 1”).  
# Thus, by using regular expressions, I extracted the last word that does not contain numbers from the street name.

# In[11]:

st_types_re = re.compile(r'[a-zA-Z]+[^0-9]\b\.?')


# The result will be a dictionary with the format: *{street_type:(list_of_street_names)}*  
# I am also adding not expected street names to the "*PROBLEMATICS*" list for further assessment.

# In[12]:

def audit_st_types(streets):
    '''Extracts the "street type" part from an address
    
    Args:
        streets (dict): A dictionary containing street names in the form of {element_id:street_name}
        
    Returns:
        dict: A dictionary of street types in the form of 
        {street_type:(street_name_1,street_name_2,...,street_name_n)}
    
    '''
    result = defaultdict(set)
    for key, value in streets.iteritems():
        try:
            street_type = st_types_re.findall(value)[-1].strip()
        except (IndexError):  #One word or empty street names
            PROBLEMATICS.append((key, 'street name', value))
        result[street_type].add(value)

    return result


# In[13]:

streets = audit_st_types(street_names)
#Sample of the dictionary
pprint.pprint(dict(streets.items()[:7]))


# It would be easy to populate the list of Common Street Types with some profound values like Street or Avenue, but guessing does not take into account any local peculiarity. Instead, I searched the dataset for all the different types and used the 12 with the most occurrences (From 13th position, abbreviations start to appear).

# In[14]:

def sort_street_types(street_types):
    '''Counts the number of appearances of each street type and sorts them.
    
    Args:
        street_types (dict): A dictionary of street types in the form of 
        {street_type:(street_name_1,street_name_2,...,street_name_n)}
        
    Returns:
        list: A sorted list of tupples where each tupple includes a 
        street type and the number of occurences in the dataset.
    '''
    result = []
    for key, value in street_types.iteritems():
        result.append((key, len(value)))
        result = sorted(list(result), key=itemgetter(1), reverse=True)
    return result


# In[15]:

street_types = sort_street_types(streets)
#print a samle of the list
street_types[:15]


# In[16]:

def populate_expected(street_types, threshold):
    '''Populates the Expected list
    
    Args:
        street_types (list): A sorted list of (street_type, #_of_appearances).
        threshold (int): The number of the top elements I want to put in the "expected" list.
        
    Returns:
        list: Returns a list of the x most frequent street types (x defined by "threshold)
    
     '''
    
    expected = []
    for i in street_types[:threshold]:
        expected.append(i[0])

    return expected


# In[17]:

EXPECTED = populate_expected(street_types, 12)
EXPECTED


# To find the street names that need correction, I used the “*get_close_matches()*” function from the [difflib](https://docs.python.org/2/library/difflib.html?highlight=get_close_matches) module to find “close matches” of the 12 Common Street Types. This is what I found:

# In[18]:

def find_abbreviations(expected, data):
    """Uses get_close_matces() to find similar text
    
    Args:
        expected (list): A list of the expected street types.
        data (list): A list of all the different street types.
        
    Retturns: nothing
        
    """
    
    for i in expected:
        print i, get_close_matches(i, data, 4, 0.5)


# In[19]:

find_abbreviations(EXPECTED, list(streets.keys()))


# Now, I can map the different variations to the one it meant to be and correct all the different abbreviations of street types.

# In[20]:

mapping = {
    'road': 'Road',
    'Rd': 'Road',
    'street': 'Street',
    'Ave': 'Avenue',
    'Avebue': 'Avenue',
    'Aenue': 'Avenue',
    'park': 'Park',
    'walk': 'Walk',
    'link': 'Link',
    'Cresent': 'Crescent',
    'Terrance': 'Terrace',
    'Ter': 'Terrace'
}


# In[21]:

def update_street_type(tree):
    '''Corrects the dataset's street name according to the mapping
    
    Args:
        tree (ElementTree): An ElementTree object for which I want to clean the street names
    
    Returns: nothing
           
    '''
    changes = {}
    for path in ["./node", "./way"]:  #"elements" do not have street names.
        for element in tree.findall(path):
            try:
                tag = chk_for_street(element)
                street_name = tag.get('v')
            except (AttributeError
                    ):  #In case element doen't have "street name" attribute
                continue
            try:
                street_type = st_types_re.findall(street_name)[-1].strip()
            except (IndexError):
                #Leaves the problematic street names as is.
                #They are already in the PROBLEMATICS list.
                street_type = street_name

            if street_type in mapping:
                tag.attrib['v'] = tag.attrib['v'].replace(street_type,
                                                          mapping[street_type])

                if street_name not in changes:
                    changes[street_name] = [tag.attrib['v'], 1]
                else:
                    changes[street_name][1] += 1
    counter = 0
    for key, value in changes.iteritems():
        counter += value[1]
        if value[1] == 1:
            print key + ' ==> ' + value[0]
        else:
            print key + ' ==> ' + value[0] + " " + "(" + str(value[
                1]) + " occurrences" + ")"
    print str(counter) + " street names were fixed"
    update_street_type.called = True #Function attribute to track if a function has been called.


# In[22]:

update_street_type.called = False


# In[23]:

update_street_type(root)


# ### Auditing Postcodes

# Postcodes in Singapore consist of 6 digits with the first two, denoting the Postal Sector, take values between 01 and  80, excluding 74 (https://www.ura.gov.sg/realEstateIIWeb/resources/misc/list_of_postal_districts.htm).  
# I am searching the dataset for this pattern, correcting whatever can be addressed automatically and adding the rest to the "*PROBLEMATICS*" for further examination.

# In[24]:

def fix_pcodes():
    """Tries to find an integer between 01 and 80, excluding 74 in the postcode field and
    if needed change the field value accordingly
    
    Args: No args
    
    Returns: Nothing
    """
    postcode_re = re.compile(
        r'(([0-6][0-9])|(7([0-3]|[5-9]))|80)[0-9]{4}')# all integers between 01 and 80, excluding 74 
    for element in root.findall(".//*[@k='addr:postcode']/.."):
        tag = element.find("./*[@k='addr:postcode']")
        postcode = tag.attrib['v']
        try:
            new_tag = postcode_re.search(postcode).group(0)
            if new_tag != postcode:
                tag.attrib['v'] = postcode_re.search(postcode).group(0)
                print postcode + ' ==> ' + tag.attrib['v']
        except (AttributeError):  # If you cannot extract a valid postcode, add the element to PROBLEMATICS
            PROBLEMATICS.append((element.get('id'), 'postcode', postcode))
    fix_pcodes.called = True #Function attribute to track if a function has been called.


# In[25]:

fix_pcodes.called = False


# In[26]:

fix_pcodes()


# Postcodes were much more consistent than the street types with 3 problems fixed programmati-
# cally and 8 pending further inspection.

# ___

# ## Importing Dataset to Database

# After performing the most of the cleaning through Python, I can store the dataset in the database to examine the *PROBLEMATIC* elements and explore it further.  
# I am using PostgreSQL to present a generic solution although a lightweight database like SGLite might be more appropriate.  
# Initially, I am exporting the data in .csv files using the schema below, creating the tables and importing the .csvs.

# ### Exporting dataset to .CSVs

# In[27]:

SCHEMA = {
    'node': {
        'type': 'dict',
        'schema': {
            'id': {'required': True, 'type': 'integer', 'coerce': int},
            'lat': {'required': True, 'type': 'float', 'coerce': float},
            'lon': {'required': True, 'type': 'float', 'coerce': float},
            'user': {'required': True, 'type': 'string'},
            'uid': {'required': True, 'type': 'integer', 'coerce': int},
            'version': {'required': True, 'type': 'string'},
            'changeset': {'required': True, 'type': 'integer', 'coerce': int},
            'timestamp': {'required': True, 'type': 'string'}
        }
    },
    'node_tags': {
        'type': 'list',
        'schema': {
            'type': 'dict',
            'schema': {
                'id': {'required': True, 'type': 'integer', 'coerce': int},
                'key': {'required': True, 'type': 'string'},
                'value': {'required': True, 'type': 'string'},
                'type': {'required': True, 'type': 'string'}
            }
        }
    },
    'way': {
        'type': 'dict',
        'schema': {
            'id': {'required': True, 'type': 'integer', 'coerce': int},
            'user': {'required': True, 'type': 'string'},
            'uid': {'required': True, 'type': 'integer', 'coerce': int},
            'version': {'required': True, 'type': 'string'},
            'changeset': {'required': True, 'type': 'integer', 'coerce': int},
            'timestamp': {'required': True, 'type': 'string'}
        }
    },
    'way_nodes': {
        'type': 'list',
        'schema': {
            'type': 'dict',
            'schema': {
                'id': {'required': True, 'type': 'integer', 'coerce': int},
                'node_id': {'required': True, 'type': 'integer', 'coerce': int},
                'position': {'required': True, 'type': 'integer', 'coerce': int}
            }
        }
    },
    'way_tags': {
        'type': 'list',
        'schema': {
            'type': 'dict',
            'schema': {
                'id': {'required': True, 'type': 'integer', 'coerce': int},
                'key': {'required': True, 'type': 'string'},
                'value': {'required': True, 'type': 'string'},
                'type': {'required': True, 'type': 'string'}
            }
        }
    }
}


# In[28]:

NODE_FIELDS = ['id', 'lat', 'lon', 'user', 'uid', 'version', 'changeset', 'timestamp']
NODE_TAGS_FIELDS = ['id', 'key', 'value', 'type']
WAY_FIELDS = ['id', 'user', 'uid', 'version', 'changeset', 'timestamp']
WAY_TAGS_FIELDS = ['id', 'key', 'value', 'type']
WAY_NODES_FIELDS = ['id', 'node_id', 'position']


# In[29]:

def shape_element(element):
    """Clean and shape node or way XML element to Python dict
    
    Arrgs:
        element (element): An element of the XML tree
        
    Returns:
        dict: if element is a node, the node's attributes and tags.
              if element is a way, the ways attributes and tags along with the nodes that form the way.
    """
    node_attribs = {}
    way_attribs = {}
    way_nodes = []
    tags = [
    ]  # Handle secondary tags the same way for both node and way elements
    if element.tag == 'node':
        node_attribs['id'] = element.get('id')
        node_attribs['lat'] = element.get('lat')
        node_attribs['lon'] = element.get('lon')
        node_attribs['user'] = element.get('user')
        node_attribs['uid'] = element.get('uid')
        node_attribs['version'] = element.get('version')
        node_attribs['changeset'] = element.get('changeset')
        node_attribs['timestamp'] = element.get('timestamp')
        for child in element:
            if child.tag == 'tag':
                tag = {'id': node_attribs['id']}
                k = child.get('k')
                if not PROBLEMCHARS.search(k):
                    k = k.split(':', 1)
                    tag['key'] = k[-1]
                    tag['value'] = child.get('v')
                    if len(k) == 1:
                        tag['type'] = 'regular'
                    elif len(k) == 2:
                        tag['type'] = k[0]
                tags.append(tag)
        return {'node': node_attribs, 'node_tags': tags}
    elif element.tag == 'way':
        counter = 0
        way_attribs['id'] = element.get('id')
        way_attribs['user'] = element.get('user')
        way_attribs['uid'] = element.get('uid')
        way_attribs['version'] = element.get('version')
        way_attribs['changeset'] = element.get('changeset')
        way_attribs['timestamp'] = element.get('timestamp')
        for child in element:
            if child.tag == 'tag':
                tag = {'id': way_attribs['id']}
                k = child.get('k')
                if not PROBLEMCHARS.search(k):
                    k = k.split(':', 1)
                    tag['key'] = k[-1]
                    tag['value'] = child.get('v')
                    if len(k) == 1:
                        tag['type'] = 'regular'
                    elif len(k) == 2:
                        tag['type'] = k[0]
                tags.append(tag)
            if child.tag == 'nd':
                nd = {'id': way_attribs['id']}
                nd['node_id'] = child.get('ref')
                nd['position'] = counter
                way_nodes.append(nd)
            counter += 1
        return {'way': way_attribs, 'way_nodes': way_nodes, 'way_tags': tags}


# In[30]:

def validate_element(element, validator, schema=SCHEMA):
    """Raise ValidationError if element does not match schema
    
    Args:
        element (element): An element of the tree
        validator (cerberus.validator): a validator
        schema (dict): The schema to validate element against.
        
    Returns:
        Nothing
        
        """
    if validator.validate(element, schema) is not True:
        field, errors = next(validator.errors.iteritems())
        message_string = "\nElement of type '{0}' has the following errors:\n{1}"
        error_string = pprint.pformat(errors)

        raise Exception(message_string.format(field, error_string))


# In[31]:

class UnicodeDictWriter(csv.DictWriter, object):
    """Extend csv.DictWriter to handle Unicode input"""

    def writerow(self, row):
        super(UnicodeDictWriter, self).writerow({
            k: (v.encode('utf-8') if isinstance(v, unicode) else v)
            for k, v in row.iteritems()
        })

    def writerows(self, rows):
        for row in rows:
            self.writerow(row)


# In[32]:

def process_map(validate=True):
    """Iteratively process each XML element and write to csv(s)
    
    Arrgs:
        validate (bool): Validate the data before write them to csv or not
        
    Returns:
        Nothing
    """

    with codecs.open(NODES_PATH, 'w') as nodes_file,          codecs.open(NODE_TAGS_PATH, 'w') as nodes_tags_file,          codecs.open(WAYS_PATH, 'w') as ways_file,          codecs.open(WAY_NODES_PATH, 'w') as way_nodes_file,          codecs.open(WAY_TAGS_PATH, 'w') as way_tags_file:

        nodes_writer = UnicodeDictWriter(nodes_file, NODE_FIELDS)
        node_tags_writer = UnicodeDictWriter(nodes_tags_file, NODE_TAGS_FIELDS)
        ways_writer = UnicodeDictWriter(ways_file, WAY_FIELDS)
        way_nodes_writer = UnicodeDictWriter(way_nodes_file, WAY_NODES_FIELDS)
        way_tags_writer = UnicodeDictWriter(way_tags_file, WAY_TAGS_FIELDS)

        nodes_writer.writeheader()
        node_tags_writer.writeheader()
        ways_writer.writeheader()
        way_nodes_writer.writeheader()
        way_tags_writer.writeheader()

        validator = cerberus.Validator()
        
        #Check that the dataset has been cleared
        if update_street_type.called is not True:
            update_street_type(root)
            
        if fix_pcodes.called is not True:
            fix_pcodes()            

        for element in root.findall("./*"):
            el = shape_element(element)
            if el:
                if validate is True:
                    #try:
                    validate_element(el, validator)
                    #except:
                    #    print element.get('id')

                if element.tag == 'node':
                    nodes_writer.writerow(el['node'])
                    node_tags_writer.writerows(el['node_tags'])
                elif element.tag == 'way':
                    ways_writer.writerow(el['way'])
                    way_nodes_writer.writerows(el['way_nodes'])
                    way_tags_writer.writerows(el['way_tags'])


# In[33]:

process_map()


# ### Connection to the database

# For connection between Jupyter Notebook and PostgreSQL, I am using [ipython-sql](https://github.com/catherinedevlin/ipython-sql)

# In[35]:

"""Loading the ipython-sql module"""
get_ipython().magic(u'load_ext sql')

"""Disabling the printing of number of rows affected by each query"""
get_ipython().magic(u'config SqlMagic.feedback=False')

"""Connecting to the database"""
get_ipython().magic(u'sql postgresql://jupyter_user:notebook@localhost/Project_3')


# ### Creation of the Tables

# I am using *DELETE CASCADE* on the tables with foreign keys to ensure the drop of "*tags*" along with the related "*elements*".

# In[36]:

get_ipython().run_cell_magic(u'sql', u'', u'CREATE TABLE public.nodes\n(\n  id bigint NOT NULL,\n  lat real,\n  lon real,\n  "user" text,\n  uid integer,\n  version integer,\n  changeset integer,\n  "timestamp" text,\n  CONSTRAINT nodes_pkey PRIMARY KEY (id)\n);\n\nCREATE TABLE public.nodes_tags\n(\n  id bigint,\n  key text,\n  value text,\n  type text,\n  CONSTRAINT nodes_tags_id_fkey FOREIGN KEY (id)\n      REFERENCES public.nodes (id) MATCH SIMPLE\n      ON UPDATE NO ACTION ON DELETE CASCADE\n);\n\nCREATE TABLE public.ways\n(\n  id bigint NOT NULL,\n  "user" text,\n  uid integer,\n  version text,\n  changeset integer,\n  "timestamp" text,\n  CONSTRAINT ways_pkey PRIMARY KEY (id)\n);\n\nCREATE TABLE public.ways_nodes\n(\n  id bigint NOT NULL,\n  node_id bigint NOT NULL,\n  "position" integer NOT NULL,\n  CONSTRAINT ways_nodes_id_fkey FOREIGN KEY (id)\n      REFERENCES public.ways (id) MATCH SIMPLE\n      ON UPDATE NO ACTION ON DELETE NO ACTION,\n  CONSTRAINT ways_nodes_node_id_fkey FOREIGN KEY (node_id)\n      REFERENCES public.nodes (id) MATCH SIMPLE\n      ON UPDATE NO ACTION ON DELETE CASCADE\n);\n\nCREATE TABLE public.ways_tags\n(\n  id bigint NOT NULL,\n  key text NOT NULL,\n  value text NOT NULL,\n  type text,\n  CONSTRAINT ways_tags_id_fkey FOREIGN KEY (id)\n      REFERENCES public.ways (id) MATCH SIMPLE\n      ON UPDATE NO ACTION ON DELETE CASCADE\n);')


# ### Importing the data

# After copying the files to the remote server, i can import them to the database.

# In[37]:

get_ipython().run_cell_magic(u'sql', u'', u"COPY public.nodes\nFROM '/home/yannis/Projects/Data_Analysis/Wrangle-OpenStreetMap-Data/Helper/nodes.csv'\nCSV HEADER;\n\nCOPY public.nodes_tags\nFROM '/home/yannis/Projects/Data_Analysis/Wrangle-OpenStreetMap-Data/Helper/nodes_tags.csv'\nCSV HEADER;\n\nCOPY public.ways\nFROM '/home/yannis/Projects/Data_Analysis/Wrangle-OpenStreetMap-Data/Helper/ways.csv'\nCSV HEADER;\n\nCOPY public.ways_nodes\nFROM '/home/yannis/Projects/Data_Analysis/Wrangle-OpenStreetMap-Data/Helper/ways_nodes.csv'\nCSV HEADER;\n\nCOPY public.ways_tags\nFROM '/home/yannis/Projects/Data_Analysis/Wrangle-OpenStreetMap-Data/Helper/ways_tags.csv'\nCSV HEADER;")


# ___

# ## Data assesment in the database

# In[38]:

pprint.pprint(PROBLEMATICS)


# I am querying the database for the above elements.

# In[52]:

def element_type(element_id):
    """From the element's id, returns the element's type.
    (I need to know the element's type, to run the appropriate query.)
    
    Args:
        element_id (str): The 'id' of the element
        
    Returns:
        (str): The tag of the element.
    """
    path = str('./*[@id="' + element_id + '"]')
    
    return root.find(path).tag


# In[53]:

def get_element_tags(element_id):
    """Returns all the tags for a specific element
    
    Args:
        element_id (str):  The 'id' of the element
        
    Returns (sql.run.ResultSet): The result of the query
    
    """
    if element_type(element_id) == 'node':
        tag = get_ipython().magic(u"sql SELECT 'Node' AS el_type, * FROM nodes_tags WHERE nodes_tags.id = $element_id")
    elif element_type(element_id) == 'way':
        tag = get_ipython().magic(u"sql SELECT 'Way' AS el_type, * FROM ways_tags WHERE ways_tags.id = $element_id")
    return tag


# In[56]:

get_element_tags(PROBLEMATICS[0][0])


# In[57]:

get_element_tags(PROBLEMATICS[2][0])


# For the two elements above, it looks like the "*street*" value is actually a housenumber.

# In[58]:

get_ipython().run_cell_magic(u'sql', u'', u"UPDATE ways_tags SET key = 'housenumber'\nWHERE (id = '453243296' OR id = '453253763') AND key = 'street'")


# In[59]:

get_element_tags(PROBLEMATICS[1][0])


# In[60]:

get_element_tags(PROBLEMATICS[3][0])


# "Habour Link" is a place of worship on "Alexandra Terrace"

# In[61]:

get_ipython().run_cell_magic(u'sql', u'', u"UPDATE ways_tags SET value = 'Alexandra Terrace'\nWHERE (id = '453227146' OR id = '46649997') AND key = 'street'")


# In[62]:

get_element_tags(PROBLEMATICS[4][0])


# "Toa Payoh Vista Market" is on 74 Lor 4 Toa Payoh (https://goo.gl/maps/UpoYE2Q4owm)

# In[63]:

get_ipython().run_cell_magic(u'sql', u'', u"INSERT INTO ways_tags VALUES ('169844052','housenumber','74','addr');\n\nUPDATE ways_tags SET value = '310074' WHERE id ='169844052' AND key = 'postcode';\n\nUPDATE ways_tags SET value = 'Lor 4 Toa Payoh' WHERE id = '169844052' AND key = 'street'")


# In[64]:

get_element_tags(PROBLEMATICS[5][0])


# It looks like "135" is a housenumber not a postcode. To find missing parts of an address (like a postcode) I'm querying the Google Maps' API.

# In[96]:

def complete_address(address):
    """
    Tries to find the full address from part of the address (e.g. without the postcode)
    
    Args:
        address(str): Partial address
        
    Returns:
        (str): Full address
    
    """
    while True:  #Retry the call in case of GeocoderTimedOut error
        try:
            location = geolocator.geocode(address)
            #coordinates = str(coord[0]) + "," + str(coord[1])
            print location.raw['formatted_address']
        except GeocoderTimedOut:
            continue
        break


# In[66]:

complete_address(' 135 Jln Pelatina, Singapore')


# I cannot find the postcode, I am just changing the "postcode" to "housenumber".

# In[67]:

get_ipython().magic(u"sql UPDATE nodes_tags SET key = 'housenumber' WHERE id = '1318498347' AND value = '135'")


# In[68]:

get_element_tags(PROBLEMATICS[6][0])


# In[69]:

complete_address(' 136 Orchard Road, Singapore')


# I cannot find a valid postcode. I am deleting the specific tag.

# In[70]:

get_ipython().magic(u"sql DELETE FROM nodes_tags WHERE id = '3026819436' AND key = 'postcode'")


# In[71]:

get_element_tags(PROBLEMATICS[7][0])


# In[72]:

complete_address(' 6 Sago Street, Singapore')


# In[73]:

get_ipython().magic(u"sql UPDATE nodes_tags SET value = '059011' WHERE id = '3756813987' AND key = 'postcode'")


# In[74]:

get_element_tags(PROBLEMATICS[8][0])


# The specific amenity is on "279 New Bridge Road, Singapore 088752" (https://goo.gl/maps/K7JzQ3Ujsvq)

# In[75]:

get_ipython().run_cell_magic(u'sql', u'', u"UPDATE nodes_tags SET value = '088752' WHERE id = '4338649392' AND key = 'postcode';\n\nINSERT INTO nodes_tags VALUES \n('4496749591','housenumber','279','addr'),\n('4496749591','street','New Bridge Road','addr')")


# In[76]:

get_element_tags(PROBLEMATICS[9][0])


# This amenity does not exist anymore (https://www.bukittimahshoppingcentre.sg/directory/). I'm deleting the whole node.

# In[77]:

get_ipython().magic(u"sql DELETE FROM nodes WHERE id = '4496749591'")


# In[78]:

get_element_tags(PROBLEMATICS[10][0])


# In[79]:

complete_address(' 80 Rhu Cross, Singapore')


# In[80]:

get_ipython().magic(u"sql UPDATE ways_tags SET value = '437437' WHERE id = '23946435' AND key = 'postcode'")


# "*Way*" element 169844052 has been corrected already.

# In[81]:

get_element_tags(PROBLEMATICS[12][0])


# In[82]:

complete_address('6 Sago Street, Singapore')


# In[83]:

get_ipython().magic(u"sql UPDATE ways_tags SET value = '059011' WHERE id = '172769494' AND key = 'postcode'")


# ___

# ## Data Exploration

# ### Dataset Specific

# Below you may find some basic attributes of the dataset.

# #### Size of the database

# In[84]:

size_in_bytes = get_ipython().magic(u"sql SELECT pg_database_size('Project_3');")
print "DB size: " + str(size_in_bytes[0][0]/1024**2) + ' MB'


# #### Number of Unique Users

# In[85]:

get_ipython().run_cell_magic(u'sql', u'', u'SELECT count(DISTINCT(uid)) AS "Unique Users"\nFROM (SELECT uid FROM nodes \n      UNION \n      SELECT uid FROM ways) AS elements;')


# #### Top 10 Users (by number of entries)

# In[86]:

get_ipython().run_cell_magic(u'sql', u'', u'SELECT nodes_ways."user" AS "User", COUNT(*) AS "Users"\nFROM (SELECT "user" FROM nodes\n      UNION ALL\n      SELECT "user" FROM ways) AS nodes_ways\nGROUP BY nodes_ways."user"\nORDER BY "Users" DESC\nLIMIT 10;')


# #### Number of Nodes and Ways

# In[87]:

n_nodes = get_ipython().magic(u'sql SELECT COUNT(*) FROM nodes')
n_ways = get_ipython().magic(u'sql SELECT COUNT(*) FROM ways')

print "Number of 'nodes: " + str(n_nodes[0][0])
print "Number of 'ways: " + str(n_ways[0][0])


# ### Area Specific

# #### Most popular streets

# In[88]:

get_ipython().run_cell_magic(u'sql', u'', u'SELECT street_names.value AS "Street", COUNT(street_names.value) AS "Times Refered"\nFROM\n\t(SELECT nodes_tags.value\n\tFROM nodes_tags\n\tWHERE type = \'addr\' AND key = \'street\'\n\tUNION ALL\n\tSELECT ways_tags.value\n\tFROM ways_tags\n\tWHERE \ttype = \'addr\' AND key = \'street\'\n\t\tOR\n\t\tid in\n\t\t\t(SELECT id\n\t\t\tFROM ways_tags\n\t\t\tWHERE key = \'highway\')\n\tAND key = \'name\') AS street_names\nGROUP BY street_names.value\nORDER BY "Times Refered" DESC\nLIMIT 10')


# #### Most frequent amenities

# Anyone who has lived in Singapore knows the love of Singaporeans for food. No surprises here; restaurants are, by far, on the top of the results.

# In[89]:

get_ipython().run_cell_magic(u'sql', u'', u'SELECT value AS "Amenity", COUNT(value) AS "Occurrences"\nFROM\t(SELECT *\n\tFROM nodes_tags\n\tUNION ALL\n\tSELECT *\n\tFROM nodes_tags) as tags\nWHERE key = \'amenity\'\nGROUP BY value\nORDER BY "Occurrences" DESC\nLIMIT 10')


# #### Most popular cuisine

# In[90]:

get_ipython().run_cell_magic(u'sql', u'', u'SELECT value AS "Cuisine", COUNT(*) AS "Restaurants" \nFROM (SELECT * FROM nodes_tags \n      UNION ALL \n      SELECT * FROM ways_tags) tags\nWHERE tags.key=\'cuisine\'\nGROUP BY value\nORDER BY "Restaurants"  DESC\nLIMIT 10')


# #### ATMs

# In[91]:

get_ipython().run_cell_magic(u'sql', u'', u'SELECT value AS "Bank", COUNT(value) AS "ATMs"\nFROM nodes_tags\nWHERE id in\n    (SELECT id\n    FROM nodes_tags\n    WHERE value = \'atm\')\n    AND\n    key = \'operator\'\nGROUP BY value\nORDER BY "ATMs" DESC')


# There are different abbreviations of bank names and some records that are not banks.

# In[92]:

get_ipython().run_cell_magic(u'sql', u'', u"UPDATE nodes_tags\nSET value = 'POSB'\nWHERE value = 'Posb';\n\nUPDATE nodes_tags\nSET value = 'UOB'\nWHERE value = 'Uob';\n\nUPDATE nodes_tags\nSET value = 'OCBC'\nWHERE value = 'Overseas Chinese Banking Corporation';")


# In[93]:

get_ipython().run_cell_magic(u'sql', u'', u"DELETE FROM nodes\nWHERE id IN\n\t(SELECT id\n\tFROM nodes_tags\n\tWHERE key = 'operator'\n\tAND (value = 'singapore room home'\n\tOR\n\tvalue = 'home'))")


# In[94]:

get_ipython().run_cell_magic(u'sql', u'', u'SELECT value AS "Bank", COUNT(value) AS "ATMs"\nFROM nodes_tags\nWHERE id in\n    (SELECT id\n    FROM nodes_tags\n    WHERE value = \'atm\')\n    AND\n    key = \'operator\'\nGROUP BY value\nORDER BY "ATMs" DESC')


# #### Religion

# Singapore is well-known for its multicultural environment. People with different religious and ethnic heritages are forming the modern city-state. This is reflected in the variety of temples that can be found in the country.

# In[95]:

get_ipython().run_cell_magic(u'sql', u'', u'SELECT tags.value AS "Religion", COUNT(*) AS "Temples" \nFROM (SELECT * FROM nodes_tags\n      UNION ALL \n      SELECT * FROM ways_tags) tags\nWHERE tags.key=\'religion\'\nGROUP BY tags.value\nORDER BY "Temples" DESC;')


# ___

# ## Ideas for additional improvements.

# There are several areas of improvement of the project in the future.
# The first one is on the completeness of the data. All the above analysis is based on a dataset that reflects a big part of Singapore but not the whole country. The reason for this is the lack of a way to download a dataset for the entire Singapore without including parts of the neighboring countries. The analyst has to either select a part of the island/country or select a wider area that includes parts of Malaysia and Indonesia. Also, because of relations between nodes, ways, and relations, the downloaded data expand much further than the actual selection. Below you can see a plotting of the coordinates of the nodes of a dataset from a tight selection of Singapore. You can notice that huge parts of nearby countries were selected.

# ![initial selection](Resources/images/initial_selection.png)

# As a future improvement, I would download a wider selection or the metro extract from [MapZen](https://mapzen.com/data/metro-extracts/metro/singapore/) and filter the non-Singaporean nodes and their references. The initial filtering could take place by introducing some latitude/longitude limits in the code to sort out most of the "non-SG" nodes.

# ![filter to square](Resources/images/filter_to_square.png)

# Then, I would download a shapefile for Singapore (e.g. http://www.diva-gis.org/gdata), use a GIS library like [Fiona](https://pypi.python.org/pypi/Fiona) to create a polygon and finally with a geometric library like [Shapely](https://github.com/Toblerity/Shapely) and compare all the nodes' coordinate against this polygon. Finally, I would clean all the ways and relations from the "non-sg" nodes and remove these that become childless to conclude with a dataset of all (and only) Singapore.

# ![After GIS](Resources/images/after_gis.png)

# The drawback of the above technic is that the comparison of each node against the polygon is a very time-consuming procedure with my initial tests taking 17-18 hours to produce a result. This is the reason the above approach left as a future improvement probably along with the use of multithreading technics to speed up the process.

# The second area with room for future improvement is the exploratory analysis of the dataset.  Just to mention some of the explorings that could take place:
# * Distribution of commits per contributor.
# * Plotting of element creation per type, per day.
# * Distribution of distance between different types of amenities
# * Popular franchises in the country (fast food, conventional stores, etc.)
# * Selection of a bank based on the average distance you have to walk for an ATM.
# * Which area has the biggest parks and recreation spaces.  
# 
# The scope of the current project was the wrangling of the dataset, so all the above have been left for future improvement.

# Finally, open data are here to make average people's life better. For the non-data analyst, it would be nice if there was an application (mobile or web) that could evaluate the suitability of a potential rental house. The work addresses of all family members, importance weights on several amenities like supermarkets, convenience stores, cafes,  public transportation, etc. and the application would calculate the suitability of each potential rental. The user would be able to sort them by score and compare them.

# ___

# ## References
# 
# 

# Udacity - https://www.udacity.com/  
# Wikipedia - https://www.wikipedia.org/  
# OpenStreetMap - https://www.openstreetmap.org  
# Overpass API - http://overpass-api.de/  
# Python Software Foundation - https://www.python.org/  
# Urban Redevelopment Authority of Singapore - https://www.ura.gov.sg  
# Catherine Devlin's Github repository - https://github.com/catherinedevlin/ipython-sql  
# Google Map APIs - https://developers.google.com/maps/
