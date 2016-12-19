
# Project Review

## Code Functionality

- [X] **Final project code functionality reflects the description in the project document.**  
>Good job cleaning your dataset. Please note that the process_map() function taken the input file as an argument and then calls shape_element() before writing output files for database insertion. It is thus important that shape_element() calls the implemented cleaning routines such that cleaned records are uploaded for subsequent analysis. Please resubmit addressing this issue.

**Response**: *Actually my mistake was that I had forgotten the "input file" as an argument to **process_map()**. My version of **process_map()** runs directly onto the element tree object which has already been cleaned. To stay on the safe side for good, I added checks for cleaning.*

```python
#Check that the dataset has been cleared
if update_street_type.called is not True:
    update_street_type(root)
            
if fix_pcodes.called is not True:
    fix_pcodes()
```

## Code Readability

- [X] **Final project code that is not intuitively readable is well-documented with comments.**  
>Good job documenting your code. Please note that all functions should be documented with docstrings, and that additional information should be included besides the description of the function's purpose. In particular, it is important to describe what types of variables are taken as arguments and what is returned by the function. Take a look at http://sphinxcontrib-napoleon.readthedocs.io/en/latest/example_google.html for further reference.

**Response:** *Comments added. Please let me know if there is a mistake to any of them.*

## Problems encountered in your map

- [X] **Student response shows understanding of the process of auditing, and ways to correct or standardize the data, including dealing with problems specific to the location, e.g. related to language or traditional ways of formatting.**  
>I was not able to find a function for auditing postal codes. Please note that it is interesting to perform a programmatic audit whenever possible, and variables that have well defined formats are well suited for the employment of regular expressions to this end. For example, postal codes in the United States have a basic five digit format that can be matched against each record in your dataset:
>```python
re.match(r'^\d{5}$', postcode)
```

**Response:** *There was `fix_pcodes()`, you probably missed it. I simplified it a little bit by using 1 regular expression instead of 2.*

## Other ideas about the datasets

- [X] **Submission document includes one or more additional suggestions for improving and analyzing the data.**  
You mentioned several interesting ways to further analyze your dataset. Please note that it would also be interesting to suggest a potential improvement to the actual data. Please note that you can be rather creative here, as you don't need to actually implement it. I have seen students proposing the development of an app using OSM data to suggest bike routes, cross validation of OSM with external data sources through APIs and the establishment of a reward system for active OSM contributors.

**Response:** *Added an additional idea for a practical use of the dataset.*

# Code Review

- [X] **Suggestion**  
>Please note that it is safer to enforce strict pattern matching when dealing with variables that have well defined formats. You probably want to discard a seven digit string. The best strategy is thus to anticipate specific patterns that can be cleaned. For example, the following command  
`clean_postcode = re.findall(r'^(\d{5})-\d{4}$', postcode)[0]`  
>will return a standardized five digit US postal code from an entry like '10027-0094'.

**Response:** *Postcodes in Singapore consist of 6 digits with the first two, denoting the Postal Sector, take values between 01 and 80, excluding 74.  
I'm not very familiar with regular expressions, but I think my regular expression is as strict as it gets.  
It tries to find any number from 00 to 73 or 75 to 80 followed by four digits and extracts it from the string.  
Keep in mind that I don't try to convert the postcodes from one system to another and I don't know the initial format (Some of them may be "S xxxxxx" or "Sxxxxxx" or even "Singapore XXXXXX").  
Please let me know if I have not understood your comment properly.*

---

*Best Regards*  
**Yannis**