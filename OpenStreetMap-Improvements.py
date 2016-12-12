
# coding: utf-8

# # Wrangling OpenStreetMap Data

# ___

# ## About the project

# ### Scope

# OpenStreetMap (OSM) is a collaborative project to create a free editable map of the world. The creation and growth of OSM have been motivated by restrictions on use or availability of map information across much of the world, and the advent of inexpensive portable satellite navigation devices.  
# 
# 
# On the specific project, I am using data from https://www.openstreetmap.org and data mungling techniques, to assess the quality of their validity, accuracy, completeness, consistency and uniformity.  
# The dataset I am using describes the center of Singapore, covering an area from Clementi on the west, to Bedok on the east and from Serangoon on the north, to Sentosa Island on the south.  
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
# For the particular project, I am using a custom .osm file for the center of Singapore which I exported by using the overpass API. The  dataset has a volume of 96 MB and can be downloaded from the following link:
# http://overpass-api.de/api/map?bbox=103.7651,1.2369,103.9310,1.3539  

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
from collections import Counter
from geopy.exc import GeocoderTimedOut


# In[2]:

#OSM downloaded from openstreetmap
SG_OSM = 'Resources/map.osm'
#The following .csv files will be used for data extraction from the XML.
NODES_PATH = "nodes.csv"
NODE_TAGS_PATH = "nodes_tags.csv"
WAYS_PATH = "ways.csv"
WAY_NODES_PATH = "ways_nodes.csv"
WAY_TAGS_PATH = "ways_tags.csv"


# In[3]:

#Regular expressions
PROBLEMCHARS = re.compile(r'[=\+/&<>;\'\"\?%#$@\,\.\t\r\n]')


# In[4]:

#A list to save elements need further attention
PROBLEMATICS = []


# ### Parsing the Data

# The size of the dataset allows me to parse it to memory to speed up the processing.  
# In the case of a significant bigger XML, I would have to use the *iterparse()* function instead.  
# (https://docs.python.org/2/library/xml.etree.elementtree.html#xml.etree.ElementTree.iterparse)

# In[5]:

tree = ET.parse(SG_OSM)
root = tree.getroot()


# ___

# ## Data Assesment

# An initial exploration of the dataset revealed the following problems:  
# * Incomplete or over-abbreviated street names
# * Incomplete or incorrect postcodes
# * Multi-abbreviated amenities names
# 
# The problematic elements that can be solved programmatically will be addressed during the wrangling process using code; the rest will be added to the database, and they will be marked (by adding them to the "*PROBLEMATICS*" list) for further assessment while in the database.

# ### Auditing Street Types

# To audit the street names I should extract them from the XML. The street names appear in two forms in the dataset:
# * In *Node* and *Way* elements, in the form of: "< tag k="addr:street" v="**street_name**"/>"
# * in some *Way* elements that have the "< tag k="highway" ..../>", and the '*v*' attribute is one of ['living_street', 'motorway', 'primary', 'residential', 'secondary', 'tertiary'], as "< tag k="name" v="**street_name**"/>

# In[6]:

def chk_for_street(element):
    '''Extracts adrresses from elements.'''
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
    if tag is not None:
        return tag
    return


# In[7]:

def get_street_names(tree):
    '''Creates a dictionary {element_id:street_name} for all elements in a given tree.'''
    result = {}
    for path in ["./node", "./way"]:
        for element in tree.findall(path):
            try:
                result[element.get('id')] = chk_for_street(element).get('v')
            except (AttributeError):  #chk_for_street() returns nothing
                continue
    return result


# In[8]:

street_names = get_street_names(root)


# In[9]:

#Sample of the dictionary
pprint.pprint(dict(street_names.items()[0:10]))


# I am searching for multiple versions of the same street type. The different versions include different abbreviations, like Street/St, or different letter cases, like Avenue/avenue.

# Although most os Singaporean street names end with the street type (e.g., "Serangoon Road" or "Arab Street") it is very common to end with a number instead (e.g. "Bedok North Avenue 1"). Thus, I am using the following regular expression that omits the last string if it contains a number.

# In[10]:

st_types_re = re.compile(r'[a-zA-Z]+[^0-9]\b\.?')


# The result will be a dictionary with the format: *{street_type:(list_of_street_names)}*  
# I am also adding not expected street names to the "*PROBLEMATICS*" list for further assessment.

# In[11]:

def audit_st_types():
    '''Extracts the "street type" part from an address '''
    result = defaultdict(set)
    for key, value in street_names.iteritems():
        try:
            street_type = st_types_re.findall(value)[-1].strip()
        except (IndexError):  #One word or empty street names
            PROBLEMATICS.append((key, 'street name', value))
        result[street_type].add(value)

    return result


# In[12]:

streets = audit_st_types()
#Sample of the dictionary
pprint.pprint(dict(streets.items()[0:10]))


# Using the *streets* dictionary, I can create a list of expected street types. It would be easy to manually populate the list with some profound values (like Street, Avenue, etc.), but guessing does not take into account any local peculiarity. Instead, I am searching the dataset for all the different street types, and count the number of occurrences of each one.

# In[13]:

def sort_street_types(street_types):
    '''Counts the number of appearances of each street type and sorts them.'''
    result = []
    for key, value in street_types.iteritems():
        result.append((key, len(value)))
        result = sorted(list(result), key=itemgetter(1), reverse=True)
    return result


# In[14]:

street_types = sort_street_types(streets)
#print a samle of the list
street_types[:15]


# After the top 12 street types, abbreviations ("Ave") start to appear. The top 12 can be used to populate the *Expected* street types.

# In[15]:

def populate_expected(street_types, threshold):
    '''Populates the Expected list'''
    expected = []
    for i in street_types[:threshold]:
        expected.append(i[0])

    return expected


# In[16]:

EXPECTED = populate_expected(street_types, 12)
EXPECTED


# Again, instead of guessing the possible abbreviations, I can use the "*get_close_matches()*" from the "*difflib*" module to find them.
# (https://docs.python.org/2/library/difflib.html?highlight=get_close_matches)

# In[17]:

def find_abbreviations(expected, data):
    """Uses get_close_matces() to find similar text"""
    for i in expected:
        print i, get_close_matches(i, data, 4, 0.5)


# In[18]:

find_abbreviations(EXPECTED, list(streets.keys()))


# Now, I can map the different variations to the one it meant to be.

# In[19]:

mapping = {
    'road': 'Road',
    'Rd': 'Road',
    'street': 'Street',
    'Ave': 'Avenue',
    'Avebue': 'Avenue',
    'Aenue': 'Avenue',
    'park': 'Park',
    'walk': 'Walk',
    'Cl': 'Close',
    'link': 'Link',
    'Cresent': 'Crescent',
    'Terrance': 'Terrace',
    'Ter': 'Terrace'
}


# Now, I can correct all the different abbreviations of street types.

# In[20]:

def update_street_type(tree):
    '''Corrects the dataset's street name according to the mapping'''
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

    for key, value in changes.iteritems():
        if value[1] == 1:
            print key + ' ==> ' + value[0]
        else:
            print key + ' ==> ' + value[0] + " " + "(" + str(value[
                1]) + " occurrences" + ")"


# In[21]:

update_street_type(root)


# At this point, the street names are free of different abbreviations and spelling errors. The elements in the *PROBLEMATICS* list needs further attention, and they will be assessed in the database.

# ### Auditing Postcodes

# Postcodes in Singapore consist of 6 digits with the first two, denoting the Postal Sector, take values between 01 and  80, excluding 74 (https://www.ura.gov.sg/realEstateIIWeb/resources/misc/list_of_postal_districts.htm).  
# I am searching the dataset for this pattern, correcting whatever can be addressed automatically and adding the rest to the "*PROBLEMATICS*" for further examination.

# In[22]:

def fix_pcodes():
    f_postcode_re = re.compile(
        r'^((([0-6][0-9])|(7([0-3]|[5-9]))|80)[0-9]{4})$')  #Full match
    postcode_re = re.compile(
        r'(([0-6][0-9])|(7([0-3]|[5-9]))|80)[0-9]{4}')  #Partial match
    for element in root.findall(".//*[@k='addr:postcode']/.."):
        tag = element.find("./*[@k='addr:postcode']")
        postcode = tag.attrib['v']
        if not f_postcode_re.match(postcode):
            try:
                #Trying to remedy the postcode by removing any
                #unnecessary string before or after the postcode
                tag.attrib['v'] = postcode_re.search(postcode).group(0)
                print postcode + ' ==> ' + tag.attrib['v']
            except (
                    AttributeError
            ):  # If there is not a 6 digits sequence in the value, delete the element
                PROBLEMATICS.append((element.get('id'), 'postcode', postcode))


# In[23]:

fix_pcodes()


# ___

# ## Importing Dataset to Database

# After performing the most of the cleaning through Python, I can store the dataset in the database to examine the *PROBLEMATIC* elements and explore it further.  
# I am using PostgreSQL to present a generic solution although a lightweight database like SGLite might be more appropriate.  
# Initially, I am exporting the data in .csv files using the schema below, creating the tables and importing the .csvs.

# ### Exporting dataset to .CSVs

# In[24]:

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


# In[25]:

NODE_FIELDS = ['id', 'lat', 'lon', 'user', 'uid', 'version', 'changeset', 'timestamp']
NODE_TAGS_FIELDS = ['id', 'key', 'value', 'type']
WAY_FIELDS = ['id', 'user', 'uid', 'version', 'changeset', 'timestamp']
WAY_TAGS_FIELDS = ['id', 'key', 'value', 'type']
WAY_NODES_FIELDS = ['id', 'node_id', 'position']


# In[26]:

def shape_element(element,
                  node_attr_fields=NODE_FIELDS,
                  way_attr_fields=WAY_FIELDS,
                  problem_chars=PROBLEMCHARS,
                  default_tag_type='regular'):
    """Clean and shape node or way XML element to Python dict"""
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


# In[27]:

def validate_element(element, validator, schema=SCHEMA):
    """Raise ValidationError if element does not match schema"""
    if validator.validate(element, schema) is not True:
        field, errors = next(validator.errors.iteritems())
        message_string = "\nElement of type '{0}' has the following errors:\n{1}"
        error_string = pprint.pformat(errors)

        raise Exception(message_string.format(field, error_string))


# In[28]:

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


# In[29]:

def process_map(file_in, validate):
    """Iteratively process each XML element and write to csv(s)"""

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


# In[30]:

process_map(SG_OSM, validate=True)


# ### Connection to the database

# For connection between Jupyter Notebook and PostgreSQL, I am using *ipython-sql* (https://github.com/catherinedevlin/ipython-sql)

# In[31]:

"""Loading the ipython-sql module"""
get_ipython().magic(u'load_ext sql')

"""Disabling the printing of number of rows affected by each query"""
get_ipython().magic(u'config SqlMagic.feedback=False')

"""Connecting to the database"""
get_ipython().magic(u'sql postgresql://jupyter_user:notebook@192.168.100.2/Project_3')


# ### Creation of the Tables

# I am using *DELETE CASCADE* on the tables with foreign keys to ensure the drop of tags along with the related elements.

# In[32]:

get_ipython().run_cell_magic(u'sql', u'', u'CREATE TABLE public.nodes\n(\n  id bigint NOT NULL,\n  lat real,\n  lon real,\n  "user" text,\n  uid integer,\n  version integer,\n  changeset integer,\n  "timestamp" text,\n  CONSTRAINT nodes_pkey PRIMARY KEY (id)\n);\n\nCREATE TABLE public.nodes_tags\n(\n  id bigint,\n  key text,\n  value text,\n  type text,\n  CONSTRAINT nodes_tags_id_fkey FOREIGN KEY (id)\n      REFERENCES public.nodes (id) MATCH SIMPLE\n      ON UPDATE NO ACTION ON DELETE CASCADE\n);\n\nCREATE TABLE public.ways\n(\n  id bigint NOT NULL,\n  "user" text,\n  uid integer,\n  version text,\n  changeset integer,\n  "timestamp" text,\n  CONSTRAINT ways_pkey PRIMARY KEY (id)\n);\n\nCREATE TABLE public.ways_nodes\n(\n  id bigint NOT NULL,\n  node_id bigint NOT NULL,\n  "position" integer NOT NULL,\n  CONSTRAINT ways_nodes_id_fkey FOREIGN KEY (id)\n      REFERENCES public.ways (id) MATCH SIMPLE\n      ON UPDATE NO ACTION ON DELETE NO ACTION,\n  CONSTRAINT ways_nodes_node_id_fkey FOREIGN KEY (node_id)\n      REFERENCES public.nodes (id) MATCH SIMPLE\n      ON UPDATE NO ACTION ON DELETE CASCADE\n);\n\nCREATE TABLE public.ways_tags\n(\n  id bigint NOT NULL,\n  key text NOT NULL,\n  value text NOT NULL,\n  type text,\n  CONSTRAINT ways_tags_id_fkey FOREIGN KEY (id)\n      REFERENCES public.ways (id) MATCH SIMPLE\n      ON UPDATE NO ACTION ON DELETE CASCADE\n);')


# ### Importing the data

# In[33]:

get_ipython().run_cell_magic(u'sql', u'', u"COPY public.nodes\nFROM '/home/yannis/ownCloud/Udacity/Data_Science/Projects/Project_3/nodes.csv'\nDELIMITER ','\nENCODING 'utf8'\nCSV HEADER;\n\nCOPY public.nodes_tags\nFROM '/home/yannis/ownCloud/Udacity/Data_Science/Projects/Project_3/nodes_tags.csv'\nDELIMITER ','\nENCODING 'utf8'\nCSV HEADER;\n\nCOPY public.ways\nFROM '/home/yannis/ownCloud/Udacity/Data_Science/Projects/Project_3/ways.csv'\nDELIMITER ','\nENCODING 'utf8'\nCSV HEADER;\n\nCOPY public.ways_nodes\nFROM '/home/yannis/ownCloud/Udacity/Data_Science/Projects/Project_3/ways_nodes.csv'\nDELIMITER ','\nENCODING 'utf8'\nCSV HEADER;\n\nCOPY public.ways_tags\nFROM '/home/yannis/ownCloud/Udacity/Data_Science/Projects/Project_3/ways_tags.csv'\nDELIMITER ','\nENCODING 'utf8'\nCSV HEADER;")


# ___

# ## Data assesment in the database

# Now it is time assess the *PROBLEMATIC* elements.  
# There are 5 elements with wrong **street name** and 8 elements with wrong **postcode**.

# In[34]:

pprint.pprint(PROBLEMATICS)


# The strategy I am following is to export the coordinates of each element and run reverse geocoding queries to get their addresses. Particularly for the way elements, since they are arrays of nodes, I am getting the addresses of all related nodes, and selecting the one with the most occurrences.  
# For the reverse geocoding I am using *Google map's* geocoder because OpenStreetMap's (*Nominatim*) may return the same errors.

# In[35]:

def element_type(element_id):
    """From the element's id, returns the element's type.
    (I need to know the element's type, to run the appropriate query.)"""
    path = str('./*[@id="' + str(element_id) + '"]')

    return root.find(path).tag


# In[36]:

def element_coordinates(element_id):
    """Return the coordinates of an element from its id"""
    el_type = element_type(element_id)
    if el_type == 'node':
        coordinates = get_ipython().magic(u'sql SELECT lat, lon FROM nodes WHERE nodes.id = $element_id')
    elif el_type == 'way':
        coordinates = get_ipython().magic(u'sql SELECT lat, lon FROM nodes, ways_nodes WHERE nodes.id = ways_nodes.node_id and ways_nodes.id = $element_id')
    else:
        print "Wrong element type"
    return coordinates


# In[37]:

def element_info(elements_list):
    """Accepts a list of elements in the form (element_id,problem_type,original_value), and returns
    a dictionary in the form {(element_id,problem_type,original_value):(formatted_address,element_type)}"""
    result = {}
    for element in elements_list:
        coordinates = element_coordinates(element[0])
        l = []
        for lat, lon in coordinates:
            a = str(lat) + "," + str(lon)
            while True:  #Retry the call in case of GeocoderTimedOut error
                try:
                    location = geolocator.reverse((a))
                except GeocoderTimedOut:
                    continue
                except SSLError:  #This is also a timeout exception
                    continue
                break
            l.append(location[0].raw['formatted_address'])
        count = Counter(l)
        result[element] = (count.most_common()[0], element_type(element[0]))
    return result


# In[38]:

pprint.pprint(element_info(PROBLEMATICS))


# 9 of the problemating elements resolved by the reverse geocoding. I'm updating their values.

# In[39]:

get_ipython().run_cell_magic(u'sql', u'', u"UPDATE ways_tags\nSET value = '310074'\nWHERE ways_tags.id = '169844052' AND ways_tags.type = 'addr' AND ways_tags.key = 'postcode';\n\nUPDATE ways_tags\nSET value = 'Toa Payoh'\nWHERE ways_tags.id = '169844052' AND ways_tags.type = 'addr' AND ways_tags.key = 'street';\n\nUPDATE nodes_tags\nSET value = '058840'\nWHERE nodes_tags.id = '3756813987' AND nodes_tags.type = 'addr' AND nodes_tags.key = 'postcode';\n\nUPDATE nodes_tags\nSET value = '088755'\nWHERE nodes_tags.id = '4338649392' AND nodes_tags.type = 'addr' AND nodes_tags.key = 'postcode';\n\nUPDATE nodes_tags\nSET value = '588179'\nWHERE nodes_tags.id = '4496749591' AND nodes_tags.type = 'addr' AND nodes_tags.key = 'postcode';\n\nUPDATE ways_tags\nSET value = 'Alexandra Terrace'\nWHERE ways_tags.id = '453227146' AND ways_tags.type = 'addr' AND ways_tags.key = 'street';\n\nUPDATE ways_tags\nSET value = 'Belimbing Avenue'\nWHERE ways_tags.id = '453243296' AND ways_tags.type = 'addr' AND ways_tags.key = 'street';\n\nUPDATE ways_tags\nSET value = 'Lichi Avenue'\nWHERE ways_tags.id = '453253763' AND ways_tags.type = 'addr' AND ways_tags.key = 'street';\n\nUPDATE ways_tags\nSET value = 'Alexandra Terrace'\nWHERE ways_tags.id = '46649997' AND ways_tags.type = 'addr' AND ways_tags.key = 'street';")


# For 3 elements I had to search the returned address on the web for getting the right postcode.

# In[40]:

get_ipython().run_cell_magic(u'sql', u'', u"UPDATE nodes_tags\nSET value = '575268'\nWHERE nodes_tags.id = '1318498347' AND nodes_tags.type = 'addr' AND nodes_tags.key = 'postcode';\n\nUPDATE ways_tags\nSET value = '058830'\nWHERE ways_tags.id = '172769494' AND ways_tags.type = 'addr' AND ways_tags.key = 'postcode';\n\nUPDATE ways_tags\nSET value = '058830'\nWHERE ways_tags.id = '23946435' AND ways_tags.type = 'addr' AND ways_tags.key = 'postcode';")


# Finally, for one of the element, I could not find a valid postcode. The specific node (3026819436) represents a medical equipment company named Liana Medic LTD. On their *contact* page there are both errors in the street name ("Ochard" instead of "Orchard") and invalid postcode ("2424", the same as the dataset)  (http://www.lianamedic.com/contact-us). I decided to remove the specific node from the '*nodes*' table along with the related entries from the connected tables.

# In[41]:

get_ipython().magic(u"sql DELETE FROM nodes WHERE nodes.id = '3026819436';")


# ___

# ## Data Exploration

# ### Basic exploration

# Below you may find some basic attributes of the dataset.

# #### Size of the database

# In[42]:

size_in_bytes = get_ipython().magic(u"sql SELECT pg_database_size('Project_3');")
print "DB size: " + str(size_in_bytes[0][0]/1024**2) + ' MB'


# #### Number of unique contributors

# In[43]:

get_ipython().run_cell_magic(u'sql', u'', u'SELECT count(DISTINCT(uid)) Unique_Contributors\nFROM (SELECT uid FROM nodes \n      UNION \n      SELECT uid FROM ways) AS elements;')


# #### Top 10 contributors (by number of entries)

# In[44]:

get_ipython().run_cell_magic(u'sql', u'', u'SELECT nodes_ways."user", COUNT(*) AS contributions\nFROM (SELECT "user" FROM nodes\n      UNION ALL\n      SELECT "user" FROM ways) AS nodes_ways\nGROUP BY nodes_ways."user"\nORDER BY contribution DESC\nLIMIT 10;')


# #### Number of nodes and ways

# In[45]:

n_nodes = get_ipython().magic(u'sql SELECT COUNT(*) FROM nodes')
n_ways = get_ipython().magic(u'sql SELECT COUNT(*) FROM ways')

print "Number of 'nodes: " + str(n_nodes[0][0])
print "Number of 'ways: " + str(n_ways[0][0])


# ### Deeper exploration

# #### Most popular streets

# In[46]:

get_ipython().run_cell_magic(u'sql', u'', u'SELECT street_names.value AS "Street", COUNT(street_names.value) AS "Times Refered"\nFROM\n\t(SELECT nodes_tags.value\n\tFROM nodes_tags\n\tWHERE type = \'addr\' AND key = \'street\'\n\tUNION ALL\n\tSELECT ways_tags.value\n\tFROM ways_tags\n\tWHERE \ttype = \'addr\' AND key = \'street\'\n\t\tOR\n\t\tid in\n\t\t\t(SELECT id\n\t\t\tFROM ways_tags\n\t\t\tWHERE key = \'highway\')\n\tAND key = \'name\') AS street_names\nGROUP BY street_names.value\nORDER BY "Times Refered" DESC\nLIMIT 10')


# #### Most frequent amenities

# Anyone who has lived in Singapore knows the love of Singaporeans for food. No surprises here; restaurants are, by far, on the top of the results.

# In[47]:

get_ipython().run_cell_magic(u'sql', u'', u'SELECT value AS "Amenity", COUNT(value) AS "Occurrences"\nFROM\t(SELECT *\n\tFROM nodes_tags\n\tUNION ALL\n\tSELECT *\n\tFROM nodes_tags) as tags\nWHERE key = \'amenity\'\nGROUP BY value\nORDER BY "Occurrences" DESC\nLIMIT 10')


# #### Most popular cuisine

# In[48]:

get_ipython().run_cell_magic(u'sql', u'', u'SELECT value AS "Cuisine", COUNT(*) AS "Restaurants" \nFROM (SELECT * FROM nodes_tags \n      UNION ALL \n      SELECT * FROM ways_tags) tags\nWHERE tags.key=\'cuisine\'\nGROUP BY value\nORDER BY "Restaurants"  DESC\nLIMIT 10')


# #### ATMs

# In[49]:

get_ipython().run_cell_magic(u'sql', u'', u'SELECT value AS "Bank", COUNT(value) AS "ATMs"\nFROM nodes_tags\nWHERE id in\n    (SELECT id\n    FROM nodes_tags\n    WHERE value = \'atm\')\n    AND\n    key = \'operator\'\nGROUP BY value\nORDER BY "ATMs" DESC')


# There are different abbreviations of bank names and some records that are not banks.

# In[50]:

get_ipython().run_cell_magic(u'sql', u'', u"UPDATE nodes_tags\nSET value = 'POSB'\nWHERE value = 'Posb';\n\nUPDATE nodes_tags\nSET value = 'UOB'\nWHERE value = 'Uob';\n\nUPDATE nodes_tags\nSET value = 'OCBC'\nWHERE value = 'Overseas Chinese Banking Corporation';")


# In[51]:

get_ipython().run_cell_magic(u'sql', u'', u"DELETE FROM nodes\nWHERE id IN\n\t(SELECT id\n\tFROM nodes_tags\n\tWHERE key = 'operator'\n\tAND (value = 'singapore room home'\n\tOR\n\tvalue = 'home'))")


# #### Religion

# Singapore is well-known for its multicultural environment. People with different religious and ethnic heritages are forming the modern city-state. This is reflected in the variety of temples that can be found in the country.

# In[52]:

get_ipython().run_cell_magic(u'sql', u'', u'SELECT tags.value AS "Religion", COUNT(*) AS "Temples" \nFROM (SELECT * FROM nodes_tags\n      UNION ALL \n      SELECT * FROM ways_tags) tags\nWHERE tags.key=\'religion\'\nGROUP BY tags.value\nORDER BY "Temples" DESC;')


# ___

# ## Ideas for additional improvements.

# There are two areas where the current project can be improved in the future.
# The first one is on the completeness of the data. All the above analysis is based on a dataset that reflects a big part of Singapore but not the whole country. The reason for this is the lack of a way to download a dataset for the entire Singapore without including parts of the neighboring countries. The analyst has to either select a part of the island/country or select a wider area that includes parts of Malaysia and Indonesia. Also, because of relations between nodes, ways, and relations, the downloaded data expand much further than the actual selection. Below you can see a plotting of the coordinates of the nodes of a dataset from a tight selection of Singapore. You can notice that huge parts of nearby countries were selected.

# ![initial selection](Resources/initial_selection.png)

# As a future improvement, I would download a wider selection or the metro extract from MapZan (https://mapzen.com/data/metro-extracts/metro/singapore/) and filter the non-Singaporean nodes and their references. The initial filtering could take place by introducing some latitude/longitude limits in the code to sort out most of the "non-SG" nodes.

# ![filter to square](Resources/filter_to_square.png)

# Then, I would download a shapefile for Singapore (e.g. http://www.diva-gis.org/gdata) use a GIS library like Fiona (https://pypi.python.org/pypi/Fiona) to create a polygon and finally with a geometric library like Shapely (https://github.com/Toblerity/Shapely) and compare all the nodes' coordinate against this polygon. Finally, I would clean all the ways and relations from the "non-sg" nodes and remove these that would become childless to conclude with a dataset of all (and only) Singapore.

# ![After GIS](Resources/after_gis.png)

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
