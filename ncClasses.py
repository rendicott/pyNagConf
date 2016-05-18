import logging

class NagConfig(object):
    ''' Object to store Nagios configuration objects
    and has various methods like 'dump to text' and
    csv export, etc. 
    '''
    def __init__(self):
        self.nagObjs = [] # stores NagObj objects
    def gen_cfg_file(self,filename,expand=None):
        if expand is None:
            expand = False
        try:
            with open (filename,'w') as cf:
                for thing in self.nagObjs:
                    cf.write(thing.gen_nag_text(expand))
        except Exception as e:
            #logging.debug("Exception in NagConfig().gen_cfg_file(): " + str(e))
            pass

    def dump_stats(self):
        msg = ''
        msg += ("Number of NagObj: " + str(len(self.nagObjs)) + '\n')
        classes = []
        allclassifications = []
        count_classified = 0
        count_unclassified = 0
        for obj in self.nagObjs:
            if obj.classified.value:
                count_classified += 1
            elif not obj.classified.value:
                count_unclassified += 1

            allclassifications.append(obj.classification.value)
            if obj.classification.value not in classes:
                classes.append(obj.classification.value)
        for c in classes:
            msg += ("Count of %s = %s\n" % (c,allclassifications.count(c)))
        msg += ("Classified objects: %s\n" % str(count_classified))
        msg += ("Unclassified objects: %s\n" % str(count_unclassified))
        return(msg)
    def purge(self):
        ''' Runs through the self.nagObjs list
        and deletes objects with the 'deleteflag'
        '''

        self.nagObjs = [x for x in self.nagObjs if not x.deleteflag.value]

    def scrub_data(self):
        ''' Runs through the objects in self.nagObjs
        and removes unwanted characters from the property
        values.
        '''
        for obj in self.nagObjs:
            for attr in dir(obj):
                if '__' not in attr and 'instancemethod' not in str(type(getattr(obj,attr))):
                    val = getattr(getattr(obj,attr),'value')
                    try:
                        if 'str' in str(type(val)):
                            newval = val.rstrip()
                            newval = newval.rstrip(' ')
                            newval = newval.rstrip('\t')
                            setattr(getattr(obj,attr),'value',newval)
                    except:
                        pass


class NagObjSuperProp():
    ''' This object will be used as a property for several of the other
    NagObj's. e.g., type(NagObjHostGroup.service_description) = NagObjSuperProp
    This way each property can have it's own methods and properties. Want to do
    this so each property can track it's own history. 
    '''
    def __init__(self,value=None,explicitInheritance=None,donor=None):
        if value is None:
            value = ''
        if explicitInheritance is None:
            explicitInheritance = False
        if donor is None:
            donor = '*'
        self.donor = donor
        self.explicitInheritance = explicitInheritance 
        self.value = value # this is the primary value to be returned on most calls
        self.inheritanceHistory = []
        self.set_history()
    def set_history(self):
        if self.value != '' and not self.explicitInheritance:
            self.inheritanceHistory.append('EXPLICIT_DIRECT')
        elif self.value == '':
            self.inheritanceHistory.append('__')
        else:
            self.inheritanceHistory.append(self.donor)
    def return_history(self):
        return((self.inheritanceHistory))
    def __repr__(self):
        return(str(self.value))

                   
class NagObjFlex():
    ''' Class to hold Nagios configuration objects
    and their properties. This class cares little
    about what the object is and has very loose
    property definitions.
    '''
    
    def __init__(self,typestring):
        ''' init only requires a typestring (e.g., define SERVICE)
        '''
        self.classification = NagObjSuperProp('unclassified')
        self.typestring = NagObjSuperProp(typestring)
        self.classified = NagObjSuperProp(False) # by default we don't know what type this obj is
        self.deleteflag = NagObjSuperProp(False) # after we morph ourself we can flag ourself for deletion
        self.templateChain = NagObjSuperProp([])
        self.inheritanceLog = NagObjSuperProp([])
    def dumpself(self):
        msgs = []
        for attr in dir(self):
            if ('__' not in attr and 
                'instancemethod' not in str(type(getattr(self,attr)))
                ):
                msgs.append([attr,getattr(self,attr)])
        return(msgs)
    def dumpself_min(self):
        ''' Returns only the properties and values
        of the properties that have set values from default
        '''
        msgs = []
        for attr in self.display_filter():
            msgs.append([   attr,
                            getattr(getattr(self,attr),'value'),
                        ])
        return(msgs)
    def display_filter(self,transfer=None,display=None):
        ''' returns list of valid objects for
        display, e.g., filters out non-nagios properties
        '''

        ''' If we're trying to copy properties from
        this object to another object we want to 
        strip out non-transferrable properties like
        template name/use info.
        '''
        if transfer is None:
            transfer = False # default to false for display purposes
        if display is None:
            display = False
        returnlist = []
        if display:
            for attr in dir(self):
                val = getattr(self,attr)
                logging.debug("\t\tValue: '%s'" % val)
                if ('__' not in attr and 
                    'instancemethod' not in str(type(val)) and
                    'classification' not in attr and
                    'classified' not in attr and
                    'deleteflag' not in attr and
                    'templateChain' not in attr and
                    'inheritanceLog' not in attr
                    ):
                    logging.debug("\t\tValue: '%s'" % val)
                    returnlist.append(attr)
        else:
            for attr in dir(self):
                val = getattr(self,attr)
                if ('__' not in attr and 
                    'instancemethod' not in str(type(val)) and
                    'classification' not in attr and
                    'classified' not in attr and
                    'deleteflag' not in attr and
                    val != '' and
                    'typestring' not in attr and
                    'templateChain' not in attr and
                    'inheritanceLog' not in attr
                    ):
                    returnlist.append(attr)

            #filter even further
            if transfer:
                templist = []
                for attr in returnlist:
                    if (    attr != 'name' and
                            attr != 'use' and
                            attr != 'register'
                            ):
                        templist.append(attr)
                returnlist[:] = templist
        return(returnlist)
    def gen_nag_text(self,expand=None):
        ''' Generates nagios cfg file text
        from this object's properties.
        '''
        if expand is None:
            expand = True
        line_definition = "define {0} {{\n"
        fmt_propval = '    {0:<30}{1:<}\n'
        fmt_propval_tpl = '    {0:<30}{1:<90}{2:<}\n'
        line_end = "}\n"
        msg = ''
        msg += line_definition.format(self.typestring.value)
        if expand:
            for attr in self.display_filter():
                prop = attr
                val = getattr(self,prop).value
                #logging.debug("prop = '%s', val = '%s'" % (prop,val))
                if val == '':
                    pass
                else:
                    msg += fmt_propval.format(prop,val)
            msg += line_end
        else:
            for attr in self.display_filter():
                prop = attr
                val = getattr(self,prop).value
                firstHist = getattr(self,prop).inheritanceHistory[0]
                if 'EXPLICIT_DIRECT' in firstHist and val != '':
                    #logging.debug("prop = '%s', val = '%s'" % (prop,val))
                    msg += fmt_propval.format(prop,val)
            msg += line_end
        return(msg)

    def morph_to_classed(self):
        ''' Takes this object and attempts 
        to create a new object of type newclass
        '''
        workingobj = None
        #logging.debug("I'm inside NagObjFlex().morph_to_classed(): ")
        #logging.debug("NagObjFlex().morph_to_classed(): self.typestring.value = '%s'" % self.typestring.value)
        try:
            found = False
            for c in classDictionary:
                if c.get('typestring') == self.typestring.value:
                    #print("\tMatched self.typestring '%s' with : %s" % (self.typestring,c.get('typestring')))
                    workingobj = c.get('classname')() # instantiates a new class object
                    #print("\tCreated workingobj of type(): %s" % str(workingobj))
                    found = True
                    break
                else:
                    #print("Could not match self.typestring with a classDictionary: " + str(self.typestring))
                    found = False
            #logging.debug("NagObjFlex().morph_to_classed(): workingobj is of type: '%s'" % workingobj.classification.value)
            #logging.debug("NagObjFlex().morph_to_classed(): self.dumpself() = '%s'" % str(self.dumpself()))
            if workingobj is not None:
                #logging.debug("NagObjFlex().morph_to_classed(): workingobj must not be 'None'....")
                #print("\tworkingobj is not None, length of dumpself(): " + str(len(self.dumpself())))

                for propval in self.dumpself():
                    prop = propval[0]
                    val = propval[1]
                    #logging.debug("NagObjFlex().morph_to_classed(): prop = %s , val = %s" % (prop,val))
                    setattr(workingobj,prop,val)
                    workingobj.classification.value = self.typestring.value
                    workingobj.classified.value = True
                    self.deleteflag.value = True
            return(workingobj)
        except Exception as ex:
            #logging.debug("NagObjFlex().morph_to_classed(): Exception: '%s'" % str(ex))
            return(str(ex))
    def copy_from_obj(self,obj):
        ''' takes select properties from obj
        and copies to self. returns list of 
        key value pairs that were copied.
        '''
        pass
    def get_uid(self):
        ''' 
        returns some unique string for type of definition
        to make debugging easier. Templates have unique 'name'
        properties but the uid for a service might be the 
        command+host or something '''
        returnvalue = 'uid' # generic filler
        r = self.typestring.value
        if r == 'host':
            try:
                returnvalue = "%s_%s" % (r,self.host_name.value)
            except:
                pass
        elif r == 'service':
            try:
                returnvalue = "%s_%s___%s" % (r,self.host_name.value,self.service_description.value)
            except:
                returnvalue = "%s_%s___%s" % (r,self.host_name.value,self.display_name.value)
        else:
            returnvalue = r + "_genericuid_"
        return(returnvalue)
    def dict_format(self):
        '''
        returns keyed list of attribute:value
        '''
        results = []
        for attr in self.display_filter(display=True):
            results.append([   attr,
                            getattr(getattr(self,attr),'value'),
                        ])
        keyed = []
        for i,tup in enumerate(results):
            keyed.append({tup[0]:tup[1]})
        return(keyed)

class NagObjHost(NagObjFlex):
    ''' For making a clearly defined
    Nagios host object with set properties.
    '''

    def __init__(self):
        self.classification                 =   NagObjSuperProp('host')  # fixed classification string
        self.classified                     =   NagObjSuperProp(True)
        # Everything above here is nagconf internal usage
        #
        # Everything below here is Nagios inherited
        ##################################################################
        self.host_name                      =   NagObjSuperProp()      #host_name
        self.alias                          =   NagObjSuperProp()      #alias
        self.display_name                   =   NagObjSuperProp()      #display_name
        self.address                        =   NagObjSuperProp()      #address
        self.parents                        =   NagObjSuperProp()      #host_names
        self.hostgroups                     =   NagObjSuperProp()      #hostgroup_names
        self.check_command                  =   NagObjSuperProp()      #command_name
        self.initial_state                  =   NagObjSuperProp()      #[o,d,u]
        self.max_check_attempts             =   NagObjSuperProp()      ##
        self.check_interval                 =   NagObjSuperProp()      ##
        self.retry_interval                 =   NagObjSuperProp()      ##
        self.active_checks_enabled          =   NagObjSuperProp()      #[0/1]
        self.passive_checks_enabled         =   NagObjSuperProp()      #[0/1]
        self.check_period                   =   NagObjSuperProp()      #timeperiod_name
        self.obsess_over_host               =   NagObjSuperProp()      #[0/1]
        self.check_freshness                =   NagObjSuperProp()      #[0/1]
        self.freshness_threshold            =   NagObjSuperProp()      ##
        self.event_handler                  =   NagObjSuperProp()      #command_name
        self.event_handler_enabled          =   NagObjSuperProp()      #[0/1]
        self.low_flap_threshold             =   NagObjSuperProp()      ##
        self.high_flap_threshold            =   NagObjSuperProp()      ##
        self.flap_detection_enabled         =   NagObjSuperProp()      #[0/1]
        self.flap_detection_options         =   NagObjSuperProp()      #[o,d,u]
        self.process_perf_data              =   NagObjSuperProp()      #[0/1]
        self.retain_status_information      =   NagObjSuperProp()      #[0/1]
        self.retain_nonstatus_information   =   NagObjSuperProp()      #[0/1]
        self.contacts                       =   NagObjSuperProp()      #contacts
        self.contact_groups                 =   NagObjSuperProp()      #contact_groups
        self.notification_interval          =   NagObjSuperProp()      ##
        self.first_notification_delay       =   NagObjSuperProp()      ##
        self.notification_period            =   NagObjSuperProp()      #timeperiod_name
        self.notification_options           =   NagObjSuperProp()      #[d,u,r,f,s]
        self.notifications_enabled          =   NagObjSuperProp()      #[0/1]
        self.stalking_options               =   NagObjSuperProp()      #[o,d,u]
        self.notes                          =   NagObjSuperProp()      #note_string
        self.notes_url                      =   NagObjSuperProp()      #url
        self.action_url                     =   NagObjSuperProp()      #url
        self.icon_image                     =   NagObjSuperProp()      #image_file
        self.icon_image_alt                 =   NagObjSuperProp()      #alt_string
        self.vrml_image                     =   NagObjSuperProp()      #image_file
        self.statusmap_image                =   NagObjSuperProp()      #image_file
        self.twod_coords                    =   NagObjSuperProp()      #x_coord,y_coord
        self.threed_coords                  =   NagObjSuperProp()      #x_coord,y_coord,z_coord
    def __repr__(self):
        msg = ''
        msg += ("host.'%s'" % self.host_name.value)
        if msg == "host.''":
            msg = self.dumpself_min()
        return(msg)

class NagObjService(NagObjFlex):
    ''' For making a clearly defined
    Nagios service object with set properties.
    '''
    def __init__(self):
        self.classification                 =   NagObjSuperProp('service')  # fixed classification string
        self.classified                     =   NagObjSuperProp(True)
        # Everything above here is nagconf internal usage
        #
        # Everything below here is Nagios inherited
        ##################################################################
        self.host_name                      =   NagObjSuperProp()      #host_name
        self.hostgroup_name                 =   NagObjSuperProp()      #hostgroup_name
        self.service_description            =   NagObjSuperProp()      #service_description
        self.display_name                   =   NagObjSuperProp()      #display_name
        self.servicegroups                  =   NagObjSuperProp()      #servicegroup_names
        self.is_volatile                    =   NagObjSuperProp()      #[0/1]
        self.check_command                  =   NagObjSuperProp()      #command_name
        self.initial_state                  =   NagObjSuperProp()      #[o,w,u,c]
        self.max_check_attempts             =   NagObjSuperProp()      ##
        self.check_interval                 =   NagObjSuperProp()      ##
        self.retry_interval                 =   NagObjSuperProp()      ##
        self.normal_check_interval          =   NagObjSuperProp()      ##
        self.active_checks_enabled          =   NagObjSuperProp()      #[0/1]
        self.passive_checks_enabled         =   NagObjSuperProp()      #[0/1]
        self.parallelize_check              =   NagObjSuperProp()      #[0/1]
        self.check_period                   =   NagObjSuperProp()      #timeperiod_name
        self.obsess_over_service            =   NagObjSuperProp()      #[0/1]
        self.check_freshness                =   NagObjSuperProp()      #[0/1]
        self.freshness_threshold            =   NagObjSuperProp()      ##
        self.event_handler                  =   NagObjSuperProp()      #command_name
        self.event_handler_enabled          =   NagObjSuperProp()      #[0/1]
        self.low_flap_threshold             =   NagObjSuperProp()      ##
        self.high_flap_threshold            =   NagObjSuperProp()      ##
        self.flap_detection_enabled         =   NagObjSuperProp()      #[0/1]
        self.flap_detection_options         =   NagObjSuperProp()      #[o,w,c,u]
        self.process_perf_data              =   NagObjSuperProp()      #[0/1]
        self.retain_status_information      =   NagObjSuperProp()      #[0/1]
        self.retain_nonstatus_information   =   NagObjSuperProp()      #[0/1]
        self.notification_interval          =   NagObjSuperProp()      ##
        self.first_notification_delay       =   NagObjSuperProp()      ##
        self.notification_period            =   NagObjSuperProp()      #timeperiod_name
        self.notification_options           =   NagObjSuperProp()      #[w,u,c,r,f,s]
        self.notifications_enabled          =   NagObjSuperProp()      #[0/1]
        self.contacts                       =   NagObjSuperProp()      #contacts
        self.contact_groups                 =   NagObjSuperProp()      #contact_groups
        self.stalking_options               =   NagObjSuperProp()      #[o,w,u,c]
        self.notes                          =   NagObjSuperProp()      #note_string
        self.notes_url                      =   NagObjSuperProp()      #url
        self.action_url                     =   NagObjSuperProp()      #url
        self.icon_image                     =   NagObjSuperProp()      #image_file
        self.icon_image_alt                 =   NagObjSuperProp()      #alt_string
        self.failure_prediction_enabled     =   NagObjSuperProp()      ##
        self.retry_check_interval           =   NagObjSuperProp()      ##
    def __repr__(self):
        msg = ''
        if self.hostgroup_name.value == '':
            msg += ("service.%s.'%s'" % (self.host_name.value,self.service_description.value) )
            msg += ("\n\r\t\t\t\tHOSTGROUP_NAME: '%s'" % self.hostgroup_name.value)
        else:
            print("Doing the hostgroup name....")
            msg += ("service.%s.'%s'" % (self.hostgroup_name.value,self.service_description.value) )
        if msg == "service..''":
            msg = self.dumpself_min()
        return(msg)

class NagObjServiceGroup(NagObjFlex):
    ''' For making a clearly defined
    Nagios servicegroup object with set properties.
    '''
    def __init__(self):
        self.classification                 =   NagObjSuperProp('servicegroup')  # fixed classification string
        self.classified                     =   NagObjSuperProp(True)
        # Everything above here is nagconf internal usage
        #
        # Everything below here is Nagios inherited
        ##################################################################
        self.servicegroup_name       =   NagObjSuperProp()      #servicegroup_name
        self.alias                   =   NagObjSuperProp()      #alias
        self.members                 =   NagObjSuperProp()      #services
        self.servicegroup_members    =   NagObjSuperProp()      #servicegroups
        self.notes                   =   NagObjSuperProp()      #note_string
        self.notes_url               =   NagObjSuperProp()      #url
        self.action_url              =   NagObjSuperProp()      #url


class NagObjContact(NagObjFlex):
    ''' For making a clearly defined
    Nagios contact object with set properties.
    '''
    def __init__(self):
        self.classification                 =   NagObjSuperProp('contact')  # fixed classification string
        self.classified                     =   NagObjSuperProp(True)
        # Everything above here is nagconf internal usage
        #
        # Everything below here is Nagios inherited
        ##################################################################
        self.contact_name                     =   NagObjSuperProp()      #contact_name
        self.alias                            =   NagObjSuperProp()      #alias
        self.contactgroups                    =   NagObjSuperProp()      #contactgroup_names
        self.host_notifications_enabled       =   NagObjSuperProp()      #[0/1]
        self.service_notifications_enabled    =   NagObjSuperProp()      #[0/1]
        self.host_notification_period         =   NagObjSuperProp()      #timeperiod_name
        self.service_notification_period      =   NagObjSuperProp()      #timeperiod_name
        self.host_notification_options        =   NagObjSuperProp()      #[d,u,r,f,s,n]
        self.service_notification_options     =   NagObjSuperProp()      #[w,u,c,r,f,s,n]
        self.host_notification_commands       =   NagObjSuperProp()      #command_name
        self.service_notification_commands    =   NagObjSuperProp()      #command_name
        self.email                            =   NagObjSuperProp()      #email_address
        self.pager                            =   NagObjSuperProp()      #pager_number or pager_email_gateway
        self.addressx                         =   NagObjSuperProp()      #additional_contact_address
        self.can_submit_commands              =   NagObjSuperProp()      #[0/1]
        self.retain_status_information        =   NagObjSuperProp()      #[0/1]
        self.retain_nonstatus_information     =   NagObjSuperProp()      #[0/1]


class NagObjCommand(NagObjFlex):
    ''' For making a clearly defined
    Nagios command object with set properties.
    '''
    def __init__(self):
        self.classification                 =   NagObjSuperProp('command')  # fixed classification string
        self.classified                     =   NagObjSuperProp(True)
        # Everything above here is nagconf internal usage
        #
        # Everything below here is Nagios inherited
        ##################################################################
        self.command_name        =   NagObjSuperProp()    #command_name
        self.command_line        =   NagObjSuperProp()    #command_line

class NagObjTimePeriod(NagObjFlex):
    ''' For making a clearly defined
    Nagios timeperiod object with set properties.
    '''
    def __init__(self):
        self.classification                 =   NagObjSuperProp('timeperiod')  # fixed classification string
        self.classified                     =   NagObjSuperProp(True)
        # Everything above here is nagconf internal usage
        #
        # Everything below here is Nagios inherited
        ##################################################################
        self.timeperiod_name =   NagObjSuperProp()   #timeperiod_name
        self.alias           =   NagObjSuperProp()   #alias
        self.exclude         =   NagObjSuperProp()   #[timeperiod1,timeperiod2,...,timeperiodn]
        #self.[weekday]   timeranges
        #self.[exception] timeranges
        ''' E.g.,
        self.sunday      =   '00:00-24:00'                 ; Every Sunday of every week
        self.monday      =   '00:00-09:00,17:00-24:00'     ; Every Monday of every week
        self.tuesday     =   '00:00-09:00,17:00-24:00'     ; Every Tuesday of every week
        self.wednesday   =   '00:00-09:00,17:00-24:00'     ; Every Wednesday of every week
        self.thursday    =   '00:00-09:00,17:00-24:00'     ; Every Thursday of every week
        self.friday      =   '00:00-09:00,17:00-24:00'     ; Every Friday of every week
        self.saturday    =   '00:00-24:00'                 ; Every Saturday of every week
        '''

class NagObjServiceEscalation(NagObjFlex):
    ''' For making a clearly defined
    Nagios serviceescalation object with set properties.
    '''
    def __init__(self):
        self.classification                 =   NagObjSuperProp('serviceescalation')  # fixed classification string
        self.classified                     =   NagObjSuperProp(True)
        # Everything above here is nagconf internal usage
        #
        # Everything below here is Nagios inherited
        ##################################################################
        self.host_name              =   NagObjSuperProp()      #host_name
        self.hostgroup_name         =   NagObjSuperProp()      #hostgroup_name
        self.service_description    =   NagObjSuperProp()      #service_description
        self.contacts               =   NagObjSuperProp()      #contacts
        self.contact_groups         =   NagObjSuperProp()      #contactgroup_name
        self.first_notification     =   NagObjSuperProp()      ##
        self.last_notification      =   NagObjSuperProp()      ##
        self.notification_interval  =   NagObjSuperProp()      ##
        self.escalation_period      =   NagObjSuperProp()      #timeperiod_name
        self.escalation_options     =   NagObjSuperProp()      #[w,u,c,r]
    def __repr__(self):
        if self.hostgroup_name.value == '':
            return("serviceescalation.%s.'%s'" % (self.host_name.value,self.service_description.value) )
        else:
            return("serviceescalation.%s.'%s'" % (self.hostgroup_name.value,self.service_description.value) )

class NagObjHostGroup(NagObjFlex):
    ''' For making a clearly defined
    Nagios hostgroup object with set properties.
    '''
    def __init__(self):
        self.classification                 =   NagObjSuperProp('hostgroup')  # fixed classification string
        self.classified                     =   NagObjSuperProp(True)
        # Everything above here is nagconf internal usage
        #
        # Everything below here is Nagios inherited
        ##################################################################
        self.hostgroup_name       =   NagObjSuperProp()      #hostgroup_name
        self.alias                =   NagObjSuperProp()      #alias
        self.members              =   NagObjSuperProp()      #hosts
        self.hostgroup_members    =   NagObjSuperProp()      #hostgroups
        self.notes                =   NagObjSuperProp()      #note_string
        self.notes_url            =   NagObjSuperProp()      #url
        self.action_url           =   NagObjSuperProp()      #url

class NagObjHostExtInfo(NagObjFlex):
    ''' For making a clearly defined
    Nagios hostextinfo object with set properties.
    '''
    def __init__(self):
        self.classification                 =   NagObjSuperProp('hostextinfo')  # fixed classification string
        self.classified                     =   NagObjSuperProp(True)
        # Everything above here is nagconf internal usage
        #
        # Everything below here is Nagios inherited
        ##################################################################
        self.host_name          =   NagObjSuperProp()      #netware1
        self.notes              =   NagObjSuperProp()      #This is the primary Netware file server
        self.notes_url          =   NagObjSuperProp()      #http://webserver.localhost.localdomain/hostinfo.pl?host=netware1
        self.icon_image         =   NagObjSuperProp()      #novell40.png 
        self.icon_image_alt     =   NagObjSuperProp()      #IntranetWare 4.11
        self.vrml_image         =   NagObjSuperProp()      #novell40.png
        self.statusmap_image    =   NagObjSuperProp()      #novell40.gd2
        self.twod_coords        =   NagObjSuperProp()      #100,250
        self.threed_coords      =   NagObjSuperProp()      #100.0,50.0,75.0

class NagObjHostEscalation(NagObjFlex):
    ''' For making a clearly defined
    Nagios hostescalation object with set properties.
    '''
    def __init__(self):
        self.classification                 =   NagObjSuperProp('hostescalation')  # fixed classification string
        self.classified                     =   NagObjSuperProp(True)
        # Everything above here is nagconf internal usage
        #
        # Everything below here is Nagios inherited
        ##################################################################
        self.host_name              =   NagObjSuperProp()      #host_name
        self.hostgroup_name         =   NagObjSuperProp()      #hostgroup_name
        self.contacts               =   NagObjSuperProp()      #contacts
        self.contact_groups         =   NagObjSuperProp()      #contactgroup_name
        self.first_notification     =   NagObjSuperProp()      ##
        self.last_notification      =   NagObjSuperProp()      ##
        self.notification_interval  =   NagObjSuperProp()      ##
        self.escalation_period      =   NagObjSuperProp()      #timeperiod_name
        self.escalation_options     =   NagObjSuperProp()      #[d,u,r]
    def __repr__(self):
        if self.hostgroup_name.value == '':
            try:
                return("hostscalation.%s.'%s'" % (self.host_name.value,self.contact_groups.value) )
            except:
                pass
        else:
            try:
                return("hostescalation.%s.'%s'" % (self.hostgroup_name.value,self.contact_groups.value) )
            except:
                pass

class NagObjContactGroup(NagObjFlex):
    ''' For making a clearly defined
    Nagios contactgroup object with set properties.
    '''
    def __init__(self):
        self.classification                 =   NagObjSuperProp('contactgroup')  # fixed classification string
        self.classified                     =   NagObjSuperProp(True)
        # Everything above here is nagconf internal usage
        #
        # Everything below here is Nagios inherited
        ##################################################################
        self.contactgroup_name      =   NagObjSuperProp()      #contactgroup_name
        self.alias                  =   NagObjSuperProp()      #alias
        self.members                =   NagObjSuperProp()      #contacts
        self.contactgroup_members   =   NagObjSuperProp()      #contactgroups

''' Used for retrieving the type of custom object
we want to create on the fly from a string.
'''
classDictionary = [
    {'classname'    :   NagConfig,                 'typestring' : 'config'},
    {'classname'    :   NagObjFlex,                'typestring' : 'flex'},
    {'classname'    :   NagObjHost,                'typestring' : 'host'},
    {'classname'    :   NagObjService,             'typestring' : 'service'},
    {'classname'    :   NagObjServiceGroup,        'typestring' : 'servicegroup'},
    {'classname'    :   NagObjContact,             'typestring' : 'contact'},
    {'classname'    :   NagObjCommand,             'typestring' : 'command'},
    {'classname'    :   NagObjTimePeriod,          'typestring' : 'timeperiod'},
    {'classname'    :   NagObjServiceEscalation,   'typestring' : 'serviceescalation'},
    {'classname'    :   NagObjHostGroup,           'typestring' : 'hostgroup'},
    {'classname'    :   NagObjHostExtInfo,         'typestring' : 'hostextinfo'},
    {'classname'    :   NagObjHostEscalation,      'typestring' : 'hostescalation'},
    {'classname'    :   NagObjContactGroup,        'typestring' : 'contactgroup'},
]
