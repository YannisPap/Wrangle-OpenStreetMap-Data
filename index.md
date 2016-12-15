
**Note: This is a brief report of the Project. Please see the [Readme](Readme.md) file for the main Project.**

---

### Data Extraction and Wrangling

# Wrangle-OpenStreetMap-Data

![Singapore](images/singapore.jpg)

## Introduction

On the particular project, I am using data mungling techniques to assess the quality of OpenStreetMap’s (OSM) data for the center of Singapore regarding their consistency and uniformity.
The data wrangling takes place programmatically, using **Python** for the most of the process and **SQL** for items that need further attention while in the **PostgreSQL**.

The dataset describes the center of Singapore, covering an area from Clementi on the west, to
Bedok on the east and from Serangoon on the north, to Sentosa Island on the south. The size of the dataset is 96 MB and can can be downloaded from [here](http://overpass-api.de/api/map?bbox=103.7651,1.2369,103.9310,1.3539)

## Skills demonstrated

* Assessment of the quality of data for validity, accuracy, completeness, consistency and uniformity.
* Parsing and gathering data from popular file formats such as .xml and .csv.
* Processing data from very large files that cannot be cleaned with spreadsheet programs.
* Storing, querying, and aggregating data using SQL.

## The Dataset

OpenStreetMap's data are structured in well-formed XML documents (.osm files) that consist of the following elements:
* **Nodes**: "Nodes" are individual dots used to mark specific locations (such as a postal box). Two or more nodes are used to draw line segments or "ways".
* **Ways**: A "way" is a line of nodes, displayed as connected line segments. "Ways" are used to create roads, paths, rivers, etc.  
* **Relations**: When "ways" or areas are linked in some way but do not represent the same physical thing, a "relation" is used to describe the larger entity they are part of. "Relations" are used to create map features, such as cycling routes, turn restrictions, and areas that are not contiguous. The multiple segments of a long way, such as an interstate or a state highway are grouped into a "relation" for that highway. Another example is a national park with several locations that are separated from each other. Those are also grouped into a "relation".

All these elements can carry tags describing the name, type of road, and other attributes. 

For the particular project, I am using a custom .osm file for the center of Singapore which I exported by using the overpass API. The  dataset has a volume of 96 MB and can be downloaded from this [link](http://overpass-api.de/api/map?bbox=103.7651,1.2369,103.9310,1.3539)  

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

Although most of the Singaporean street names end with the street type (e.g., “Serangoon Road” or “Arab Street”) it is also common to end with a number instead (e.g. “Bedok North Avenue 1”).  
Thus, by using regular expressions, I am extracting the last word that does not contain numbers from the street name.  
  
It would be easy to populate the list of Common Street Types with some profound values like Street or Avenue, but guessing does not take into account any local peculiarity. Instead, I searched the dataset for all the different types and used the 12 with the most occurrences (From 13th position, abbreviations start to appear).


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



To find the street names that need correction, I used the “*get_close_matches()*” function from the [difflib](https://docs.python.org/2/library/difflib.html?highlight=get_close_matches) module to find “close matches” of the 12 Common Street Types. This is what I found:


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

The code was able to correct 998 problems.


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
    998 street names were fixed


### Auditing Postcodes

Postcodes in Singapore consist of 6 digits with the first two, denoting the Postal Sector, take values between 01 and  80, excluding 74 ([Urban Redevelopment Authority of Singapore](https://www.ura.gov.sg/realEstateIIWeb/resources/misc/list_of_postal_districts.htm)).  
I am searching the dataset for this pattern, correcting whatever can be addressed automatically and adding the rest to the "*PROBLEMATICS*" for further examination.


```python
fix_pcodes()
```

    Singapore 408564 ==> 408564
    S118556 ==> 118556
    S 278989 ==> 278989


Postcodes were much more consistent than the street types with 3 problems fixed programmati-
cally and 8 pending further inspection.

___

## Data assesment in the database

After performing the most of the cleaning with Python, I stored the dataset in a database to explore it and examine further the PROBLEMATIC elements.
As a database I used PostgreSQL to present a generic solution although a lightweight database like SQLite might be a more appropriate choice for the size of the dataset.

### Addresses

The small number of the elements that were requiring further attention (13) allowed me to examine them one by one. There were three categories of problems.  
In the first category belong elements that some values have been placed to wrong attributes (e.g. housenumber in the place of postcode. These problems resolved just by checking the attributes and update the relevant tables with the righ keys/values relation.  
Incomplete addresses with no self-explained errors belong to the second category. For these elements I defined a function that uses Google Maps API to resolve the full address from a partial address. This was helpful for the addresses with missing postcodes.  
Finally, whatever could not be resolved with one of the above ways I used web search with any information available.  
You may find the changes that took place during this phase in the following table.

| Element id | Problematic Attribute | Original Value | Corrected Value              |
|------------|-----------------------|----------------|------------------------------|
| 453243296  | street                | 2              | (street attribute removed)   |
| 453243296  | housenumber           | (missing)      | 2                            |
| 453253763  | street                | 2              | (street attribute removed)   |
| 453253763  | housenumber           | (missing)      | 2                            |
| 453227146  | street                | 65             | Alexandra Terrace            |
| 46649997   | street                | 65             | Alexandra Terrace            |
| 169844052  | street                | 310074         | Lor 4 Toa Payoh              |
| 169844052  | postcode              | 74             | 310074                       |
| 169844052  | housenumber           | (missing)      | 74                           |
| 1318498347 | postcode              | 135            | (postcode attribute removed) |
| 1318498347 | housenumber           | (missing)      | 135                          |
| 3026819436 | postcode              | 2424           | 238841                       |
| 3756813987 | postcode              | 05901          | 059011                       |
| 4338649392 | postcode              | 88752          | 088752                       |
| 4338649392 | housenumber           | (missing)      | 279                          |
| 4338649392 | street                | (missing)      | New Bridge Road              |
| 4496749591 | postcode              | #B1-42         | (element deleted)            |
| 23946435   | postcode              | 437 437        | 437437                       |
| 172769494  | postcode              | 05901          | 059011                       |

### Amenities

In Singapore they refer to the banks with their abbreviations rather than their complete names.
This fact along with their popularity of the ATMs on the street amenities list (will be presented
later) makes them prone to mistakes. The assessment revealed only 5 issues:
- ‘UOB’ referred as ‘Uob’
- ‘POSB’ referred as ‘Posb’
- ‘OCBC’ referred as ‘Overseas Chinese Banking Corporation’
- 2 completely irrelevant nodes marked as ‘ATM’

___

## Data Exploration

### Dataset Specific

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
        <td>sikh</td>
        <td>1</td>
    </tr>
    <tr>
        <td>jewish</td>
        <td>1</td>
    </tr>
</table>



___

## Ideas for additional improvements.

There are two areas where the current project can be improved in the future.
The first one is on the completeness of the data. All the above analysis is based on a dataset that reflects a big part of Singapore but not the whole country. The reason for this is the lack of a way to download a dataset for the entire Singapore without including parts of the neighboring countries. The analyst has to either select a part of the island/country or select a wider area that includes parts of Malaysia and Indonesia. Also, because of relations between nodes, ways, and relations, the downloaded data expand much further than the actual selection. Below you can see a plotting of the coordinates of the nodes of a dataset from a tight selection of Singapore. You can notice that huge parts of nearby countries were selected.

![initial selection](../Resources/initial_selection.png)

As a future improvement, I would download a wider selection or the metro extract from [MapZen](https://mapzen.com/data/metro-extracts/metro/singapore/) and filter the non-Singaporean nodes and their references. The initial filtering could take place by introducing some latitude/longitude limits in the code to sort out most of the "non-SG" nodes.

![filter to square](../Resources/filter_to_square.png)

Then, I would download a shapefile for Singapore (e.g. http://www.diva-gis.org/gdata), use a GIS library like [Fiona](https://pypi.python.org/pypi/Fiona) to create a polygon and finally with a geometric library like [Shapely](https://github.com/Toblerity/Shapely) and compare all the nodes' coordinate against this polygon. Finally, I would clean all the ways and relations from the "non-sg" nodes and remove these that become childless to conclude with a dataset of all (and only) Singapore.

![After GIS](../Resources/after_gis.png)

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
Google Map APIs - https://developers.google.com/maps/
