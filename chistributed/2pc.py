   def handle_2pc(self, msg):
     typ = msg["type"]

     ###############
     #### START ####
     ###############
     if typ == "START":
       # INPUT type "START" , dest leader , source name , key SPLIT/MERGE/ADD/DROP , value SPLIT/MERGE_ID/NAME/NAME
       self.req.send_json({"parent" : self.name ,"destination": [self.group], "type": "LEARN",
                               "key": "BLOCK", "value": msg["value"]})
       self.req.send_json({"parent" : self.name ,"destination": [self.group.leader], "type": "PROPOSE",
                               "key": "START", "value": msg["key"] , "who" : msg["value"]})
     
     #######################
     #### START_PAXOSED ####
     #######################
     elif typ == "START_PAXOSED":
      #INPUT type start_paxosed, key start, value split/merge/add/drop , who split/merge_id/name/name
       if msg["value"] == "SPLIT" or msg["key"] == "ADD" or msg["key"] == "DROP":
         new_msg = { "parent":msg["parent"] ,"type": "READY", "destination": [self.lgroup.leader],
                                 "source": self.name, "key": msg["value"], "value": msg["who"] }
         self.req.send_json(new_msg)
         new_msg["destination"] = [self.rgroup.leader]
         self.req.send_json(new_msg)

       ################
       #### MERGE #####
       ################
       elif msg["value"] == "MERGE":
         if len(self.group.members) + len(self.lgroup.members) < MAX_GROUP and len(self.lgroup.members) < len(self.rgroup.members):
           new_msg = { "parent":msg["parent"] ,"type": "READY", "destination": [self.rgroup.leader],
                                 "source": self.name, "key": "MERGE", "value": "MERGE_ID"}
         elif len(self.group.members) + len(self.rgroup.members) < MAX_GROUP :
           new_msg = { "parent":msg["parent"] ,"type": "READY", "destination": [self.lgroup.leader], 
                                 "source": self.name, "key": "MERGE", "value": "MERGE_ID" }
         else:
          #dont merge
          new_msg =({"parent" : self.name ,"destination": [self.group], "type": "LEARN", "key": "UNBLOCK", "value": msg["who"]})

         self.req.send_json(new_msg)

        else:
          print "unrecognized start_paxosed message",msg["type"]




     ###############
     #### READY ####
     ###############
     elif typ == "READY":
         # type READY , key split/merge/add/drop , value split/MERGE_ID/ / /name/name
         self.req.send_json({"parent" : msg["parent"] , "source": self.name, "destination": [self.group.leader], 
                             "type": "PROPOSE", "key": "READY", "value": msg["key"] , "who" : msg["value"]})
    
     #######################
     #### READY_PAXOSED ####
     #######################
     elif typ == "READY_PAXOSED":
       # type ready_paxosed, key ready , value split,merge_id/add/drop, who split/merge_id/merge_req/merge_id/name/name

       #########################
       #### SPLIT,ADD,DROP #####
       #########################
       if msg["key"] == "SPLIT" or msg["key"] == "ADD" or msg["key"] == "DROP":
         self.req.send_json({"parent" : msg["parent"] ,"source": self.name, "destination": [self.group.leader], 
                             "type": "LEARN", "key": "BLOCK", "value": msg["key"]})
         response = {"parent":msg["parent"] ,"destination": [msg["source"]], "source": self.name, 
                     "type" : "YES", "key": msg["key"], "value": msg["who"]}
       ################
       #### MERGE #####
       ################
       elif msg["key"] == "MERGE":
         self.req.send_json({"parent" : msg["parent"], "source": self.name, "destination": [self.group.leader], 
                             "type": "LEARN", "key": "BLOCK", "value": "MERGE"})
         ###################
         #### MERGE_ID #####
         ###################
         if msg["value"] == "MERGE_ID":
           response = { "parent":msg["parent"] ,"destination": [msg["source"]], "source": self.name, 
                        "type" : "YES", "key": "MERGE", "value": "MERGE_ID"}

         ####################
         #### MERGE_REQ #####
         ####################
         elif msg["value"] == "MERGE_REQ":
           response = {"parent":msg["parent"], "source": self.name, "type" : "READY", "key": "MERGE", "value": "MERGE_FWD"}
           if msg["source"] == self.rgroup.leader:

             response["destination"] =  [self.lgroup.leader]
           elif msg["source"] == self.lgroup.leader:
             response["destination"] =  [self.rgroup.leader]
           else:
             print "not leader of either group?"
             return

         ###################
         #### MERGE_FWD #####
         ###################
         elif msg["value"] == "MERGE_FWD":
           response = {"parent": msg["parent"] ,"destination": [msg["source"]], "source": self.name, 
                       "type" : "YES", "key": "MERGE", "value": "MERGE_FWD"}

           self.req.send_json(response)

    ###############
    ##### YES #####
    ###############   

     elif typ == "YES":
      #type yes, key split,merge, val split,merge_id,merge_req,merge_fwd

       ####################
       #### MERGE_REQ #####
       ####################
       if msg["value"] == "MERGE_REQ":

         if msg["source"] == self.lgroup.leader:
           self.group = merge("left")
           self.lgroup = msg["newNeighbor"]

           neighbor_id = self.rgroup.leader
           neighbor_fwd = msg["newNeighbor"]
           which = "leftMerge"

         elif msg["source"] == self.rgroup.leader:
           self.group = merge("right")
           self.rgroup = msg["newNeighbor"]
           neighbor_id = self.lgroup.leader
           neighbor_fwd = msg["newNeighbor"]
           which = "rightMerge"
         else:
           print "NOT LEADER OF GROUP??"
           neighbor = None
  
         commit_msg = ({ "parent": msg["parent"] , "destination": [msg["source"]], 
                         "source": self.name, "type": "COMMIT", "key": "MERGE_REQ", 
                         "value": (self.lgroup,self.group,self.rgroup), "store": self.store})
         self.pending_reqs.append( ("commit", commit_msg["key"], commit_msg["value"], commit_msg["destination"][0] ) )
         self.req.send_json(commit_msg)

         learn_msg = ({"parent": msg["parent"] ,"destination": self.group.members, "source" : self.name, 
                       "type": "LEARN", "key": "GROUPS", 
                       "value": (self.lgroup,self.group,self.rgroup), "store": msg["store"]})
         self.req.send_json(learn_msg)

         neighbor_msg = ({"parent": msg["parent"] , "destination": [neighbor_id.leader], "source": self.name,
                          "type": "COMMIT", "key": "MERGE_ID", "which": which, "value": (self.group)})
         self.pending_reqs.append( ("commit", neighbor_msg["key"], neighbor_msg["value"], neighbor_msg["destination"] ) )
         self.req.send_json(neighbor_msg)

         neighbor2_msg = ({"parent": msg["parent"] , "source": self.name, "destination": [neighbor_fwd.leader], 
                           "type": "COMMIT", "key": "MERGE_FWD","which": which, "value": (self.group)})
         self.pending_reqs.append( ("commit", neighbor_msg2["key"], neighbor_msg2["value"], neighbor_msg2["destination"] ) )
         self.req.send_json(neighbor2_msg)
       #########################
       #### SPLIT,ADD,DROP #####
       #########################         
       elif msg["key"] == "SPLIT" or msg["key"] == "ADD" or msg["key"] == "DROP":
         if msg["key"] not in self.okays:
           self.okays[ msg["key"] ] = 1
         else:
           del self.okays[ msg["key"] ]
           self.req.send_json({"parent": msg["parent"], "source": self.name, "destination": [self.group.leader], 
                               "type": "PROPOSE", "key": "YES","value": msg["key"], "who" : msg["value"]})
       else:
         self.req.send_json({"parent": msg["parent"], "source": self.name, "destination": [self.group.leader], 
                               "type": "PROPOSE", "key": "YES","value": msg["key"], "who" : msg["value"]})

     #######################
     ####  YES_PAXOSED  ####
     #######################
     elif typ == "YES_PAXOSED":
       # type yes_paxosed, key ready , value split,merge_id/add/drop, who split/merge_id/merge_req/merge_id/name/name
       ################
       #### SPLIT #####
       ################
       if msg["key"] == "SPLIT":
         group1, group2 = self.handle_split()

         learn_msg1 = ({"parent": msg["parent"], "destination": group1.members, "source" : self.name, 
                        "type": "LEARN", "key": "GROUPS", "value": (self.lgroup, group1 , group2), "store" : {}})
         learn_msg2 = ({"parent": msg["parent"], "destination": group2.members, "source" : self.name, 
                        "type": "LEARN", "key": "GROUPS", "value": (group1, group2 , self.rgroup), "store" : dict()})

         neighborL_msg = ({"parent": msg["parent"] , "destination": [self.lgroup.leader], "source": self.name,
                           "type": "COMMIT", "key": "SPLIT","which": "yourRight", "value": (group1)})
         self.pending_reqs.append( ("commit", neighborL_msg["key"], neighborL_msg["value"], neighborL_msg["destination"] ) )
         neighborR_msg = ({"parent": msg["parent"] , "destination": [self.rgroup.leader], "source": self.name,
                           "type": "COMMIT", "key": "SPLIT","which": "yourLeft", "value": (group2)})
         self.pending_reqs.append( ("commit", neighborR_msg["key"], neighborR_msg["value"], neighborR_msg["destination"] ) )

         self.req.send_json(learn_msg1)
         self.req.send_json(learn_msg2)
         self.req.send_json(neighborL_msg)
         self.req.send_json(neighborR_msg)
       ################
       #### ADD  ######
       ################
       elif msg["key"] == "ADD":

        newGroup = Group(self.group.key_range, self.group.leader, (self.group.members + [msg["who"]]), self.group.p_num)

        learn_msg = ({"parent": msg["parent"], "destination": newGroup.members, "source" : self.name, 
                        "type": "LEARN", "key": "ADD_SELF", "value": (self.lgroup,newGroup,self.rgroup), "store" : self.store)

        neighborL_msg = ({"parent": msg["parent"] , "destination": [self.lgroup.leader], "source": self.name,
                           "type": "COMMIT", "key": "ADD_OTHER","which": "yourRight", "value": msg["who"] })
        self.pending_reqs.append( ("commit", neighborL_msg["key"], neighborL_msg["value"], neighborL_msg["destination"] ) )

        neighborR_msg = ({"parent": msg["parent"] , "destination": [self.rgroup.leader], "source": self.name,
                           "type": "COMMIT", "key": "ADD_OTHER","which": "yourLeft", "value": msg["who"] })
        self.pending_reqs.append( ("commit", neighborR_msg["key"], neighborR_msg["value"], neighborR_msg["destination"] ) )

        self.req.send_json(learn_msg)
        self.req.send_json(neighborL_msg)
        self.req.send_json(neighborR_msg)
       ################
       ##### DROP #####
       ################
       elif msg["key"] == "DROP":
        

        learn_msg = ({"parent": msg["parent"], "destination": self.group.members, "source" : self.name, 
                        "type": "LEARN", "key": "DROP_SELF", "value": msg["who"]})

        neighborL_msg = ({"parent": msg["parent"] , "destination": [self.lgroup.leader], "source": self.name,
                           "type": "COMMIT", "key": "DROP_OTHER","which": "yourRight", "value": msg["who"]})
        self.pending_reqs.append( ("commit", neighborL_msg["key"], neighborL_msg["value"], neighborL_msg["destination"] ) )


        neighborR_msg = ({"parent": msg["parent"] , "destination": [self.rgroup.leader], "source": self.name,
                           "type": "COMMIT", "key": "DROP_OTHER","which": "yourLeft", "value": msg["who"] })
        self.pending_reqs.append( ("commit", neighborR_msg["key"], neighborR_msg["value"], neighborR_msg["destination"] ) )

        self.req.send_json(learn_msg)
        self.req.send_json(neighborL_msg)
        self.req.send_json(neighborR_msg)
       ################
       #### MERGE #####
       ################
       elif msg["key"] == "MERGE":

         if msg["source"] == self.lgroup.leader:
           dest = self.rgroup.leader
           groupInfo = self.lgroup
         elif msg["source"] == self.rgroup.leader:
           dest = self.lgroup.leader
           groupInfo = self.rgroup
         else:
           print "ERROR LEADER NOT FOUND"
           return
         ###################
         #### MERGE_ID #####
         ###################
         if msg["value"] == "MERGE_ID":
           new_msg = {"parent": msg["parent"], "type": "READY", "destination": [dest], "source": self.name, 
                      "key": "MERGE", "value": "MERGE_REQ"}
           self.req.send_json(new_msg)
         ###################
         #### MERGE_FWD #####
         ###################
         elif msg["value"] == "MERGE_FWD":
           new_msg = {"parent": msg["parent"], "type": "YES", "destination": [dest], "source": self.name,
                      "key": "MERGE", "value": "MERGE_REQ", "newNeighbor" : groupInfo, "store" : self.store}
           self.req.send_json(new_msg)
                 

    #######################
    ###### NO & WAIT ######
    #######################
     elif typ == "NO" or typ == "WAIT":
       self.loop.add_timeout(time.time() + .5, 
                             lambda: self.req.send_json({"parent":msg["parent"], "type": "START", 
                                                         "destination":[self.group.leader], 
                                                         "source": self.name, "key": msg["key"], 
                                                         "value": msg["value"]}))
    ################
    #### COMMIT ####
    ################
     elif typ == "COMMIT":

       self.req.send_json({"parent":  msg["parent"] ,"destination": [ msg["source"] ], "source": self.name, 
                           "type": "COMMIT_ACK", "req": ("commit", msg["key"], msg["value"], neighborR_msg["destination"] )})

       self.req.send_json({"parent":  msg["parent"] ,"destination": [self.group], "source": self.name, 
                           "type": "LEARN", "key": "UNBLOCK"})

       ################
       #### SPLIT #####
       ################
       if msg["key"] == "SPLIT":
         if msg["which"] == "yourRight":
           learn_msg1 = ({"parent": msg["parent"] ,"destination": self.group.members, "source": self.name, "type": "LEARN", 
                          "key": "GROUPS", "value": (self.lgroup, self.group, msg["value"]), "store": dict()})
         elif msg["which"] == "yourLeft":
           learn_msg1 = ({"parent" : msg["parent"] ,"destination": self.group.members, "source" : self.name, "type": "LEARN", 
                          "key": "GROUPS", "value": (msg["value"], self.group , self.rgroup), "store" : dict()})
         else:
           print "SPLIT COMMIT ILLFORMED - which is messed"
       ################
       #### MERGE #####
       ################
       elif msg["key"] == "MERGE":

         ###################
         #### MERGE_ID #####
         ###################
         if msg["value"] == "MERGE_ID":
           if msg["which"] == "leftMerge":
             learn_msg = ({ "destination": self.group.members, "source" : self.name, "type": "LEARN", 
                            "key": "GROUPS", "value": (msg["value"],self.group,self.rgroup), "store": dict()})
           elif msg["which"] == "rightMerge":
             learn_msg = ({ "parent" : msg["parent"] ,"destination": self.group.members, "source" : self.name, "type": "LEARN", 
                           "key": "GROUPS", "value": (self.lgroup, self.group, msg["value"]), "store": dict()})
           else:
             print "Commit illformed w/o which field"
             self.req.send_json(learn_msg)    
         ####################
         #### MERGE_REQ #####
         ####################
         elif msg["value"] == "MERGE_REQ":
           learn_msg = ({"parent" : msg["parent"] ,"destination": self.group.members, "source" : self.name, "type": "LEARN", 
                         "key": "GROUPS", "value": (msg["value"]), "store" : msg["store"]})
           self.req.send_json(learn_msg)       
         ####################
         #### MERGE_FWD #####
         ####################
         elif msg["value"] == "MERGE_FWD":
           if msg["which"] == "rightMerge":
             learn_msg = ({"parent" : msg["parent"] ,"destination": self.group.members, "source" : self.name, "type": "LEARN", 
                           "key": "GROUPS", "value": (msg["value"],self.group,self.rgroup), "store": dict()})
           elif msg["which"] == "leftMerge":
             learn_msg = ({  "parent" : msg["parent"] ,"destination": self.group.members, "source" : self.name, 
                             "type": "LEARN", "key": "GROUPS", "value": (self.lgroup, self.group, msg["value"]), "store": dict()})
           else:
             print "Commit illformed w/o which field"
             self.req.send_json(learn_msg)
       #########################
       #### ADD/DROP_OTHER #####
       #########################
       elif msg["key"] == "ADD_OTHER" or msg["key"] == "DROP_OTHER":

          learn_msg = ({  "parent" : msg["parent"] ,"destination": self.group.members, "source" : self.name, 
                             "type": "LEARN", "key": msg["key"], "value": (msg["value"]). "which" : msg["which"] })
          self.req.send_json(learn_msg)