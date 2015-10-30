'''
NagConf - Management Console Menu for modifying, building, and deleting
Nagios configuration files. 
'''

import logging
import sys
import inspect
import gc
import os
import itertools
import operator
import pprint

from operator import itemgetter
from optparse import OptionParser, OptionGroup

sversion = 'v0.1'
scriptfilename = os.path.basename(sys.argv[0])
defaultlogfilename = scriptfilename + '.log'

import ncClasses
from ncClasses import NagObjFlex

def setuplogging(loglevel,printtostdout,logfile):
    #pretty self explanatory. Takes options and sets up logging.
    print "starting up with loglevel",loglevel,logging.getLevelName(loglevel)
    logging.basicConfig(filename=logfile,
                        filemode='w',level=loglevel, 
                        format='%(asctime)s:%(levelname)s:%(message)s')
    if printtostdout:
        soh = logging.StreamHandler(sys.stdout)
        soh.setLevel(loglevel)
        logger = logging.getLogger()
        logger.addHandler(soh)

def giveupthefunc():
    #This function grabs the name of the current function
    # this is used in most of the debugging/info/warning messages
    # so I know where an operation failed
    '''This code block comes from user "KindAll" on StackOverflow
    http://stackoverflow.com/a/4506081'''
    frame = inspect.currentframe(1)
    code  = frame.f_code
    globs = frame.f_globals
    functype = type(lambda: 0)
    funcs = []
    for func in gc.get_referrers(code):
        if type(func) is functype:
            if getattr(func, "func_code", None) is code:
                if getattr(func, "func_globals", None) is globs:
                    funcs.append(func)
                    if len(funcs) > 1:
                        return None
    return funcs[0] if funcs else None

def get_config(options):
    ''' Another sample function.
    '''
    thisfunc = str(giveupthefunc())
    logging.debug(thisfunc + "Number of files in cfgdir = " + str(len(os.listdir(options.cfgdir))))
    numcfgfiles = 0
    dir = options.cfgdir
    cfgrawtext = []
    cfgfiles = []
    for fname in os.listdir(dir):
        if '.cfg' in fname:
            numcfgfiles += 1
            cfgfiles.append(fname)
    logging.debug(thisfunc + "Number of cfg files in cfgidr = " + str(numcfgfiles))
    files = [os.path.join(dir, f) for f in cfgfiles]
    cfglines = 0
    for f in files:
        with open(f,'r') as cf:
            ''' now we're reading the files we actually care about.
            Since niether us nor Nagios cares about individual files
            we're going to strip out comments 
            '''
            for line in cf:
                cfglines += 1
                if '#' not in line:
                    cfgrawtext.append(line)
    logging.debug(thisfunc + "Number of lines of raw config: " + str(cfglines))
    return(cfgrawtext)    

def classify_config(raw):
    ''' Takes raw Nagios config text and processes 
    it into rudimentary objects (NagObjFlex)
    properties based on stuff between the {} in the text
    returns a list of those objects
    '''
    import re
    # first scrub the rawtext to remove tabs
    rawtext = []
    for line in raw:
        line = line.replace('\t',' ')
        line = line.strip('\t')
        rawtext.append(line)
    
    r_def = re.compile('(define )(?P<defname>[a-zA-Z_]*)({| *{)')
    r_end = re.compile('(})')
    r_prop = re.compile('( *)(?P<prop>[a-zA-Z_]*)( *)(?P<val>.*)')
    r_valcom = re.compile('(?P<realval>.*)(?P<comment>;.*)')
    anchors = []
    # go through and find blocks of definitions and add start/stop points to anchors list
    for i,line in enumerate(rawtext):
        r_def_match = re.search(r_def,line)
        r_end_match = re.search(r_end,line)
        if r_def_match or r_end_match:
            anchors.append(i)
    #logging.debug(str(anchors))
    anchors.sort(reverse=True)
    #logging.debug(str(anchors))
    allobjs = []
    while True:
        definition = ''
        currObj = None
        # loop through anchors blocks of definitions
        for ln in range(anchors.pop(),anchors.pop()):

            line = rawtext[ln]
            r_def_match = re.search(r_def,line)
            r_prop_match = re.search(r_prop,line)
            if r_def_match:
                definition = r_def_match.group('defname')
                # create blank new flex object with typestring = definition
                currObj = NagObjFlex(definition)
            elif r_prop_match and not r_def_match:
                prop = r_prop_match.group('prop')
                val = r_prop_match.group('val')
                r_valcom_match = re.search(r_valcom,val)
                if r_valcom_match:
                    val = r_valcom_match.group('realval')
                # first have to set the prop as a NagObjSuperProp() since this is new prop
                setattr(currObj,prop,ncClasses.NagObjSuperProp(val))
        allobjs.append(currObj)
        #print cfgformat.format(definition,prop,val)
        if len(anchors) < 1:
            break
    cfgformat = '{0:30}{1}'
    '''
    for obj in allobjs:
        for thing in obj.dumpself():
            logging.debug(cfgformat.format(*thing))
        logging.debug(' ')
    '''
    logging.debug("Number of base objects: " + str(len(allobjs)))
    return allobjs


def morph(nco):
    classed = []
    for thing in nco.nagObjs:
        try:
            #logging.debug("morph(): pre-morph thing classification: '%s'" % thing.classification.value)
            newthing = thing.morph_to_classed()
            #logging.debug("morph(): post-morph newthing classification: '%s'" % newthing.classification.value)
            if newthing is not None:
                classed.append(newthing)
        except Exception as ar:
            #print "--"
            logging.debug(str(ar))
    #logging.debug("morph(): Finished running things.morph_to_classed(), attempting nco.dump_s(tats()...")
    #logging.debug(nco.dump_stats())
    #logging.debug("morph(): Finished nco.dump_stats(), now running nco.purge()....")
    nco.purge()
    #logging.debug("morph(): Finished nco.purge(), trying nco.dump_stats()...")
    #logging.debug(nco.dump_stats())
    for thing in classed:
        nco.nagObjs.append(thing)

    #logging.debug("Now leaving morph()...")
    return nco

def dedupe_sort_list_of_dict(lod,dedupeField=None,orderField=None):
    ''' Takes a list of dictionaries and 
    eliminates duplicates that have the 
    same dedupeField.
    Based on a stackoverflow answer by 
    http://stackoverflow.com/users/885973/turkesh-patel
    '''
    '''
    E.g.,
    templatelist = [    {'tpname': 'TPL-windows-server',    'idx': 1}, 
                        {'tpname': 'TPL-host-pnp',          'idx': 2}, 
                        {'tpname': 'buddy',                 'idx': 3}, 
                        {'tpname': 'generic-host',          'idx': 4}, 
                        {'tpname': 'TPL-windows-server',    'idx': 5}, 
                        {'tpname': 'TPL-host-pnp',          'idx': 6}, 
                        {'tpname': 'generic-host',          'idx': 7},
                    ]
    dedupe_sort_list_of_dict(templatelist,dedupeField='tpname',orderField='idx')

    '''
    # first dedupe
    getvals = operator.itemgetter(dedupeField)
    lod.sort(key=getvals)
    result = []
    for k, g in itertools.groupby(lod, getvals):
        result.append(g.next())
    # now sort
    getvals = operator.itemgetter(orderField)
    # since Nagios inheritance works left to right and we're 'popping' to inherit...
    result.sort(key=getvals,reverse=True) 
    lod[:] = result
    msg = pprint.pformat(lod)
    #logging.debug(msg + '\n')
    return(lod)


def discover_template_chain(nco):
    templates = []
    for thing in nco.nagObjs:
        try:
            if thing.name:
                templates.append(thing)
        except:
            pass
    logging.debug("Number of templates = " + str(len(templates)))
    count = 0
    count_usingtpls = 0
    ''' This is a sloppy way of doing this. It only works to discover inheritance
    for as many levels as there are loops. I think it will go down 5 or 6 levels 
    unless we add more loops. Nagios inherently supports infinite levels of inheritance
    so nagConf becomes the limitation here. 
    '''
    for thing in nco.nagObjs:
        i_tpls = [] # holds indexed templates
        seq = 0 # the index number so we can track inheritance priority.
        try:
            tpls = thing.use.value.split(',')
            count_usingtpls += 1
            for tp in tpls:
                seq += 1
                i_tpls.append({'idx':seq,'tpname':tp})
            for thing2 in templates:
                try:
                    if thing2.name.value in tpls:
                        tpls2 = thing2.use.value.split(',')
                        for a in tpls2:
                            tpls.append(a)
                            seq += 1
                            i_tpls.append({'idx':seq,'tpname':a})
                        for thing3 in templates:
                            try:
                                if thing3.name.value in tpls2:
                                    tpls3 = thing3.use.value.split(',')
                                    for b in tpls3:
                                        tpls.append(b)
                                        seq += 1
                                        i_tpls.append({'idx':seq,'tpname':b})
                                    for thing4 in templates:
                                        try:
                                            if thing4.name.value in tpls3:
                                                tpls4 = thing4.use.value.split(',')
                                                for c in tpls4:
                                                    tpls.append(c)
                                                    seq += 1
                                                    i_tpls.append({'idx':seq,'tpname':c})
                                                for thing5 in templates:
                                                    try:
                                                        if thing5.name.value in tpls4:
                                                            tpls5 = thing5.use.value.split(',')
                                                            for d in tpls5:
                                                                tpls.append(d)
                                                                seq += 1
                                                                i_tpls.append({'idx':seq,'tpname':d})
                                                            for thing6 in templates:
                                                                try:
                                                                    if thing6.name.value in tpls5:
                                                                        tpls6 = thing6.use.value.split(',')
                                                                        for e in tpls5:
                                                                            tpls.append(e)
                                                                            seq += 1
                                                                            i_tpls.append({'idx':seq,'tpname':e})
                                                                except:
                                                                    logging.debug("reached max template chain depth (max 5)")
                                                    except:
                                                        pass
                                        except:
                                            pass
                            except:
                                pass
                except:
                    pass
            # remove duplicates
            i_tpls = dedupe_sort_list_of_dict(i_tpls,dedupeField='tpname',orderField='idx')
            # now strip out extra blank space chars
            for tplll in i_tpls:
                try:
                    tplll['tpname'] = tplll.get('tpname').rstrip(' ')
                except:
                    pass
            thing.templateChain.value = i_tpls
            #logging.debug("Discovered template chain: " )
            #for tp in i_tpls:
                #logging.debug("\t\t %s" % str(tp))
            count += 1
        except Exception as el:
            #Slogging.debug(str(el))
            pass
    logging.debug("discover_template_chain(): Discovered %s chains." % str(count))
    logging.debug("discover_template_chain(): Number of objects with the 'use' statement: %s" % str(count_usingtpls))
    return(nco)

def inherit_from_chain(nco):
    ''' Takes the template chain and cycles through
    it in reverse overriding properties. 
    '''
    # lists to hold templates and users of templates
    tpls = []
    tpls_strings = []
    tplsAndUsers = []
    users = []
    for obj in nco.nagObjs:
        try:
            if obj.name.value and obj.use.value:
                # go ahead and strip out spaces in the object's name field
                obj.name.value = obj.name.value.rstrip(' ')
                #logging.debug("Found template AND user with name = '%s'" % obj.name.value)
                tplsAndUsers.append(obj)
                tpls_strings.append(obj.name.value)
        except:
            pass
    for obj in nco.nagObjs:
        try:
            # only templates have the .name property
            if obj.name.value and obj.name.value not in tpls_strings:
                obj.name.value = obj.name.value.rstrip(' ')
                #logging.debug("Found original template with name = %s" % obj.name.value)
                tpls.append(obj)
        except Exception as er:
            #logging.debug("Exception filtering templates: " + str(er))
            pass
        try:
            # only things using templates have the .use property
            if obj.use.value:
                users.append(obj)
        except:
            pass
    logging.debug("Len(tpls): %s" % str(len(tpls)))
    logging.debug("Len(users): %s" % str(len(users)))
    count_copies = 0

    # now combine all templates into one list
    for t in tplsAndUsers:
        tpls.append(t)
    for user in tpls:
        # if they have a template chain...
        logging.debug("Working on template with name: " + user.name.value)
        if len(user.templateChain.value) >= 1:
            #logging.debug("\tlen(user.templateChain.value): " + str(len(user.templateChain.value)))
            while True:
                try:
                    working = user.templateChain.value.pop()
                    #logging.debug("\tSearching for template with name: '%s' ..." % working.get('tpname'))
                except Exception as dog:
                    #logging.debug("\tException popping from templateChain: " + str(dog))
                    break
                # cycle through the template list
                found = False
                for tpl in tpls:
                    # find the matching template
                    if working.get('tpname') == tpl.name.value:
                        found = True
                        # find all set properties from the template, make that list attr_to_copy
                        attrs_to_copy = tpl.display_filter(transfer=True)
                        
                        #logging.debug("\t\tCopying properties from: " + working.get('tpname'))
                        for prop in attrs_to_copy:
                            val = getattr(getattr(tpl,prop),'value')
                            if val is not '':
                                msg = "\t\t\t%s::%s (%s) came from %s" % (working.get('idx'),prop,val,tpl.name.value)
                                user.inheritanceLog.value.append(msg)
                                try:
                                    existingValue = getattr(getattr(user,prop),'value',val)
                                    if existingValue == '':
                                        raise(Exception)
                                    elif '+' in existingValue:
                                        print("found a +")
                                        # must honor nagios additive property
                                        # strip out the '+' from the string
                                        existingValue = existingValue.strip('+')
                                        newValue = existingValue + ',' + val
                                        print("newValue: '%s' for '%s'" % (newValue,user.name.value))
                                        # set the new value
                                        setattr(getattr(user,prop),'value',newValue)
                                        # record the history chain
                                        tHist = getattr(getattr(user,prop),'inheritanceHistory')
                                        tHist.append(tpl.name.value)
                                        setattr(getattr(user,prop),'inheritanceHistory',tHist)
                                    else:                                    
                                        #logging.debug("\t\t\t\tFound existing propery '%s', tracking chain but not changing..." % prop)
                                        # pull in existing inheritanceHistory if any
                                        tHist = getattr(getattr(user,prop),'inheritanceHistory')
                                        tHist.append(tpl.name.value)
                                        setattr(getattr(user,prop),'inheritanceHistory',tHist)
                                except:
                                    #logging.debug("\t\t\t\tNo pre-existing property or value blank for '%s', creating new..." % prop)
                                    tempObjSuperProp = ncClasses.NagObjSuperProp(val,explicitInheritance=True,donor=tpl.name.value)
                                    setattr(user,prop,tempObjSuperProp)
                                    count_copies += 1
                #logging.debug('\t\t\t\tFound: ' + str(found))
            general =  user.classification.value
            logging.debug("History chain for '%s' with name '%s': " % (general,user.name.value))
            for propString in user.display_filter(transfer=True):
                prop = getattr(user,propString)
                try:
                    histFormat = "{0:55}{1:100}{2:}"
                    ider = "'%s.%s'" % (general,propString)
                    hist = "'" + str(prop.return_history()) + "'"
                    msg = histFormat.format(ider,"'" + prop.value + "'",hist)
                    logging.debug('\t\t' + msg)
                except:
                    pass
    # now loop through all the rest of the objects
    for user in users:
        #logging.debug("Working on user with uid: " + user.get_uid())
        # if they have a template chain...
        try:
            user.name.value
            #logging.debug("User has name '%s', which means it's a template so skipping..." % user.name.value)
            continue
        except:
            if len(user.templateChain.value) >= 1:
                #logging.debug("\tlen(user.templateChain.value): " + str(len(user.templateChain.value)))
                while True:
                    try:
                        working = user.templateChain.value.pop()
                        #logging.debug("\tSearching for template with name: '%s' ..." % working.get('tpname'))
                    except Exception as dog:
                        #logging.debug("\tException popping from templateChain: " + str(dog))
                        break
                    # cycle through the template list
                    found = False
                    for tpl in tpls:
                        # find the matching template
                        if working.get('tpname') == tpl.name.value:
                            found = True
                            # find all set properties from the template, make that list attr_to_copy
                            attrs_to_copy = tpl.display_filter(transfer=True)
                            #logging.debug("\t\tCopying properties from: " + working.get('tpname'))
                            for prop in attrs_to_copy:
                                val = getattr(getattr(tpl,prop),'value')
                                if val is not '':
                                    msg = "\t\t\t%s::%s (%s) came from %s" % (working.get('idx'),prop,val,tpl.name.value)
                                    user.inheritanceLog.value.append(msg)
                                    try:
                                        existingValue = getattr(getattr(user,prop),'value',val)
                                        if existingValue == '':
                                            raise(Exception)
                                        elif '+' in existingValue:
                                            print("found a +")
                                            # must honor nagios additive property
                                            # strip out the '+' from the string
                                            existingValue = existingValue.strip('+')
                                            newValue = existingValue + ',' + val
                                            # set the new value
                                            setattr(getattr(user,prop),'value',newValue)
                                            # record the history chain
                                            tHist = getattr(getattr(user,prop),'inheritanceHistory')
                                            tHist.append(tpl.name.value)
                                            setattr(getattr(user,prop),'inheritanceHistory',tHist)
                                        else:                                    
                                            #logging.debug("\t\t\t\tFound existing propery '%s', tracking chain but not changing..." % prop)
                                            # pull in existing inheritanceHistory if any
                                            tHist = getattr(getattr(user,prop),'inheritanceHistory')
                                            tHist.append(tpl.name.value)
                                            setattr(getattr(user,prop),'inheritanceHistory',tHist)
                                    except:
                                        #logging.debug("\t\t\t\tNo pre-existing property or value blank for '%s', creating new..." % prop)
                                        tempObjSuperProp = ncClasses.NagObjSuperProp(val,explicitInheritance=True,donor=tpl.name.value)
                                        setattr(user,prop,tempObjSuperProp)
                                        count_copies += 1
                    #logging.debug('\t\t\t\tFound: ' + str(found))
                general = user.classification.value
                logging.debug("History chain for '%s': " % user.get_uid())
                for propString in user.display_filter(transfer=True):
                    prop = getattr(user,propString) 
                    try:
                        histFormat = "{0:55}{1:100}{2:}"
                        ider = "'%s.%s'" % (general,propString)
                        hist = "'" + str(prop.return_history()) + "'"
                        msg = histFormat.format(ider,"'" + prop.value + "'",hist)
                        logging.debug('\t\t' + msg)
                    except:
                        pass

            #for logentry in user.inheritanceLog.value:
                #logging.debug("\t\t\t\t" + logentry)
    #

    logging.debug("inherit_from_chain(): Number of object property copies: %s" % str(count_copies))
    return(nco)

def main(options):
    ''' The main() method. Program starts here.
    '''
    # test the logging
    thisfunc = str(giveupthefunc())
    cfgrawtext = get_config(options)
    nco = ncClasses.NagConfig()
    nco.nagObjs = classify_config(cfgrawtext)
    '''
    mn = ncClasses.NagObjHost()
    mn.color = 'red'
    mn.age = 10
    mn.something = 'whatever'
    print mn.dumpself()
    '''
    logging.debug(nco.dump_stats())
    logging.debug("About to try and nco.scrub_data()...")
    try:
        nco.scrub_data()
    except Exception as ee:
        #logging.debug(str(ee))
        pass
    logging.debug("Finished nco.scrub_data(), attempting nco.dump_stats()...")
    logging.debug(nco.dump_stats())
    logging.debug("About to try and morph(nco)...")
    try:
        nco = morph(nco)
    except Exception as eee:
        #logging.debug(str(eee))
        pass
    logging.debug("Finished morph(), now trying nco.dump_stats()")
    logging.debug(nco.dump_stats())


    try:
        nco = discover_template_chain(nco)
    except Exception as eeee:
        #logging.debug(str(eeee) )
        pass

    try:
        nco = inherit_from_chain(nco)
    except Exception as ex:
        logging.debug(str(ex))
        pass

    for thing in nco.nagObjs:
        logging.debug(thing.gen_nag_text())


    #nco.gen_cfg_file('nagconf.cfg')

if __name__ == '__main__':
    '''This main section is mostly for parsing arguments to the 
    script and setting up debugging'''
    from optparse import OptionParser
    '''set up an additional option group just for debugging parameters'''
    from optparse import OptionGroup
    usage = ("%prog [--debug] [--printtostdout] [--logfile] [--version] [--help] [--samplefileoption]")
    #set up the parser object
    parser = OptionParser(usage, version='%prog ' + sversion)
    parser.add_option('-c','--cfgdir', 
                    type='string',
                    help=("This is the directory containing Nagios .cfg files."),default='.\samples')

    parser_debug = OptionGroup(parser,'Debug Options')
    parser_debug.add_option('-d','--debug',type='string',
        help=('Available levels are CRITICAL (3), ERROR (2), '
            'WARNING (1), INFO (0), DEBUG (-1)'),
        default='CRITICAL')
    parser_debug.add_option('-p','--printtostdout',action='store_true',
        default=False,help='Print all log messages to stdout')
    parser_debug.add_option('-l','--logfile',type='string',metavar='FILE',
        help=('Desired filename of log file output. Default '
            'is "'+ defaultlogfilename +'"')
        ,default=defaultlogfilename)
    #officially adds the debuggin option group
    parser.add_option_group(parser_debug) 
    options,args = parser.parse_args() #here's where the options get parsed

    try: #now try and get the debugging options
        loglevel = getattr(logging,options.debug)
    except AttributeError: #set the log level
        loglevel = {3:logging.CRITICAL,
                    2:logging.ERROR,
                    1:logging.WARNING,
                    0:logging.INFO,
                    -1:logging.DEBUG,
                    }[int(options.debug)]

    try:
        open(options.logfile,'w') #try and open the default log file
    except:
        print "Unable to open log file '%s' for writing." % options.logfile
        logging.debug(
            "Unable to open log file '%s' for writing." % options.logfile)

    setuplogging(loglevel,options.printtostdout,options.logfile)

    main(options)