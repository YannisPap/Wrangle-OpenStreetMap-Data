
# Wrangle-OpenStreetMap-Data

___

On the particular project, I am using data mungling techniques to assess the quality of OpenStreetMap’s (OSM) data for the center of Singapore regarding their consistency and uniformity.
The data wrangling takes place programmatically, using **Python** for the most of the process and **SQL** for items that need further attention while in the **PostgreSQL**.

The dataset describes the center of Singapore, covering an area from Clementi on the west, to
Bedok on the east and from Serangoon on the north, to Sentosa Island on the south. The size of the dataset is 96 MB and can can be downloaded from [here](http://overpass-api.de/api/map?bbox=103.7651,1.2369,103.9310,1.3539)

## About the project

### Scope

OpenStreetMap (OSM) is a collaborative project to create a free editable map of the world. The creation and growth of OSM have been motivated by restrictions on use or availability of map information across much of the world, and the advent of inexpensive portable satellite navigation devices.  


On the specific project, I am using data from https://www.openstreetmap.org and data mungling techniques, to assess the quality of their validity, accuracy, completeness, consistency and uniformity.  
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

For the particular project, I am using a custom .osm file for the center of Singapore which I exported by using the overpass API. The  dataset has a volume of 96 MB and can be downloaded from this [link](http://overpass-api.de/api/map?bbox=103.7651,1.2369,103.9310,1.3539)  

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
from geopy.exc import GeocoderTimedOut
```


```python
#OSM downloaded from openstreetmap
SG_OSM = '../Helper/Singapore.osm'
#The following .csv files will be used for data extraction from the XML.
NODES_PATH = "../Helper/nodes.csv"
NODE_TAGS_PATH = "../Helper/nodes_tags.csv"
WAYS_PATH = "../Helper/ways.csv"
WAY_NODES_PATH = "../Helper/ways_nodes.csv"
WAY_TAGS_PATH = "../Helper/ways_tags.csv"
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
In the case of a significant bigger XML, I would have to use the [iterparse()](https://docs.python.org/2/library/xml.etree.elementtree.html#xml.etree.ElementTree.iterparse) function instead.  


```python
tree = ET.parse(SG_OSM)
root = tree.getroot()
```

___

## Data Assessment

An initial exploration of the dataset revealed the following problems:  
- Abbreviations of street types like ‘Av’ instead of ‘Avenue’ and ‘Rd’ instead of ‘Road’.
- All lowercase letters like ‘street’ instead of ‘Street’.
- Postcodes including the first letter (S xxxxxx) or the whole name (Singapore xxxxxx) of the
country.
- Postcodes omitting the leading ‘0’ (probably because of declared as integers at some point
before their import to OpenStreetMap.)
- Multi-abbreviated amenity names.

The problems in the amenity names were to a small extent, and they were corrected directly in
the database, the rest resolved programmatically using Python on the biggest part and a subtle portion of them needed further assessment, resolven in the database.

### Auditing Street Types

To audit the street names I should extract them from the XML.  
The street names appear in two forms in the dataset:  
In *Node* and *Way* elements, in the form of: "*< tag k="addr:street" v="**street_name**"/>*"

```python
<node id="337171253" lat="1.3028023" lon="103.8599300" version="3" timestamp="2015-08-01T01:38:25Z" changeset="33022579" uid="741163" user="JaLooNz">
    <tag k="addr:city" v="Singapore"/>
    <tag k="addr:country" v="SG"/>
    <tag k="addr:housenumber" v="85"/>
    <tag k="addr:postcode" v="198501"/>
    <tag k="addr:street" v="Sultan Gate"/>
    <tag k="fax" v="+65 6299 4316"/>
    <tag k="name" v="Malay Heritage Centre"/>
    <tag k="phone" v="+65 6391 0450"/>
    <tag k="tourism" v="museum"/>
    <tag k="website" v="http://malayheritage.org.sg/"/>
</node>
```

In *Way* elements that have the "*< tag k="highway" ..../>*", and the '*v*' attribute is one of ['living_street', 'motorway', 'primary', 'residential', 'secondary', 'tertiary'], as "*< tag k="name" v="**street_name**"/>*".

```python
<way id="4386520" version="23" timestamp="2016-11-07T12:03:39Z" changeset="43462870" uid="2818856" user="CitymapperHQ">
    <nd ref="26778964"/>
    <nd ref="247749632"/>
    <nd ref="1275309736"/>
    <nd ref="1275309696"/>
    <nd ref="462263980"/>
    <nd ref="473019059"/>
    <nd ref="4486796339"/>
    <nd ref="1278204303"/>
    <nd ref="3689717007"/>
    <nd ref="246494174"/>
    <tag k="highway" v="primary"/>
    <tag k="name" v="Orchard Road"/>
    <tag k="oneway" v="yes"/>
</way>
```


```python
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
```


```python
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
```


```python
street_names = get_street_names(root)
```


```python
#Sample of the dictionary
pprint.pprint(dict(street_names.items()[:10]))
```

    {'173767759': 'Lornie Road',
     '178436854': 'Upper Weld Road',
     '201275515': 'Jalan Novena',
     '241208738': 'Race Course Road',
     '241208739': 'Race Course Road',
     '260092923': 'Jalan Novena Utara',
     '334112229': 'Joo Chiat Road',
     '388268000': 'Waringin Park',
     '46818743': 'Bukit Purmei Avenue',
     '9590561': 'Merchant Road'}


I am searching for multiple versions of the same street type. The different versions include different abbreviations, like Street/St, or different letter cases, like Avenue/avenue.

Although most of the Singaporean street names end with the street type (e.g., “Serangoon Road” or “Arab Street”) it is also common to end with a number instead (e.g. “Bedok North Avenue 1”).  
Thus, by using regular expressions, I extracted the last word that does not contain numbers from the street name.


```python
st_types_re = re.compile(r'[a-zA-Z]+[^0-9]\b\.?')
```

The result will be a dictionary with the format: *{street_type:(list_of_street_names)}*  
I am also adding not expected street names to the "*PROBLEMATICS*" list for further assessment.


```python
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
```


```python
streets = audit_st_types(street_names)
#Sample of the dictionary
pprint.pprint(dict(streets.items()[:7]))
```

    {'Fyover': set(['Ophir Fyover']),
     'Melor': set(['Jalan Melor']),
     'Pelatina': set(['Jln Pelatina']),
     'Riang': set(['Jalan Riang']),
     'Rise': set(['Ascot Rise',
                  'Binchang Rise',
                  'Binjai Rise',
                  'Cairnhill Rise',
                  'Canning Rise',
                  'Clover Rise',
                  'Dover Rise',
                  'Goldhill Rise',
                  'Greenleaf Rise',
                  'Holland Rise',
                  'Matlock Rise',
                  'Mount Sinai Rise',
                  'Novena Rise',
                  'Oxley Rise',
                  'Siglap Rise',
                  'Slim Barracks Rise',
                  'Telok Blangah Rise',
                  'Toa Payoh Rise',
                  'Watten Rise']),
     'Satu': set(['Jalan Satu', 'Lengkong Satu']),
     'Taman': set(['Jalan Taman'])}


It would be easy to populate the list of Common Street Types with some profound values like Street or Avenue, but guessing does not take into account any local peculiarity. Instead, I searched the dataset for all the different types and used the 12 with the most occurrences (From 13th position, abbreviations start to appear).


```python
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
```


```python
street_types = sort_street_types(streets)
#print a samle of the list
street_types[:15]
```




    [('Road', 576),
     ('Avenue', 145),
     ('Street', 139),
     ('Drive', 87),
     ('Lane', 79),
     ('Geylang', 42),
     ('Crescent', 42),
     ('Walk', 40),
     ('Park', 39),
     ('Close', 37),
     ('Link', 35),
     ('Terrace', 30),
     ('Ave', 29),
     ('Hill', 25),
     ('Place', 23)]




```python
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



To find the street names that need correction, I used the “*get_close_matches()*” function from the [difflib](https://docs.python.org/2/library/difflib.html?highlight=get_close_matches) module to find “close matches” of the 12 Common Street Types. This is what I found:


```python
def find_abbreviations(expected, data):
    """Uses get_close_matces() to find similar text
    
    Args:
        expected (list): A list of the expected street types.
        data (list): A list of all the different street types.
        
    Retturns: nothing
        
    """
    
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
    Link ['Link', 'Minyak', 'Bingka', 'Limu']
    Terrace ['Terrace', 'Terrance', 'Ter', 'Tenteram']


Now, I can map the different variations to the one it meant to be and correct all the different abbreviations of street types.


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
    'link': 'Link',
    'Cresent': 'Crescent',
    'Terrance': 'Terrace',
    'Ter': 'Terrace'
}
```


```python
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
```


```python
update_street_type.called = False
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
    Bukit Batok East Ave 6 ==> Bukit Batok East Avenue 6 (2 occurrences)
    Roseburn Ave ==> Roseburn Avenue
    Read Cresent ==> Read Crescent
    Sophia Rd ==> Sophia Road
    Bedok North road ==> Bedok North Road (4 occurrences)
    Chee Hoon Ave ==> Chee Hoon Avenue (2 occurrences)
    Holland Grove Ter ==> Holland Grove Terrace
    Serangoon Aenue 1 ==> Serangoon Avenue 1
    Hua Guan Ave ==> Hua Guan Avenue (3 occurrences)
    Elite Park Ave ==> Elite Park Avenue
    Malcolm Rd ==> Malcolm Road
    Eng Neo Ave ==> Eng Neo Avenue (2 occurrences)
    Bukit Timah Rd ==> Bukit Timah Road (2 occurrences)
    Stockport Rd ==> Stockport Road
    Greenmead Ave ==> Greenmead Avenue
    Ross Ave ==> Ross Avenue
    Nanson road ==> Nanson Road
    Raeburn park ==> Raeburn Park
    Upper Wilkie Rd ==> Upper Wilkie Road
    Tai Thong Cresent ==> Tai Thong Crescent
    Clementi Ave 2 ==> Clementi Avenue 2 (3 occurrences)
    Clementi Ave 1 ==> Clementi Avenue 1
    First Hospital Ave ==> First Hospital Avenue
    Wareham Rd ==> Wareham Road
    31 Lower Kent Ridge Rd ==> 31 Lower Kent Ridge Road
    Towner Rd ==> Towner Road
    Greenleaf Ave ==> Greenleaf Avenue
    1013 Geylang East Ave 3 ==> 1013 Geylang East Avenue 3
    Lakme Terrance ==> Lakme Terrace
    Ubi Ave 1 ==> Ubi Avenue 1
    Daisy Ave ==> Daisy Avenue
    Bayfront Avebue ==> Bayfront Avenue
    Eunos Ave 5A ==> Eunos Avenue 5A
    Commonwealth Cresent ==> Commonwealth Crescent
    Pine walk ==> Pine Walk
    Elite Terrance ==> Elite Terrace
    Sian Tuan Ave ==> Sian Tuan Avenue
    Tai Keng Ave ==> Tai Keng Avenue
    Orchard Rd ==> Orchard Road
    Wilmonar Ave ==> Wilmonar Avenue
    Parkstone Rd ==> Parkstone Road
    Kent Ridge Cresent ==> Kent Ridge Crescent (9 occurrences)
    Vanda Ave ==> Vanda Avenue
    Gloucester road ==> Gloucester Road (5 occurrences)
    Tanjong Pagar Rd ==> Tanjong Pagar Road
    Hougang Ave 3 ==> Hougang Avenue 3
    Hougang Ave 1 ==> Hougang Avenue 1
    Chempaka Ave ==> Chempaka Avenue
    Greendale Ave ==> Greendale Avenue
    83 street names were fixed


### Auditing Postcodes

Postcodes in Singapore consist of 6 digits with the first two, denoting the Postal Sector, take values between 01 and  80, excluding 74 (https://www.ura.gov.sg/realEstateIIWeb/resources/misc/list_of_postal_districts.htm).  
I am searching the dataset for this pattern, correcting whatever can be addressed automatically and adding the rest to the "*PROBLEMATICS*" for further examination.


```python
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
```


```python
fix_pcodes.called = False
```


```python
fix_pcodes()
```

    Singapore 408564 ==> 408564
    S118556 ==> 118556
    S 278989 ==> 278989


Postcodes were much more consistent than the street types with 3 problems fixed programmati-
cally and 8 pending further inspection.

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
```


```python
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
def process_map(validate=True):
    """Iteratively process each XML element and write to csv(s)
    
    Arrgs:
        validate (bool): Validate the data before write them to csv or not
        
    Returns:
        Nothing
    """

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
```


```python
process_map()
```

### Connection to the database

For connection between Jupyter Notebook and PostgreSQL, I am using [ipython-sql](https://github.com/catherinedevlin/ipython-sql)


```python
"""Loading the ipython-sql module"""
%load_ext sql

"""Disabling the printing of number of rows affected by each query"""
%config SqlMagic.feedback=False

"""Connecting to the database"""
%sql postgresql://jupyter_user:notebook@localhost/Project_3
```




    u'Connected: jupyter_user@Project_3'



### Creation of the Tables

I am using *DELETE CASCADE* on the tables with foreign keys to ensure the drop of "*tags*" along with the related "*elements*".


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

After copying the files to the remote server, i can import them to the database.


```python
%%sql
COPY public.nodes
FROM '/home/yannis/Projects/Data_Analysis/Wrangle-OpenStreetMap-Data/Helper/nodes.csv'
CSV HEADER;

COPY public.nodes_tags
FROM '/home/yannis/Projects/Data_Analysis/Wrangle-OpenStreetMap-Data/Helper/nodes_tags.csv'
CSV HEADER;

COPY public.ways
FROM '/home/yannis/Projects/Data_Analysis/Wrangle-OpenStreetMap-Data/Helper/ways.csv'
CSV HEADER;

COPY public.ways_nodes
FROM '/home/yannis/Projects/Data_Analysis/Wrangle-OpenStreetMap-Data/Helper/ways_nodes.csv'
CSV HEADER;

COPY public.ways_tags
FROM '/home/yannis/Projects/Data_Analysis/Wrangle-OpenStreetMap-Data/Helper/ways_tags.csv'
CSV HEADER;
```




    []



___

## Data assesment in the database


```python
pprint.pprint(PROBLEMATICS)
```

    [('453243296', 'street name', '2'),
     ('46649997', 'street name', u'\u516c\u53f865'),
     ('453227146', 'street name', u'\u516c\u53f865'),
     ('453253763', 'street name', '2'),
     ('169844052', 'street name', '310074'),
     ('1318498347', 'postcode', '135'),
     ('3026819436', 'postcode', '2424'),
     ('3756813987', 'postcode', '05901'),
     ('4338649392', 'postcode', '88752'),
     ('4496749591', 'postcode', '#B1-42'),
     ('23946435', 'postcode', '437 437'),
     ('169844052', 'postcode', '74'),
     ('172769494', 'postcode', '05901')]


I am querying the database for the above elements.


```python
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
```


```python
def get_element_tags(element_id):
    """Returns all the tags for a specific element
    
    Args:
        element_id (str):  The 'id' of the element
        
    Returns (sql.run.ResultSet): The result of the query
    
    """
    if element_type(element_id) == 'node':
        tag = %sql SELECT 'Node' AS el_type, * FROM nodes_tags WHERE nodes_tags.id = $element_id
    elif element_type(element_id) == 'way':
        tag = %sql SELECT 'Way' AS el_type, * FROM ways_tags WHERE ways_tags.id = $element_id
    return tag
```


```python
get_element_tags(PROBLEMATICS[0][0])
```




<table>
    <tr>
        <th>el_type</th>
        <th>id</th>
        <th>key</th>
        <th>value</th>
        <th>type</th>
    </tr>
    <tr>
        <td>Way</td>
        <td>453243296</td>
        <td>street</td>
        <td>2</td>
        <td>addr</td>
    </tr>
    <tr>
        <td>Way</td>
        <td>453243296</td>
        <td>building</td>
        <td>yes</td>
        <td>regular</td>
    </tr>
</table>




```python
get_element_tags(PROBLEMATICS[2][0])
```




<table>
    <tr>
        <th>el_type</th>
        <th>id</th>
        <th>key</th>
        <th>value</th>
        <th>type</th>
    </tr>
    <tr>
        <td>Way</td>
        <td>453227146</td>
        <td>housenumber</td>
        <td>65</td>
        <td>addr</td>
    </tr>
    <tr>
        <td>Way</td>
        <td>453227146</td>
        <td>postcode</td>
        <td>119936</td>
        <td>addr</td>
    </tr>
    <tr>
        <td>Way</td>
        <td>453227146</td>
        <td>street</td>
        <td>公司65</td>
        <td>addr</td>
    </tr>
    <tr>
        <td>Way</td>
        <td>453227146</td>
        <td>building</td>
        <td>yes</td>
        <td>regular</td>
    </tr>
    <tr>
        <td>Way</td>
        <td>453227146</td>
        <td>name</td>
        <td>Habourlink</td>
        <td>regular</td>
    </tr>
</table>



For the two elements above, it looks like the "*street*" value is actually a housenumber.


```python
%%sql
UPDATE ways_tags SET key = 'housenumber'
WHERE (id = '453243296' OR id = '453253763') AND key = 'street'
```




    []




```python
get_element_tags(PROBLEMATICS[1][0])
```




<table>
    <tr>
        <th>el_type</th>
        <th>id</th>
        <th>key</th>
        <th>value</th>
        <th>type</th>
    </tr>
    <tr>
        <td>Way</td>
        <td>46649997</td>
        <td>housenumber</td>
        <td>65</td>
        <td>addr</td>
    </tr>
    <tr>
        <td>Way</td>
        <td>46649997</td>
        <td>postcode</td>
        <td>119936</td>
        <td>addr</td>
    </tr>
    <tr>
        <td>Way</td>
        <td>46649997</td>
        <td>street</td>
        <td>公司65</td>
        <td>addr</td>
    </tr>
    <tr>
        <td>Way</td>
        <td>46649997</td>
        <td>building</td>
        <td>yes</td>
        <td>regular</td>
    </tr>
    <tr>
        <td>Way</td>
        <td>46649997</td>
        <td>name</td>
        <td>Habourlink</td>
        <td>regular</td>
    </tr>
</table>




```python
get_element_tags(PROBLEMATICS[3][0])
```




<table>
    <tr>
        <th>el_type</th>
        <th>id</th>
        <th>key</th>
        <th>value</th>
        <th>type</th>
    </tr>
    <tr>
        <td>Way</td>
        <td>453253763</td>
        <td>building</td>
        <td>yes</td>
        <td>regular</td>
    </tr>
    <tr>
        <td>Way</td>
        <td>453253763</td>
        <td>housenumber</td>
        <td>2</td>
        <td>addr</td>
    </tr>
</table>



"Habour Link" is a place of worship on "Alexandra Terrace"


```python
%%sql
UPDATE ways_tags SET value = 'Alexandra Terrace'
WHERE (id = '453227146' OR id = '46649997') AND key = 'street'
```




    []




```python
get_element_tags(PROBLEMATICS[4][0])
```




<table>
    <tr>
        <th>el_type</th>
        <th>id</th>
        <th>key</th>
        <th>value</th>
        <th>type</th>
    </tr>
    <tr>
        <td>Way</td>
        <td>169844052</td>
        <td>postcode</td>
        <td>74</td>
        <td>addr</td>
    </tr>
    <tr>
        <td>Way</td>
        <td>169844052</td>
        <td>street</td>
        <td>310074</td>
        <td>addr</td>
    </tr>
    <tr>
        <td>Way</td>
        <td>169844052</td>
        <td>building</td>
        <td>yes</td>
        <td>regular</td>
    </tr>
    <tr>
        <td>Way</td>
        <td>169844052</td>
        <td>name</td>
        <td>Toa Payoh Vista Market</td>
        <td>regular</td>
    </tr>
</table>



"Toa Payoh Vista Market" is on 74 Lor 4 Toa Payoh (https://goo.gl/maps/UpoYE2Q4owm)


```python
%%sql
INSERT INTO ways_tags VALUES ('169844052','housenumber','74','addr');

UPDATE ways_tags SET value = '310074' WHERE id ='169844052' AND key = 'postcode';

UPDATE ways_tags SET value = 'Lor 4 Toa Payoh' WHERE id = '169844052' AND key = 'street'
```




    []




```python
get_element_tags(PROBLEMATICS[5][0])
```




<table>
    <tr>
        <th>el_type</th>
        <th>id</th>
        <th>key</th>
        <th>value</th>
        <th>type</th>
    </tr>
    <tr>
        <td>Node</td>
        <td>1318498347</td>
        <td>postcode</td>
        <td>135</td>
        <td>addr</td>
    </tr>
    <tr>
        <td>Node</td>
        <td>1318498347</td>
        <td>street</td>
        <td>Jln Pelatina</td>
        <td>addr</td>
    </tr>
    <tr>
        <td>Node</td>
        <td>1318498347</td>
        <td>building</td>
        <td>yes</td>
        <td>regular</td>
    </tr>
</table>



It looks like "135" is a housenumber not a postcode. To find missing parts of an address (like a postcode) I'm querying the Google Maps' API.


```python
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
```


```python
complete_address(' 135 Jln Pelatina, Singapore')
```

    135 Jln Pelatina, Singapore


I cannot find the postcode, I am just changing the "postcode" to "housenumber".


```python
%sql UPDATE nodes_tags SET key = 'housenumber' WHERE id = '1318498347' AND value = '135'
```




    []




```python
get_element_tags(PROBLEMATICS[6][0])
```




<table>
    <tr>
        <th>el_type</th>
        <th>id</th>
        <th>key</th>
        <th>value</th>
        <th>type</th>
    </tr>
    <tr>
        <td>Node</td>
        <td>3026819436</td>
        <td>city</td>
        <td>Singapore</td>
        <td>addr</td>
    </tr>
    <tr>
        <td>Node</td>
        <td>3026819436</td>
        <td>housenumber</td>
        <td>136</td>
        <td>addr</td>
    </tr>
    <tr>
        <td>Node</td>
        <td>3026819436</td>
        <td>postcode</td>
        <td>2424</td>
        <td>addr</td>
    </tr>
    <tr>
        <td>Node</td>
        <td>3026819436</td>
        <td>street</td>
        <td>Orchard Road</td>
        <td>addr</td>
    </tr>
    <tr>
        <td>Node</td>
        <td>3026819436</td>
        <td>landuse</td>
        <td>retail</td>
        <td>regular</td>
    </tr>
    <tr>
        <td>Node</td>
        <td>3026819436</td>
        <td>name</td>
        <td>Liana Medic Ltd</td>
        <td>regular</td>
    </tr>
    <tr>
        <td>Node</td>
        <td>3026819436</td>
        <td>bitcoin</td>
        <td>yes</td>
        <td>payment</td>
    </tr>
    <tr>
        <td>Node</td>
        <td>3026819436</td>
        <td>phone</td>
        <td>+65 2424666</td>
        <td>regular</td>
    </tr>
    <tr>
        <td>Node</td>
        <td>3026819436</td>
        <td>website</td>
        <td>http://www.lianamedic.com/</td>
        <td>regular</td>
    </tr>
</table>




```python
complete_address(' 136 Orchard Road, Singapore')
```

    136 Orchard Rd, Singapore


I cannot find a valid postcode. I am deleting the specific tag.


```python
%sql DELETE FROM nodes_tags WHERE id = '3026819436' AND key = 'postcode'
```




    []




```python
get_element_tags(PROBLEMATICS[7][0])
```




<table>
    <tr>
        <th>el_type</th>
        <th>id</th>
        <th>key</th>
        <th>value</th>
        <th>type</th>
    </tr>
    <tr>
        <td>Node</td>
        <td>3756813987</td>
        <td>city</td>
        <td>Singapore</td>
        <td>addr</td>
    </tr>
    <tr>
        <td>Node</td>
        <td>3756813987</td>
        <td>country</td>
        <td>SG</td>
        <td>addr</td>
    </tr>
    <tr>
        <td>Node</td>
        <td>3756813987</td>
        <td>housenumber</td>
        <td>6</td>
        <td>addr</td>
    </tr>
    <tr>
        <td>Node</td>
        <td>3756813987</td>
        <td>postcode</td>
        <td>05901</td>
        <td>addr</td>
    </tr>
    <tr>
        <td>Node</td>
        <td>3756813987</td>
        <td>street</td>
        <td>Sago Street</td>
        <td>addr</td>
    </tr>
    <tr>
        <td>Node</td>
        <td>3756813987</td>
        <td>amenity</td>
        <td>restaurant</td>
        <td>regular</td>
    </tr>
    <tr>
        <td>Node</td>
        <td>3756813987</td>
        <td>name</td>
        <td>Wonderful Food and Beverage</td>
        <td>regular</td>
    </tr>
    <tr>
        <td>Node</td>
        <td>3756813987</td>
        <td>phone</td>
        <td>+65 9108 5572</td>
        <td>regular</td>
    </tr>
</table>




```python
complete_address(' 6 Sago Street, Singapore')
```

    6 Sago St, Singapore 059011



```python
%sql UPDATE nodes_tags SET value = '059011' WHERE id = '3756813987' AND key = 'postcode'
```




    []




```python
get_element_tags(PROBLEMATICS[8][0])
```




<table>
    <tr>
        <th>el_type</th>
        <th>id</th>
        <th>key</th>
        <th>value</th>
        <th>type</th>
    </tr>
    <tr>
        <td>Node</td>
        <td>4338649392</td>
        <td>postcode</td>
        <td>88752</td>
        <td>addr</td>
    </tr>
    <tr>
        <td>Node</td>
        <td>4338649392</td>
        <td>name</td>
        <td>Exit Plan</td>
        <td>regular</td>
    </tr>
    <tr>
        <td>Node</td>
        <td>4338649392</td>
        <td>tourism</td>
        <td>attraction</td>
        <td>regular</td>
    </tr>
</table>



The specific amenity is on "279 New Bridge Road, Singapore 088752" (https://goo.gl/maps/K7JzQ3Ujsvq)


```python
%%sql
UPDATE nodes_tags SET value = '088752' WHERE id = '4338649392' AND key = 'postcode';

INSERT INTO nodes_tags VALUES 
('4496749591','housenumber','279','addr'),
('4496749591','street','New Bridge Road','addr')
```




    []




```python
get_element_tags(PROBLEMATICS[9][0])
```




<table>
    <tr>
        <th>el_type</th>
        <th>id</th>
        <th>key</th>
        <th>value</th>
        <th>type</th>
    </tr>
    <tr>
        <td>Node</td>
        <td>4496749591</td>
        <td>city</td>
        <td>Singapore</td>
        <td>addr</td>
    </tr>
    <tr>
        <td>Node</td>
        <td>4496749591</td>
        <td>postcode</td>
        <td>#B1-42</td>
        <td>addr</td>
    </tr>
    <tr>
        <td>Node</td>
        <td>4496749591</td>
        <td>street</td>
        <td>Bukit Timah Shopping Centre</td>
        <td>addr</td>
    </tr>
    <tr>
        <td>Node</td>
        <td>4496749591</td>
        <td>name</td>
        <td>GP Tuition</td>
        <td>regular</td>
    </tr>
    <tr>
        <td>Node</td>
        <td>4496749591</td>
        <td>housenumber</td>
        <td>279</td>
        <td>addr</td>
    </tr>
    <tr>
        <td>Node</td>
        <td>4496749591</td>
        <td>street</td>
        <td>New Bridge Road</td>
        <td>addr</td>
    </tr>
</table>



This amenity does not exist anymore (https://www.bukittimahshoppingcentre.sg/directory/). I'm deleting the whole node.


```python
%sql DELETE FROM nodes WHERE id = '4496749591'
```




    []




```python
get_element_tags(PROBLEMATICS[10][0])
```




<table>
    <tr>
        <th>el_type</th>
        <th>id</th>
        <th>key</th>
        <th>value</th>
        <th>type</th>
    </tr>
    <tr>
        <td>Way</td>
        <td>23946435</td>
        <td>city</td>
        <td>Singapore</td>
        <td>addr</td>
    </tr>
    <tr>
        <td>Way</td>
        <td>23946435</td>
        <td>country</td>
        <td>SG</td>
        <td>addr</td>
    </tr>
    <tr>
        <td>Way</td>
        <td>23946435</td>
        <td>housenumber</td>
        <td>80</td>
        <td>addr</td>
    </tr>
    <tr>
        <td>Way</td>
        <td>23946435</td>
        <td>postcode</td>
        <td>437 437</td>
        <td>addr</td>
    </tr>
    <tr>
        <td>Way</td>
        <td>23946435</td>
        <td>street</td>
        <td>Rhu Cross</td>
        <td>addr</td>
    </tr>
    <tr>
        <td>Way</td>
        <td>23946435</td>
        <td>description</td>
        <td>18 hole Par 72</td>
        <td>regular</td>
    </tr>
    <tr>
        <td>Way</td>
        <td>23946435</td>
        <td>leisure</td>
        <td>golf_course</td>
        <td>regular</td>
    </tr>
    <tr>
        <td>Way</td>
        <td>23946435</td>
        <td>name</td>
        <td>Marina Bay Golf Course</td>
        <td>regular</td>
    </tr>
    <tr>
        <td>Way</td>
        <td>23946435</td>
        <td>phone</td>
        <td>+65 6345 7788</td>
        <td>regular</td>
    </tr>
    <tr>
        <td>Way</td>
        <td>23946435</td>
        <td>website</td>
        <td>http://www.mbgc.com.sg/</td>
        <td>regular</td>
    </tr>
</table>




```python
complete_address(' 80 Rhu Cross, Singapore')
```

    80 Rhu Cross, Singapore 437437



```python
%sql UPDATE ways_tags SET value = '437437' WHERE id = '23946435' AND key = 'postcode'
```




    []



"*Way*" element 169844052 has been corrected already.


```python
get_element_tags(PROBLEMATICS[12][0])
```




<table>
    <tr>
        <th>el_type</th>
        <th>id</th>
        <th>key</th>
        <th>value</th>
        <th>type</th>
    </tr>
    <tr>
        <td>Way</td>
        <td>172769494</td>
        <td>city</td>
        <td>Singapore</td>
        <td>addr</td>
    </tr>
    <tr>
        <td>Way</td>
        <td>172769494</td>
        <td>country</td>
        <td>SG</td>
        <td>addr</td>
    </tr>
    <tr>
        <td>Way</td>
        <td>172769494</td>
        <td>housenumber</td>
        <td>6</td>
        <td>addr</td>
    </tr>
    <tr>
        <td>Way</td>
        <td>172769494</td>
        <td>postcode</td>
        <td>05901</td>
        <td>addr</td>
    </tr>
    <tr>
        <td>Way</td>
        <td>172769494</td>
        <td>street</td>
        <td>Sago Street</td>
        <td>addr</td>
    </tr>
    <tr>
        <td>Way</td>
        <td>172769494</td>
        <td>building</td>
        <td>yes</td>
        <td>regular</td>
    </tr>
    <tr>
        <td>Way</td>
        <td>172769494</td>
        <td>source</td>
        <td>Bing</td>
        <td>regular</td>
    </tr>
</table>




```python
complete_address('6 Sago Street, Singapore')
```

    6 Sago St, Singapore 059011



```python
%sql UPDATE ways_tags SET value = '059011' WHERE id = '172769494' AND key = 'postcode'
```




    []



___

## Data Exploration

### Dataset Specific

Below you may find some basic attributes of the dataset.

#### Size of the database


```python
size_in_bytes = %sql SELECT pg_database_size('Project_3');
print "DB size: " + str(size_in_bytes[0][0]/1024**2) + ' MB'
```

    DB size: 96 MB


#### Number of Unique Users


```python
%%sql
SELECT count(DISTINCT(uid)) AS "Unique Users"
FROM (SELECT uid FROM nodes 
      UNION 
      SELECT uid FROM ways) AS elements;
```




<table>
    <tr>
        <th>Unique Users</th>
    </tr>
    <tr>
        <td>848</td>
    </tr>
</table>



#### Top 10 Users (by number of entries)


```python
%%sql
SELECT nodes_ways."user" AS "User", COUNT(*) AS "Users"
FROM (SELECT "user" FROM nodes
      UNION ALL
      SELECT "user" FROM ways) AS nodes_ways
GROUP BY nodes_ways."user"
ORDER BY "Users" DESC
LIMIT 10;
```




<table>
    <tr>
        <th>User</th>
        <th>Users</th>
    </tr>
    <tr>
        <td>JaLooNz</td>
        <td>155426</td>
    </tr>
    <tr>
        <td>rene78</td>
        <td>32937</td>
    </tr>
    <tr>
        <td>Luis36995</td>
        <td>32150</td>
    </tr>
    <tr>
        <td>cboothroyd</td>
        <td>20478</td>
    </tr>
    <tr>
        <td>calfarome</td>
        <td>16615</td>
    </tr>
    <tr>
        <td>ridixcr</td>
        <td>13830</td>
    </tr>
    <tr>
        <td>nikhilprabhakar</td>
        <td>13082</td>
    </tr>
    <tr>
        <td>Paul McCormack</td>
        <td>12620</td>
    </tr>
    <tr>
        <td>matx17</td>
        <td>12000</td>
    </tr>
    <tr>
        <td>yurasi</td>
        <td>8868</td>
    </tr>
</table>



#### Number of Nodes and Ways


```python
n_nodes = %sql SELECT COUNT(*) FROM nodes
n_ways = %sql SELECT COUNT(*) FROM ways

print "Number of 'nodes: " + str(n_nodes[0][0])
print "Number of 'ways: " + str(n_ways[0][0])
```

    Number of 'nodes: 409352
    Number of 'ways: 66404


### Area Specific

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
        <td>19</td>
    </tr>
    <tr>
        <td>UOB</td>
        <td>13</td>
    </tr>
    <tr>
        <td>OCBC</td>
        <td>10</td>
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
        <td>DSS</td>
        <td>1</td>
    </tr>
    <tr>
        <td>HSBC</td>
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
        <td>Standard Chartered Bank</td>
        <td>1</td>
    </tr>
    <tr>
        <td>Quantified Assets, Pte. Ltd.</td>
        <td>1</td>
    </tr>
</table>



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

There are several areas of improvement of the project in the future.
The first one is on the completeness of the data. All the above analysis is based on a dataset that reflects a big part of Singapore but not the whole country. The reason for this is the lack of a way to download a dataset for the entire Singapore without including parts of the neighboring countries. The analyst has to either select a part of the island/country or select a wider area that includes parts of Malaysia and Indonesia. Also, because of relations between nodes, ways, and relations, the downloaded data expand much further than the actual selection. Below you can see a plotting of the coordinates of the nodes of a dataset from a tight selection of Singapore. You can notice that huge parts of nearby countries were selected.

![initial selection](Resources/images/initial_selection.png)

As a future improvement, I would download a wider selection or the metro extract from [MapZen](https://mapzen.com/data/metro-extracts/metro/singapore/) and filter the non-Singaporean nodes and their references. The initial filtering could take place by introducing some latitude/longitude limits in the code to sort out most of the "non-SG" nodes.

![filter to square](Resources/images/filter_to_square.png)

Then, I would download a shapefile for Singapore (e.g. http://www.diva-gis.org/gdata), use a GIS library like [Fiona](https://pypi.python.org/pypi/Fiona) to create a polygon and finally with a geometric library like [Shapely](https://github.com/Toblerity/Shapely) and compare all the nodes' coordinate against this polygon. Finally, I would clean all the ways and relations from the "non-sg" nodes and remove these that become childless to conclude with a dataset of all (and only) Singapore.

![After GIS](Resources/images/after_gis.png)

The drawback of the above technic is that the comparison of each node against the polygon is a very time-consuming procedure with my initial tests taking 17-18 hours to produce a result. This is the reason the above approach left as a future improvement probably along with the use of multithreading technics to speed up the process.

The second area with room for future improvement is the exploratory analysis of the dataset.  Just to mention some of the explorings that could take place:
* Distribution of commits per contributor.
* Plotting of element creation per type, per day.
* Distribution of distance between different types of amenities
* Popular franchises in the country (fast food, conventional stores, etc.)
* Selection of a bank based on the average distance you have to walk for an ATM.
* Which area has the biggest parks and recreation spaces.  

The scope of the current project was the wrangling of the dataset, so all the above have been left for future improvement.

Finally, open data are here to make average people's life better. For the non-data analyst, it would be nice if there was an application (mobile or web) that could evaluate the suitability of a potential rental house. The work addresses of all family members, importance weights on several amenities like supermarkets, convenience stores, cafes,  public transportation, etc. and the application would calculate the suitability of each potential rental. The user would be able to sort them by score and compare them.

___

## References



Udacity - https://www.udacity.com/  
Wikipedia - https://www.wikipedia.org/  
OpenStreetMap - https://www.openstreetmap.org  
Overpass API - http://overpass-api.de/  
Python Software Foundation - https://www.python.org/  
Urban Redevelopment Authority of Singapore - https://www.ura.gov.sg  
Catherine Devlin's Github repository - https://github.com/catherinedevlin/ipython-sql  
Google Map APIs - https://developers.google.com/maps/
