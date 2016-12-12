
# Wrangling OpenStreetMap Data

___

## About the project

### Scope

OpenStreetMap (OSM) is a collaborative project to create a free editable map of the world. The creation and growth of OSM have been motivated by restrictions on use or availability of map information across much of the world, and the advent of inexpensive portable satellite navigation devices.  


On the specific project, I am using data from https://www.openstreetmap.org and data mungling techniques, to assess the quality of their validity, accuracy, completeness, consistency and uniformity.  
The dataset I am using describes the center of Singapore, covering an area from Clementi on the west, to Bedok on the east and from Serangoon on the north, to Sentosa Island on the south.  
The biggest part of the wrangling takes place programmatically using Python and then the dataset is entered into a PostgreSQL database for further examination of any remaining elements that need attention. Finally, I perform some basic exploration and express some ideas for additional improvements.

### Skills demonstrated

* Assessment of the quality of data for validity, accuracy, completeness, consistency and uniformity.
* Parsing and gathering data from popular file formats such as .xml and .csv.
* Processing data from very large files that cannot be cleaned with spreadsheet programs.
* Storing, querying, and aggregating data using SQL.

### The Dataset

OpenStreetMap's data are structured in well-formed XML documents (.osm files) that consist of the following elements:
* **Nodes**: "Nodes" are individual dots used to mark specific locations (such as a postal box). Two or more nodes are used to draw line segments or "ways".
* **Ways**: A "way" is a line of nodes, displayed as connected line segments. "Ways" are used to create roads, paths, rivers, etc.  
* **Relations**: When "ways" or areas are linked in some way but do not represent the same physical thing, a "relation" is used to describe the larger entity they are part of. "Relations" are used to create map features, such as cycling routes, turn restrictions, and areas that are not contiguous. The multiple segments of a long way, such as an interstate or a state highway are grouped into a "relation" for that highway. Another example is a national park with several locations that are separated from each other. Those are also grouped into a "relation".

All these elements can carry tags describing the name, type of road, and other attributes. 

For the particular project, I am using a custom .osm file for the center of Singapore which I exported by using the overpass API. The  dataset has a volume of 96 MB and can be downloaded from the following link:
http://overpass-api.de/api/map?bbox=103.7651,1.2369,103.9310,1.3539  

___

## Data Preparation

### Imports and Definitions


```python
%matplotlib inline

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
```


```python
#OSM downloaded from openstreetmap
SG_OSM = 'Resources/map.osm'
#The following .csv files will be used for data extraction from the XML.
NODES_PATH = "nodes.csv"
NODE_TAGS_PATH = "nodes_tags.csv"
WAYS_PATH = "ways.csv"
WAY_NODES_PATH = "ways_nodes.csv"
WAY_TAGS_PATH = "ways_tags.csv"
```


```python
#Regular expressions
PROBLEMCHARS = re.compile(r'[=\+/&<>;\'\"\?%#$@\,\.\t\r\n]')
```


```python
#A list to save elements need further attention
PROBLEMATICS = []
```

### Parsing the Data

The size of the dataset allows me to parse it to memory to speed up the processing.  
In the case of a significant bigger XML, I would have to use the *iterparse()* function instead.  
(https://docs.python.org/2/library/xml.etree.elementtree.html#xml.etree.ElementTree.iterparse)


```python
tree = ET.parse(SG_OSM)
root = tree.getroot()
```

___

## Data Assesment

An initial exploration of the dataset revealed the following problems:  
* Incomplete or over-abbreviated street names
* Incomplete or incorrect postcodes
* Multi-abbreviated amenities names

The problematic elements that can be solved programmatically will be addressed during the wrangling process using code; the rest will be added to the database, and they will be marked (by adding them to the "*PROBLEMATICS*" list) for further assessment while in the database.

### Auditing Street Types

To audit the street names I should extract them from the XML. The street names appear in two forms in the dataset:
* In *Node* and *Way* elements, in the form of: "< tag k="addr:street" v="**street_name**"/>"
* in some *Way* elements that have the "< tag k="highway" ..../>", and the '*v*' attribute is one of ['living_street', 'motorway', 'primary', 'residential', 'secondary', 'tertiary'], as "< tag k="name" v="**street_name**"/>


```python
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
```


```python
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
```


```python
street_names = get_street_names(root)
```


```python
#Sample of the dictionary
pprint.pprint(dict(street_names.items()[0:10]))
```

    {'172814272': 'Tanjong Pagar Road',
     '172814274': 'Duxton Hill',
     '172814276': 'Blair Road',
     '172814279': 'Craig Road',
     '312190492': 'primary_link',
     '44352821': 'Dunman Road',
     '44352823': 'Dunman Road',
     '44352824': 'Dunman Lane',
     '71231228': 'Swiss Club Avenue',
     '9590561': 'Merchant Road'}


I am searching for multiple versions of the same street type. The different versions include different abbreviations, like Street/St, or different letter cases, like Avenue/avenue.

Although most os Singaporean street names end with the street type (e.g., "Serangoon Road" or "Arab Street") it is very common to end with a number instead (e.g. "Bedok North Avenue 1"). Thus, I am using the following regular expression that omits the last string if it contains a number.


```python
st_types_re = re.compile(r'[a-zA-Z]+[^0-9]\b\.?')
```

The result will be a dictionary with the format: *{street_type:(list_of_street_names)}*  
I am also adding not expected street names to the "*PROBLEMATICS*" list for further assessment.


```python
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
```


```python
streets = audit_st_types()
#Sample of the dictionary
pprint.pprint(dict(streets.items()[0:10]))
```

    {'Aenue': set(['Serangoon Aenue 1']),
     'Gr': set(['Eden Gr']),
     'Heights': set(['Hume Heights',
                     'Leedon Heights',
                     'Telok Blangah Heights',
                     'Watten Heights']),
     'Limau': set(['Jalan Kebun Limau', 'Lorong Limau']),
     'Melor': set(['Jalan Melor']),
     'Rendang': set(['Jalan Rendang']),
     'Selangat': set(['Lorong Selangat']),
     'Siglap': set(['Jalan Ulu Siglap', 'Lorong Siglap', 'Taman Siglap']),
     'Tenteram': set(['Jalan Tenteram']),
     'garden': set(['ah soo garden'])}


Using the *streets* dictionary, I can create a list of expected street types. It would be easy to manually populate the list with some profound values (like Street, Avenue, etc.), but guessing does not take into account any local peculiarity. Instead, I am searching the dataset for all the different street types, and count the number of occurrences of each one.


```python
def sort_street_types(street_types):
    '''Counts the number of appearances of each street type and sorts them.'''
    result = []
    for key, value in street_types.iteritems():
        result.append((key, len(value)))
        result = sorted(list(result), key=itemgetter(1), reverse=True)
    return result
```


```python
street_types = sort_street_types(streets)
#print a samle of the list
street_types[:15]
```




    [('Road', 574),
     ('Avenue', 145),
     ('Street', 139),
     ('Drive', 87),
     ('Lane', 80),
     ('Geylang', 42),
     ('Crescent', 42),
     ('Walk', 40),
     ('Park', 39),
     ('Close', 37),
     ('Link', 34),
     ('Terrace', 30),
     ('Ave', 29),
     ('Hill', 25),
     ('Flyover', 23)]



After the top 12 street types, abbreviations ("Ave") start to appear. The top 12 can be used to populate the *Expected* street types.


```python
def populate_expected(street_types, threshold):
    '''Populates the Expected list'''
    expected = []
    for i in street_types[:threshold]:
        expected.append(i[0])

    return expected
```


```python
EXPECTED = populate_expected(street_types, 12)
EXPECTED
```




    ['Road',
     'Avenue',
     'Street',
     'Drive',
     'Lane',
     'Geylang',
     'Crescent',
     'Walk',
     'Park',
     'Close',
     'Link',
     'Terrace']



Again, instead of guessing the possible abbreviations, I can use the "*get_close_matches()*" from the "*difflib*" module to find them.
(https://docs.python.org/2/library/difflib.html?highlight=get_close_matches)


```python
def find_abbreviations(expected, data):
    """Uses get_close_matces() to find similar text"""
    for i in expected:
        print i, get_close_matches(i, data, 4, 0.5)
```


```python
find_abbreviations(EXPECTED, list(streets.keys()))
```

    Road ['Road', 'road', 'Rd', 'Ria']
    Avenue ['Avenue', 'Aenue', 'Avebue', 'Ave']
    Street ['Street', 'street', 'See', 'Stangee']
    Drive ['Drive', 'Grove', 'Grisek', 'Bridge']
    Lane ['Lane', 'Lana', 'Lateh', 'Layang']
    Geylang ['Geylang', 'Pelangi', 'Selangat', 'Selanting']
    Crescent ['Crescent', 'Cresent', 'Cres', 'Green']
    Walk ['Walk', 'walk', 'Wajek', 'Wakaff']
    Park ['Park', 'park', 'Parkway', 'Paras']
    Close ['Close', 'Cross', 'Circle', 'Flyover']
    Link ['Link', 'link', 'Minyak', 'Bingka']
    Terrace ['Terrace', 'Terrance', 'Ter', 'service']


Now, I can map the different variations to the one it meant to be.


```python
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
```

Now, I can correct all the different abbreviations of street types.


```python
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
```


```python
update_street_type(root)
```

    Greenwood Ave ==> Greenwood Avenue (2 occurrences)
    Smith street ==> Smith Street
    Eunos Ave 7A ==> Eunos Avenue 7A
    Arumugam Rd ==> Arumugam Road (3 occurrences)
    Yarwood Ave ==> Yarwood Avenue (2 occurrences)
    Eunos Ave 6 ==> Eunos Avenue 6
    Eunos Ave 5 ==> Eunos Avenue 5
    Holland Grove Ter ==> Holland Grove Terrace
    Roseburn Ave ==> Roseburn Avenue
    Read Cresent ==> Read Crescent
    Sophia Rd ==> Sophia Road
    Bedok North road ==> Bedok North Road (4 occurrences)
    Nanson road ==> Nanson Road
    Chee Hoon Ave ==> Chee Hoon Avenue (2 occurrences)
    secondary_link ==> secondary_Link (66 occurrences)
    Serangoon Aenue 1 ==> Serangoon Avenue 1
    Hua Guan Ave ==> Hua Guan Avenue (3 occurrences)
    Elite Park Ave ==> Elite Park Avenue
    Malcolm Rd ==> Malcolm Road
    Eng Neo Ave ==> Eng Neo Avenue (2 occurrences)
    Bukit Timah Rd ==> Bukit Timah Road (2 occurrences)
    primary_link ==> primary_Link (246 occurrences)
    Stockport Rd ==> Stockport Road
    Greenmead Ave ==> Greenmead Avenue
    Ross Ave ==> Ross Avenue
    motorway_link ==> motorway_Link (442 occurrences)
    Tai Keng Ave ==> Tai Keng Avenue
    Upper Wilkie Rd ==> Upper Wilkie Road
    Bukit Batok East Ave 6 ==> Bukit Batok East Avenue 6 (2 occurrences)
    Clementi Ave 2 ==> Clementi Avenue 2 (3 occurrences)
    Clementi Ave 1 ==> Clementi Avenue 1
    First Hospital Ave ==> First Hospital Avenue
    Wareham Rd ==> Wareham Road
    Orchard Rd ==> Orchard Road
    31 Lower Kent Ridge Rd ==> 31 Lower Kent Ridge Road
    road ==> Road (8 occurrences)
    Towner Rd ==> Towner Road
    Greenleaf Ave ==> Greenleaf Avenue
    1013 Geylang East Ave 3 ==> 1013 Geylang East Avenue 3
    Lakme Terrance ==> Lakme Terrace
    Ubi Ave 1 ==> Ubi Avenue 1
    Daisy Ave ==> Daisy Avenue
    Bayfront Avebue ==> Bayfront Avenue
    tertiary_link ==> tertiary_Link (31 occurrences)
    Eunos Ave 5A ==> Eunos Avenue 5A
    Commonwealth Cresent ==> Commonwealth Crescent
    Pine walk ==> Pine Walk
    Elite Terrance ==> Elite Terrace
    Sian Tuan Ave ==> Sian Tuan Avenue
    Raeburn park ==> Raeburn Park
    trunk_link ==> trunk_Link (122 occurrences)
    Wilmonar Ave ==> Wilmonar Avenue
    Tai Thong Cresent ==> Tai Thong Crescent
    Parkstone Rd ==> Parkstone Road
    Kent Ridge Cresent ==> Kent Ridge Crescent (9 occurrences)
    Vanda Ave ==> Vanda Avenue
    Gloucester road ==> Gloucester Road (5 occurrences)
    Tanjong Pagar Rd ==> Tanjong Pagar Road
    Hougang Ave 3 ==> Hougang Avenue 3
    Hougang Ave 1 ==> Hougang Avenue 1
    Chempaka Ave ==> Chempaka Avenue
    Greendale Ave ==> Greendale Avenue


At this point, the street names are free of different abbreviations and spelling errors. The elements in the *PROBLEMATICS* list needs further attention, and they will be assessed in the database.

### Auditing Postcodes

Postcodes in Singapore consist of 6 digits with the first two, denoting the Postal Sector, take values between 01 and  80, excluding 74 (https://www.ura.gov.sg/realEstateIIWeb/resources/misc/list_of_postal_districts.htm).  
I am searching the dataset for this pattern, correcting whatever can be addressed automatically and adding the rest to the "*PROBLEMATICS*" for further examination.


```python
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
```


```python
fix_pcodes()
```

    Singapore 408564 ==> 408564
    S118556 ==> 118556
    S 278989 ==> 278989


___

## Importing Dataset to Database

After performing the most of the cleaning through Python, I can store the dataset in the database to examine the *PROBLEMATIC* elements and explore it further.  
I am using PostgreSQL to present a generic solution although a lightweight database like SGLite might be more appropriate.  
Initially, I am exporting the data in .csv files using the schema below, creating the tables and importing the .csvs.

### Exporting dataset to .CSVs


```python
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
```


```python
NODE_FIELDS = ['id', 'lat', 'lon', 'user', 'uid', 'version', 'changeset', 'timestamp']
NODE_TAGS_FIELDS = ['id', 'key', 'value', 'type']
WAY_FIELDS = ['id', 'user', 'uid', 'version', 'changeset', 'timestamp']
WAY_TAGS_FIELDS = ['id', 'key', 'value', 'type']
WAY_NODES_FIELDS = ['id', 'node_id', 'position']
```


```python
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
```


```python
def validate_element(element, validator, schema=SCHEMA):
    """Raise ValidationError if element does not match schema"""
    if validator.validate(element, schema) is not True:
        field, errors = next(validator.errors.iteritems())
        message_string = "\nElement of type '{0}' has the following errors:\n{1}"
        error_string = pprint.pformat(errors)

        raise Exception(message_string.format(field, error_string))
```


```python
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
```


```python
def process_map(file_in, validate):
    """Iteratively process each XML element and write to csv(s)"""

    with codecs.open(NODES_PATH, 'w') as nodes_file, \
         codecs.open(NODE_TAGS_PATH, 'w') as nodes_tags_file, \
         codecs.open(WAYS_PATH, 'w') as ways_file, \
         codecs.open(WAY_NODES_PATH, 'w') as way_nodes_file, \
         codecs.open(WAY_TAGS_PATH, 'w') as way_tags_file:

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
```


```python
process_map(SG_OSM, validate=True)
```

### Connection to the database

For connection between Jupyter Notebook and PostgreSQL, I am using *ipython-sql* (https://github.com/catherinedevlin/ipython-sql)


```python
"""Loading the ipython-sql module"""
%load_ext sql

"""Disabling the printing of number of rows affected by each query"""
%config SqlMagic.feedback=False

"""Connecting to the database"""
%sql postgresql://jupyter_user:notebook@192.168.100.2/Project_3
```




    u'Connected: jupyter_user@Project_3'



### Creation of the Tables

I am using *DELETE CASCADE* on the tables with foreign keys to ensure the drop of tags along with the related elements.


```python
%%sql
CREATE TABLE public.nodes
(
  id bigint NOT NULL,
  lat real,
  lon real,
  "user" text,
  uid integer,
  version integer,
  changeset integer,
  "timestamp" text,
  CONSTRAINT nodes_pkey PRIMARY KEY (id)
);

CREATE TABLE public.nodes_tags
(
  id bigint,
  key text,
  value text,
  type text,
  CONSTRAINT nodes_tags_id_fkey FOREIGN KEY (id)
      REFERENCES public.nodes (id) MATCH SIMPLE
      ON UPDATE NO ACTION ON DELETE CASCADE
);

CREATE TABLE public.ways
(
  id bigint NOT NULL,
  "user" text,
  uid integer,
  version text,
  changeset integer,
  "timestamp" text,
  CONSTRAINT ways_pkey PRIMARY KEY (id)
);

CREATE TABLE public.ways_nodes
(
  id bigint NOT NULL,
  node_id bigint NOT NULL,
  "position" integer NOT NULL,
  CONSTRAINT ways_nodes_id_fkey FOREIGN KEY (id)
      REFERENCES public.ways (id) MATCH SIMPLE
      ON UPDATE NO ACTION ON DELETE NO ACTION,
  CONSTRAINT ways_nodes_node_id_fkey FOREIGN KEY (node_id)
      REFERENCES public.nodes (id) MATCH SIMPLE
      ON UPDATE NO ACTION ON DELETE CASCADE
);

CREATE TABLE public.ways_tags
(
  id bigint NOT NULL,
  key text NOT NULL,
  value text NOT NULL,
  type text,
  CONSTRAINT ways_tags_id_fkey FOREIGN KEY (id)
      REFERENCES public.ways (id) MATCH SIMPLE
      ON UPDATE NO ACTION ON DELETE CASCADE
);
```




    []



### Importing the data


```python
%%sql
COPY public.nodes
FROM '/home/yannis/ownCloud/Udacity/Data_Science/Projects/Project_3/nodes.csv'
DELIMITER ','
ENCODING 'utf8'
CSV HEADER;

COPY public.nodes_tags
FROM '/home/yannis/ownCloud/Udacity/Data_Science/Projects/Project_3/nodes_tags.csv'
DELIMITER ','
ENCODING 'utf8'
CSV HEADER;

COPY public.ways
FROM '/home/yannis/ownCloud/Udacity/Data_Science/Projects/Project_3/ways.csv'
DELIMITER ','
ENCODING 'utf8'
CSV HEADER;

COPY public.ways_nodes
FROM '/home/yannis/ownCloud/Udacity/Data_Science/Projects/Project_3/ways_nodes.csv'
DELIMITER ','
ENCODING 'utf8'
CSV HEADER;

COPY public.ways_tags
FROM '/home/yannis/ownCloud/Udacity/Data_Science/Projects/Project_3/ways_tags.csv'
DELIMITER ','
ENCODING 'utf8'
CSV HEADER;
```




    []



___

## Data assesment in the database

Now it is time assess the *PROBLEMATIC* elements.  
There are 5 elements with wrong **street name** and 8 elements with wrong **postcode**.


```python
pprint.pprint(PROBLEMATICS)
```

    [('453243296', 'street name', '2'),
     ('46649997', 'street name', u'\u516c\u53f865'),
     ('453253763', 'street name', '2'),
     ('453227146', 'street name', u'\u516c\u53f865'),
     ('169844052', 'street name', '310074'),
     ('1318498347', 'postcode', '135'),
     ('3026819436', 'postcode', '2424'),
     ('3756813987', 'postcode', '05901'),
     ('4338649392', 'postcode', '88752'),
     ('4496749591', 'postcode', '#B1-42'),
     ('23946435', 'postcode', '437 437'),
     ('169844052', 'postcode', '74'),
     ('172769494', 'postcode', '05901')]


The strategy I am following is to export the coordinates of each element and run reverse geocoding queries to get their addresses. Particularly for the way elements, since they are arrays of nodes, I am getting the addresses of all related nodes, and selecting the one with the most occurrences.  
For the reverse geocoding I am using *Google map's* geocoder because OpenStreetMap's (*Nominatim*) may return the same errors.


```python
def element_type(element_id):
    """From the element's id, returns the element's type.
    (I need to know the element's type, to run the appropriate query.)"""
    path = str('./*[@id="' + str(element_id) + '"]')

    return root.find(path).tag
```


```python
def element_coordinates(element_id):
    """Return the coordinates of an element from its id"""
    el_type = element_type(element_id)
    if el_type == 'node':
        coordinates = %sql SELECT lat, lon FROM nodes WHERE nodes.id = $element_id
    elif el_type == 'way':
        coordinates = %sql SELECT lat, lon FROM nodes, ways_nodes WHERE nodes.id = ways_nodes.node_id and ways_nodes.id = $element_id
    else:
        print "Wrong element type"
    return coordinates
```


```python
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
```


```python
pprint.pprint(element_info(PROBLEMATICS))
```

    {('1318498347', 'postcode', '135'): ((u'143-145 Taman Permata, Singapore', 1),
                                         'node'),
     ('169844052', 'postcode', '74'): ((u'74 Lor 4 Toa Payoh, Block 74, Singapore 310074',
                                        3),
                                       'way'),
     ('169844052', 'street name', '310074'): ((u'74 Lor 4 Toa Payoh, Block 74, Singapore 310074',
                                               3),
                                              'way'),
     ('172769494', 'postcode', '05901'): ((u'281 South Bridge Rd, Singapore', 2),
                                          'way'),
     ('23946435', 'postcode', '437 437'): ((u'MCE, Singapore', 19), 'way'),
     ('3026819436', 'postcode', '2424'): ((u'150 Orchard Rd, Singapore 238841',
                                           1),
                                          'node'),
     ('3756813987', 'postcode', '05901'): ((u'288 South Bridge Rd, Buddha Tooth Relic Temple and Museum, Singapore 058840',
                                            1),
                                           'node'),
     ('4338649392', 'postcode', '88752'): ((u'285 New Bridge Rd, Singapore 088755',
                                            1),
                                           'node'),
     ('4496749591', 'postcode', '#B1-42'): ((u'170 Upper Bukit Timah Rd, Singapore 588179',
                                             1),
                                            'node'),
     ('453227146', 'street name', u'\u516c\u53f865'): ((u'63 Alexandra Terrace, Singapore 119937',
                                                        8),
                                                       'way'),
     ('453243296', 'street name', '2'): ((u'73 Belimbing Ave, Singapore 349933',
                                          2),
                                         'way'),
     ('453253763', 'street name', '2'): ((u'44 Lichi Ave, Singapore 348818', 2),
                                         'way'),
     ('46649997', 'street name', u'\u516c\u53f865'): ((u'61 Alexandra Terrace, Singapore 119936',
                                                       10),
                                                      'way')}


9 of the problemating elements resolved by the reverse geocoding. I'm updating their values.


```python
%%sql
UPDATE ways_tags
SET value = '310074'
WHERE ways_tags.id = '169844052' AND ways_tags.type = 'addr' AND ways_tags.key = 'postcode';

UPDATE ways_tags
SET value = 'Toa Payoh'
WHERE ways_tags.id = '169844052' AND ways_tags.type = 'addr' AND ways_tags.key = 'street';

UPDATE nodes_tags
SET value = '058840'
WHERE nodes_tags.id = '3756813987' AND nodes_tags.type = 'addr' AND nodes_tags.key = 'postcode';

UPDATE nodes_tags
SET value = '088755'
WHERE nodes_tags.id = '4338649392' AND nodes_tags.type = 'addr' AND nodes_tags.key = 'postcode';

UPDATE nodes_tags
SET value = '588179'
WHERE nodes_tags.id = '4496749591' AND nodes_tags.type = 'addr' AND nodes_tags.key = 'postcode';

UPDATE ways_tags
SET value = 'Alexandra Terrace'
WHERE ways_tags.id = '453227146' AND ways_tags.type = 'addr' AND ways_tags.key = 'street';

UPDATE ways_tags
SET value = 'Belimbing Avenue'
WHERE ways_tags.id = '453243296' AND ways_tags.type = 'addr' AND ways_tags.key = 'street';

UPDATE ways_tags
SET value = 'Lichi Avenue'
WHERE ways_tags.id = '453253763' AND ways_tags.type = 'addr' AND ways_tags.key = 'street';

UPDATE ways_tags
SET value = 'Alexandra Terrace'
WHERE ways_tags.id = '46649997' AND ways_tags.type = 'addr' AND ways_tags.key = 'street';
```




    []



For 3 elements I had to search the returned address on the web for getting the right postcode.


```python
%%sql
UPDATE nodes_tags
SET value = '575268'
WHERE nodes_tags.id = '1318498347' AND nodes_tags.type = 'addr' AND nodes_tags.key = 'postcode';

UPDATE ways_tags
SET value = '058830'
WHERE ways_tags.id = '172769494' AND ways_tags.type = 'addr' AND ways_tags.key = 'postcode';

UPDATE ways_tags
SET value = '058830'
WHERE ways_tags.id = '23946435' AND ways_tags.type = 'addr' AND ways_tags.key = 'postcode';
```




    []



Finally, for one of the element, I could not find a valid postcode. The specific node (3026819436) represents a medical equipment company named Liana Medic LTD. On their *contact* page there are both errors in the street name ("Ochard" instead of "Orchard") and invalid postcode ("2424", the same as the dataset)  (http://www.lianamedic.com/contact-us). I decided to remove the specific node from the '*nodes*' table along with the related entries from the connected tables.


```python
%sql DELETE FROM nodes WHERE nodes.id = '3026819436';
```




    []



___

## Data Exploration

### Basic exploration

Below you may find some basic attributes of the dataset.

#### Size of the database


```python
size_in_bytes = %sql SELECT pg_database_size('Project_3');
print "DB size: " + str(size_in_bytes[0][0]/1024**2) + ' MB'
```

    DB size: 96 MB


#### Number of unique contributors


```python
%%sql
SELECT count(DISTINCT(uid)) Unique_Contributors
FROM (SELECT uid FROM nodes 
      UNION 
      SELECT uid FROM ways) AS elements;
```




<table>
    <tr>
        <th>unique_contributors</th>
    </tr>
    <tr>
        <td>849</td>
    </tr>
</table>



#### Top 10 contributors (by number of entries)


```python
%%sql
SELECT nodes_ways."user", COUNT(*) AS contributions
FROM (SELECT "user" FROM nodes
      UNION ALL
      SELECT "user" FROM ways) AS nodes_ways
GROUP BY nodes_ways."user"
ORDER BY contribution DESC
LIMIT 10;
```

    (psycopg2.ProgrammingError) column "contribution" does not exist
    LINE 6: ORDER BY contribution DESC
                     ^
     [SQL: 'SELECT nodes_ways."user", COUNT(*) AS contributions\nFROM (SELECT "user" FROM nodes\n      UNION ALL\n      SELECT "user" FROM ways) AS nodes_ways\nGROUP BY nodes_ways."user"\nORDER BY contribution DESC\nLIMIT 10;']


#### Number of nodes and ways


```python
n_nodes = %sql SELECT COUNT(*) FROM nodes
n_ways = %sql SELECT COUNT(*) FROM ways

print "Number of 'nodes: " + str(n_nodes[0][0])
print "Number of 'ways: " + str(n_ways[0][0])
```

    Number of 'nodes: 409352
    Number of 'ways: 66404


### Deeper exploration

#### Most popular streets


```python
%%sql
SELECT street_names.value AS "Street", COUNT(street_names.value) AS "Times Refered"
FROM
	(SELECT nodes_tags.value
	FROM nodes_tags
	WHERE type = 'addr' AND key = 'street'
	UNION ALL
	SELECT ways_tags.value
	FROM ways_tags
	WHERE 	type = 'addr' AND key = 'street'
		OR
		id in
			(SELECT id
			FROM ways_tags
			WHERE key = 'highway')
	AND key = 'name') AS street_names
GROUP BY street_names.value
ORDER BY "Times Refered" DESC
LIMIT 10
```




<table>
    <tr>
        <th>Street</th>
        <th>Times Refered</th>
    </tr>
    <tr>
        <td>Jalan Senang</td>
        <td>229</td>
    </tr>
    <tr>
        <td>Joo Chiat Road</td>
        <td>204</td>
    </tr>
    <tr>
        <td>Bedok Reservoir Road</td>
        <td>185</td>
    </tr>
    <tr>
        <td>Tanjong Pagar Road</td>
        <td>166</td>
    </tr>
    <tr>
        <td>South Bridge Road</td>
        <td>165</td>
    </tr>
    <tr>
        <td>Serangoon Road</td>
        <td>164</td>
    </tr>
    <tr>
        <td>North Bridge Road</td>
        <td>135</td>
    </tr>
    <tr>
        <td>Seah Street</td>
        <td>134</td>
    </tr>
    <tr>
        <td>Neil Road</td>
        <td>133</td>
    </tr>
    <tr>
        <td>Dunlop Street</td>
        <td>128</td>
    </tr>
</table>



#### Most frequent amenities

Anyone who has lived in Singapore knows the love of Singaporeans for food. No surprises here; restaurants are, by far, on the top of the results.


```python
%%sql
SELECT value AS "Amenity", COUNT(value) AS "Occurrences"
FROM	(SELECT *
	FROM nodes_tags
	UNION ALL
	SELECT *
	FROM nodes_tags) as tags
WHERE key = 'amenity'
GROUP BY value
ORDER BY "Occurrences" DESC
LIMIT 10
```




<table>
    <tr>
        <th>Amenity</th>
        <th>Occurrences</th>
    </tr>
    <tr>
        <td>restaurant</td>
        <td>1562</td>
    </tr>
    <tr>
        <td>parking</td>
        <td>654</td>
    </tr>
    <tr>
        <td>taxi</td>
        <td>524</td>
    </tr>
    <tr>
        <td>cafe</td>
        <td>396</td>
    </tr>
    <tr>
        <td>fast_food</td>
        <td>252</td>
    </tr>
    <tr>
        <td>atm</td>
        <td>194</td>
    </tr>
    <tr>
        <td>toilets</td>
        <td>190</td>
    </tr>
    <tr>
        <td>bar</td>
        <td>176</td>
    </tr>
    <tr>
        <td>bank</td>
        <td>120</td>
    </tr>
    <tr>
        <td>police</td>
        <td>120</td>
    </tr>
</table>



#### Most popular cuisine


```python
%%sql
SELECT value AS "Cuisine", COUNT(*) AS "Restaurants" 
FROM (SELECT * FROM nodes_tags 
      UNION ALL 
      SELECT * FROM ways_tags) tags
WHERE tags.key='cuisine'
GROUP BY value
ORDER BY "Restaurants"  DESC
LIMIT 10
```




<table>
    <tr>
        <th>Cuisine</th>
        <th>Restaurants</th>
    </tr>
    <tr>
        <td>chinese</td>
        <td>99</td>
    </tr>
    <tr>
        <td>japanese</td>
        <td>42</td>
    </tr>
    <tr>
        <td>korean</td>
        <td>36</td>
    </tr>
    <tr>
        <td>coffee_shop</td>
        <td>34</td>
    </tr>
    <tr>
        <td>burger</td>
        <td>33</td>
    </tr>
    <tr>
        <td>italian</td>
        <td>32</td>
    </tr>
    <tr>
        <td>indian</td>
        <td>28</td>
    </tr>
    <tr>
        <td>asian</td>
        <td>27</td>
    </tr>
    <tr>
        <td>pizza</td>
        <td>17</td>
    </tr>
    <tr>
        <td>french</td>
        <td>15</td>
    </tr>
</table>



#### ATMs


```python
%%sql
SELECT value AS "Bank", COUNT(value) AS "ATMs"
FROM nodes_tags
WHERE id in
    (SELECT id
    FROM nodes_tags
    WHERE value = 'atm')
    AND
    key = 'operator'
GROUP BY value
ORDER BY "ATMs" DESC
```




<table>
    <tr>
        <th>Bank</th>
        <th>ATMs</th>
    </tr>
    <tr>
        <td>POSB</td>
        <td>18</td>
    </tr>
    <tr>
        <td>UOB</td>
        <td>12</td>
    </tr>
    <tr>
        <td>OCBC</td>
        <td>9</td>
    </tr>
    <tr>
        <td>Citibank</td>
        <td>8</td>
    </tr>
    <tr>
        <td>DBS</td>
        <td>7</td>
    </tr>
    <tr>
        <td>singapore room home</td>
        <td>1</td>
    </tr>
    <tr>
        <td>Quantified Assets, Pte. Ltd.</td>
        <td>1</td>
    </tr>
    <tr>
        <td>Posb</td>
        <td>1</td>
    </tr>
    <tr>
        <td>HSBC</td>
        <td>1</td>
    </tr>
    <tr>
        <td>Uob</td>
        <td>1</td>
    </tr>
    <tr>
        <td>DSS</td>
        <td>1</td>
    </tr>
    <tr>
        <td>Overseas Chinese Banking Corporation</td>
        <td>1</td>
    </tr>
    <tr>
        <td>DBS / UOB</td>
        <td>1</td>
    </tr>
    <tr>
        <td>DBS/POSB</td>
        <td>1</td>
    </tr>
    <tr>
        <td>home</td>
        <td>1</td>
    </tr>
    <tr>
        <td>Standard Chartered Bank</td>
        <td>1</td>
    </tr>
</table>



There are different abbreviations of bank names and some records that are not banks.


```python
%%sql
UPDATE nodes_tags
SET value = 'POSB'
WHERE value = 'Posb';

UPDATE nodes_tags
SET value = 'UOB'
WHERE value = 'Uob';

UPDATE nodes_tags
SET value = 'OCBC'
WHERE value = 'Overseas Chinese Banking Corporation';
```




    []




```python
%%sql
DELETE FROM nodes
WHERE id IN
	(SELECT id
	FROM nodes_tags
	WHERE key = 'operator'
	AND (value = 'singapore room home'
	OR
	value = 'home'))
```




    []



#### Religion

Singapore is well-known for its multicultural environment. People with different religious and ethnic heritages are forming the modern city-state. This is reflected in the variety of temples that can be found in the country.


```python
%%sql
SELECT tags.value AS "Religion", COUNT(*) AS "Temples" 
FROM (SELECT * FROM nodes_tags
      UNION ALL 
      SELECT * FROM ways_tags) tags
WHERE tags.key='religion'
GROUP BY tags.value
ORDER BY "Temples" DESC;
```




<table>
    <tr>
        <th>Religion</th>
        <th>Temples</th>
    </tr>
    <tr>
        <td>christian</td>
        <td>73</td>
    </tr>
    <tr>
        <td>muslim</td>
        <td>38</td>
    </tr>
    <tr>
        <td>buddhist</td>
        <td>30</td>
    </tr>
    <tr>
        <td>hindu</td>
        <td>9</td>
    </tr>
    <tr>
        <td>taoist</td>
        <td>6</td>
    </tr>
    <tr>
        <td>jewish</td>
        <td>1</td>
    </tr>
    <tr>
        <td>sikh</td>
        <td>1</td>
    </tr>
</table>



___

## Ideas for additional improvements.

There are two areas where the current project can be improved in the future.
The first one is on the completeness of the data. All the above analysis is based on a dataset that reflects a big part of Singapore but not the whole country. The reason for this is the lack of a way to download a dataset for the entire Singapore without including parts of the neighboring countries. The analyst has to either select a part of the island/country or select a wider area that includes parts of Malaysia and Indonesia. Also, because of relations between nodes, ways, and relations, the downloaded data expand much further than the actual selection. Below you can see a plotting of the coordinates of the nodes of a dataset from a tight selection of Singapore. You can notice that huge parts of nearby countries were selected.

![initial selection](Resources/initial_selection.png)

As a future improvement, I would download a wider selection or the metro extract from MapZan (https://mapzen.com/data/metro-extracts/metro/singapore/) and filter the non-Singaporean nodes and their references. The initial filtering could take place by introducing some latitude/longitude limits in the code to sort out most of the "non-SG" nodes.

![filter to square](Resources/filter_to_square.png)

Then, I would download a shapefile for Singapore (e.g. http://www.diva-gis.org/gdata) use a GIS library like Fiona (https://pypi.python.org/pypi/Fiona) to create a polygon and finally with a geometric library like Shapely (https://github.com/Toblerity/Shapely) and compare all the nodes' coordinate against this polygon. Finally, I would clean all the ways and relations from the "non-sg" nodes and remove these that would become childless to conclude with a dataset of all (and only) Singapore.

![After GIS](Resources/after_gis.png)

The drawback of the above technic is that the comparison of each node against the polygon is a very time-consuming procedure with my initial tests taking 17-18 hours to produce a result. This is the reason the above approach left as a future improvement probably along with the use of multithreading technics to speed up the process.

The second area with room for future improvement is the exploratory analysis of the dataset.  Just to mention some of the explorings that could take place:
* Distribution of commits per contributor.
* Plotting of element creation per type, per day.
* Distribution of distance between different types of amenities
* Popular franchises in the country (fast food, conventional stores, etc.)
* Selection of a bank based on the average distance you have to walk for an ATM.
* Which area has the biggest parks and recreation spaces.  

The scope of the current project was the wrangling of the dataset, so all the above have been left for future improvement.

___

## References



Udacity - https://www.udacity.com/  
Wikipedia - https://www.wikipedia.org/  
OpenStreetMap - https://www.openstreetmap.org  
Overpass API - http://overpass-api.de/  
Python Software Foundation - https://www.python.org/  
Urban Redevelopment Authority of Singapore - https://www.ura.gov.sg  
Catherine Devlin's Github repository - https://github.com/catherinedevlin/ipython-sql  
