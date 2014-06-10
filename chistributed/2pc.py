   def handle_2pc(self, msg):



     typ = msg["type"]
     if typ == "START":
        #START PAXOS ON INTERPROCESS (keys: MERGE_REQ, MERGE_ID, SPLIT, value:START)
        #ONCE PAXOS FINISHED, SEND READY ( in )
        #BLOCK
       self.req.send_json({"parent" : msg["parent"] ,"destination": [self.group.leader], "type": "PROPOSE", "key": "START", "value": ,msg["value"]})

     elif typ == "START_PAXOSED":
      #IN LEARN PHASE, SEND_PAXOSED to LEADER
      #type start_paxosed, key start, value split,merge_id
       self.req.send_json({"parent" : msg["parent"] ,"destination": [self.group], "type": "LEARN", "key": "BLOCK", "value": msg["value"]})
       if msg["value"] == "SPLIT":
         new_msg = { "parent":msg["parent"] ,"type": "READY", "destination": [self.lgroup.leader], "source": [self.name], "key": "SPLIT", "value": "SPLIT"}
         self.req.send_json(new_msg)
         new_msg["destination"] = [self.rgroup.leader]
         self.req.send_json(new_msg)

       elif msg["key"] == "MERGE_ID":
         if len(self.group.members) + len(self.lgroup.members) < MAX_GROUP and len(self.lgroup.members) < len(self.rgroup.members):
           new_msg = { "parent":msg["parent"] ,"type": "READY", "destination": [self.rgroup.leader], "source": [self.name], "key": "MERGE_ID", "value": "READY"}
         elif len(self.group.members) + len(self.rgroup.members) < MAX_GROUP :
           new_msg = { "parent":msg["parent"] ,"type": "READY", "destination": [self.lgroup.leader], "source": [self.name], "key": "MERGE_ID", "value": "READY"}
         else:
          #dont merge
          #if blocked, unblock here
           return
         self.req.send_json(new_msg)

     ###############
     #### READY ####
     ###############
     elif typ == "READY":
         self.req.send_json({"parent" : msg["parent"] ,  "destination": [self.group.leader], "type": "PROPOSE", "key": "READY", "value": msg["value"]})

     elif typ == "READY_PAXOSED":

       if msg["key"] == "SPLIT":
         self.req.send_json({"parent" : msg["parent"] ,"destination": [self.group], "type": "LEARN", "key": "BLOCK", "value": "SPLIT"})
         response = { "parent":msg["parent"] ,"destination": msg["source"], "source": [self.name], "type" : "YES", "key": "SPLIT", "value": "SPLIT"}
       elif msg["key"] == "MERGE":
         self.req.send_json({"parent" : msg["parent"] ,"destination": [self.group], "type": "LEARN", "key": "BLOCK", "value": "MERGE"})
         if msg["value"] == "MERGE_ID":
           response = { "parent":msg["parent"] ,"destination": msg["source"], "source": [self.name], "type" : "YES", "key": "MERGE", "value": "MERGE_ID"}

         elif msg["value"] == "MERGE_REQ":
           response = { "parent":msg["parent"] ,"source": [self.name], "type" : "READY", "key": "MERGE", "value": "MERGE_FWD"}
           if msg["source"][0] == self.rgroup.leader:

             response["destination"] =  [self.lgroup.leader]
           elif msg["source"][0] == self.lgroup.leader:
             response["destination"] =  [self.rgroup.leader]
           else:
             print "not leader of either group?"
             return

         elif msg["value"] == "MERGE_FWD":
           response = { "parent":msg["parent"] ,"destination": msg["source"], "source": [self.name], "type" : "YES", "key": "MERGE", "value": "MERGE_FWD"}

           self.req.send_json(response)

    ###############
    #### YES ####
    ###############   

     elif typ == "YES":
      #type yes, key split,merge, val split,merge_id,merge_req,merge_fwd
       if msg["value"] == "MERGE_REQ":

         if msg["source"][0] == self.lgroup.leader:
           self.group = merge("left")
           self.lgroup = msg["newNeighbor"]
           neighbor = self.rgroup.leader
           which = "leftMerge"

         elif msg["source"][0] == self.rgroup.leader:
           self.group = merge("right")
           self.rgroup = msg["newNeighbor"]
           neighbor = self.lgroup.leader
           which = "rightMerge"
         else:
           print "NOT LEADER OF GROUP??"
           neighbor = None
           pass
  

         commit_msg = ({ "parent" : msg["parent"] , "destination": msg["source"], "type": "COMMIT", "key": "MERGE_REQ", "value": (self.lgroup,self.group,self.rgroup), "store": self.store})
         self.req.send_json(commit_msg)

         learn_msg = ({ "parent" : msg["parent"] ,"destination": self.group.members, "source" : [self.name], "type": "LEARN", "key": "GROUPS", "value": (self.lgroup,self.group,self.rgroup), "store": msg["store"]})
         self.req.send_json(learn_msg)

         neighbor_msg = ({ "parent" : msg["parent"] , "destination": [neighbor], "type": "COMMIT", "key": "MERGE_ID","which": which, "value": (self.group)})
         self.req.send_json(neighbor_msg)

         neighbor2_msg = ({ "parent" : msg["parent"] , "destination": [neighbor], "type": "COMMIT", "key": "MERGE_FWD","which": which, "value": (self.group)})
         self.req.send_json(neighbor2_msg)
         
       elif msg["key"] == "SPLIT":
         if "SPLIT" not in self.okays:
           self.okays["SPLIT"] = 1
         else:
           del self.okays["SPLIT"]
           self.req.send_json({"parent" : msg["parent"] ,"destination": [self.group.leader], "type": "PROPOSE", "key": "YES","value": msg["value"]})

       else:
         self.req.send_json({"parent" : msg["parent"] ,"destination": [self.group.leader], "type": "PROPOSE", "key": "YES","value": msg["value"]})

     elif typ == "YES_PAXOSED":
       if msg["key"] == "SPLIT":
         group1,group2 = self.handle_split()

         learn_msg1 = ({ "parent" : msg["parent"] ,"destination": group1.members, "source" : [self.name], "type": "LEARN", "key": "GROUPS", "value": (self.lgroup, group1 , group2), "store" : {}})
         learn_msg2 = ({ "parent" : msg["parent"] ,"destination": group2.members, "source" : [self.name], "type": "LEARN", "key": "GROUPS", "value": (group1, group2 , self.rgroup), "store" : {}})

         neighborL_msg = ({ "parent" : msg["parent"] , "destination": [self.lgroup.leader], "type": "COMMIT", "key": "SPLIT","which": "yourRight", "value": (group1)})
         neighborR_msg = ({ "parent" : msg["parent"] , "destination": [self.rgroup.leader], "type": "COMMIT", "key": "SPLIT","which": "yourLeft", "value": (group2)})

         self.req.send_json(learn_msg1)
         self.req.send_json(learn_msg2)
         self.req.send_json(neighborL_msg)
         self.req.send_json(neighborR_msg)

       elif msg["key"] == "MERGE":

         if msg["source"][0] == self.lgroup.leader:
           dest = self.rgroup.leader
           groupInfo = self.lgroup
         elif msg["source"][0] == self.rgroup.leader:
           dest = self.lgroup.leader
           groupInfo = self.rgroup
         else:
           print "ERROR LEADER NOT FOUND"
           return

         if msg["value"] == "MERGE_ID":
           new_msg = { "parent":msg["parent"] ,"type": "READY", "destination": [dest], "source": [self.name], "key": "MERGE", "value": "MERGE_REQ"}
           self.req.send_json(new_msg)
         elif msg["value"] == "MERGE_FWD":
           new_msg = { "parent":msg["parent"] ,"type": "YES", "destination": [dest], "source": [self.name], "key": "MERGE", 
                      "value": "MERGE_REQ", "newNeighbor" : groupInfo, "store" : self.store}
           self.req.send_json(new_msg)
                 

    #######################
    ###### NO & WAIT ######
    #######################
     elif typ == "NO" or typ == "WAIT":
       self.loop.add_timeout(time.time() + .5, lambda: self.req.send_json({ "parent":msg["parent"],"type": "START", "destination":[self.group.leader], 
                                                                           "source": [self.name], "key": msg["key"], "value": msg["value"]}))
    ################
    #### COMMIT ####
    ################
     elif typ == "COMMIT": 
       self.req.send_json({"parent" : msg["parent"] ,"destination": [self.group], "type": "LEARN", "key": "UNBLOCK"})
       if msg["key"] == "SPLIT":
          #response = { "parent":msg["parent"] ,"destination": msg["source"], "source": [self.name], "type" : "YES", "key": "SPLIT", "value": "SPLIT"}
         if msg["which"] == "yourRight":
           learn_msg1 = ({  "parent" : msg["parent"] ,"destination": self.group.members, "source" : [self.name], "type": "LEARN", 
                          "key": "GROUPS", "value": (self.lgroup, self.group , msg["value"]), "store" : {}})
         elif msg["which"] == "yourLeft":
           learn_msg1 = ({ "parent" : msg["parent"] ,"destination": self.group.members, "source" : [self.name], "type": "LEARN", 
                          "key": "GROUPS", "value": (msg["value"], self.group , self.rgroup), "store" : {}})
         else:
           print "SPLIT COMMIT ILLFORMED - which is messed"

       elif msg["key"] == "MERGE":

         if msg["value"] == "MERGE_ID":
           if which == "leftMerge":
             learn_msg = ({ "destination": self.group.members, "source" : [self.name], 
                           "type": "LEARN", "key": "GROUPS", "value": (msg["value"],self.group,self.rgroup), "store" : {}})
           elif which == "rightMerge":
             learn_msg = ({ "parent" : msg["parent"] ,"destination": self.group.members, "source" : [self.name], "type": "LEARN", 
                           "key": "GROUPS", "value": (self.lgroup, self.group, msg["value"]), "store" : {}})
           else:
             print "Commit illformed w/o which field"
             self.req.send_json(learn_msg)    

         elif msg["value"] == "MERGE_REQ":
           learn_msg = ({ "parent" : msg["parent"] ,"destination": self.group.members, "source" : [self.name], "type": "LEARN", 
                         "key": "GROUPS", "value": (msg["value"]), "store" : msg["store"]})
           self.req.send_json(learn_msg)       

         elif msg["value"] == "MERGE_FWD":
           if which == "rightMerge":
             learn_msg = ({ "parent" : msg["parent"] ,"destination": self.group.members, "source" : [self.name], "type": "LEARN", 
                           "key": "GROUPS", "value": (msg["value"],self.group,self.rgroup), "store" : {}})
           elif which == "leftMerge":
             learn_msg = ({  "parent" : msg["parent"] ,"destination": self.group.members, "source" : [self.name], "type": "LEARN", "key": "GROUPS", 
                           "value": (self.lgroup, self.group, msg["value"]), "store" : {}})
           else:
             print "Commit illformed w/o which field"
             self.req.send_json(learn_msg)
