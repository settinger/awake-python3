import sqlite3, re
versions=dict()
#   |-----------Version characteristics here.-----------|
#   | These are the expected results of each test       |
#   |     in format [test_name:expected_result].        |
#   | Expected_result is interpereted as a regex.       |
#   | The tests are executed in order and testing for a |
#   |     version stops as soon as a test fails.        |
#   | This means that tests that would be invalid for a |
#   |     specific version can be put after checks that |
#   |     would reject that version.                    |
#   |---------------------------------------------------|
versions[1]=[["memref_proc_type","^text$"]]
versions[2]=[["memref_proc_type","^address$"]]
tests=dict()
#   |-----------------Test queries here-----------------|
#   | These are the queries to run for each test,       |
#   |     in format:                                    |
#   |     [query,filter_column,filter_regex,data_field] |
#   | The test returns the first result where           |
#   |     the value for filter_column matches           |
#   |     filter_regex.                                 |
#   | If filter_column or filter_regex is None,         |
#   |     no filter is applied.                         |
#   | data_field indicates which column to return.      |
#   |---------------------------------------------------|
tests["memref_proc_type"]=["PRAGMA table_info(memref);","name","^proc$","type"]
def runTest(c,testname):
    test=tests[testname]
    query=test[0]
    filter_col=test[1]
    filter_regex=test[2]
    data_field=test[3]
    c.execute(query)
    if (filter_col is None) or (filter_regex is None):                  #Don't apply filters if these are None
        result=c.fetchone()                                                 #Get one result.
        if not (data_field in list(result.keys())):                               #If data_field is not a column in the result,
            return "!NODATACOL!"                                                #return a special string.
        return result[data_field]                                           #Else, return data_field's value.
    else:                                                               #Else, apply the filter.
        while True:                                                         #Keep getting results until one matches.
            result=c.fetchone()                                                 #Get one result
            if result is None:                                                  #If we run out of results,
                return "!NORESULTS!"                                                #return a special string.
            if not (filter_col in list(result.keys())):                               #If filter_col is not a column in the result,
                return "!NOFILTERCOL!"                                              #return a special string
            if re.search(filter_regex,result[filter_col]) is not None:          #If the regex matches,
                if not (data_field in list(result.keys())):                               #If data_field is not a column in the result,
                    return "!NODATACOL!"                                                #return a special string.
                return result[data_field]                                           #Else, return data_field's value.
def detectVersion(filename):
    conn = sqlite3.connect(filename, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row                  #Make cursors return row objects instead of tuples.
    c=conn.cursor()
    for versionid in list(versions.keys()):               #Run for each version
        ver=versions[versionid]
        for test in ver:                                #Run for each test
            result=runTest(c, test[0])                   #Run the test
            if re.search(test[1],result) is None:           #If the result doesn't match expected value,
                break                                           #Skip the rest of the tests for this version.
        else:                                           #If every test completed successfully,
            c.close()                                       #Close the cursor    
            conn.close()                                    #Close the connection
            return versionid                                #return the version number.
    c.close()
    conn.close()
    return 0
