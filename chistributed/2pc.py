## note about 2pc: I assume that in Paxos we learn the values and dont delete them for at least enough time for me to check
## them here. I couldnt figure out how to send the person wed want to respond to once learning a value, so i basically check 
## in the function if we reached concensus or not. THIS MAY BE DANGEROUS! BE WARNED>>>> 

def 2pc(msg):
    typ = msg["type"]
    response = {"destination": msg["source"], "source": [self.name], "key": msg["key"], "value": msg["value"]}
    if typ == "START":
        
        self.req.send_json({"destination": [self.group.leader], "type": "PROPOSE", "key": msg["key"], "value": "START"})
        if self.proposer.props_accepted[msg["key"]]:
            response = {"type": "READY", "destination": msg["source"], "source": [self.name], "key": msg["key"], "value": msg["value"]}
            self.req.send_json(response)

    elif typ == "READY":
        response = {"destination": msg["source"], "source": [self.name], "key": msg["key"], "value": msg["value"]}
        if msg["key"] != "MERGE_REQ":
            self.req.send_json({"type": "PROPOSE", "destination": [self.group.leader], "key": msg["key"], "value": "READY"})
            
            if self.proposer.props_accepted[msg["key"]]:
                response["type"] = "OK"
            else:
                response["type"] = "NO"
            self.req.send_json(response)
        else:
            new_msg = {"type": "READY", "key": "MERGE_FWD", "value": msg["value"], "source": [self.name]}
            if msg["source"] == [self.lgroup.leader]:
                new_msg["destination"] = self.rgroup.leader
            else:
                new_msg["destination"] = self.lgroup.leader
            self.req.send_json(new_msg)
            
    elif typ == "OK":
        response = {"destination": msg["source"], "source": [self.name], "key": msg["key"], "value": msg["value"]}
        if msg["key"] == "MERGE_FWD":
            #should I paxos here to decide to forward it as an okay? yes probably
            self.req.send_json({"type": "PROPOSE", "destination": [self.group.leader], "key": "MERGE_REQ", "value": "READY"})
            if self.proposer.props_acced[msg["key"]]:
                response["type"] = "OK"
                self.req.send_json(response)
        else:
            if msg["key"] == "MERGE_REQ" or msg["key"] == "MERGE_ID":
                if "MERGE" in self.okays:
                    self.okays["MERGE"].append((msg["key"], msg["source"][0]))
                else:
                    self.okays["MERGE"] = [(msg["key"], msg["source"][0])]
                if len(self.okays["MERGE"]) == 2:
                    to_merge = [x for x in self.okays["MERGE"] if x[0] == "MERGE_REQ"]
                    assert (len(to_merge) == 1)
                    if to_merge[1] == self.lgroup.leader:
                        v = self.handle_merge("left")
                     
                    elif to_merge[1] == self.rgroup.leader:
                        v = self.handle_merge("right")
                    self.okays["MERGE"] = []
            elif msg["key"] == "SPLIT_ID":
                self.okays["SPLIT"] += 1
                if self.okays["SPLIT"] == 2:
                    v = self.handle_split()
                    self.okays["SPLIT"] = 0
                    
                response["type"] = "COMMIT"
                response["value"] = v
                response["destination"] = [self.lgroup.leader]
                self.req.send_json(response)
                response["destination"] = [self.rgroup.leader]
                self.req.send_json(response)

    elif typ == "COMMIT":
        #when this is committed and its a merge, make sure to pass on a new left or right group in paxos with a propose message
        self.req.send_json({"type": "PROPOSE", "destination": [self.group.leader], "key": msg["key"], "value": msg["value"]})
 
   
    ##################################################
    #---------- Two Phase Commit Handling -----------#
    ##################################################

    #######################
    #### START + PAXOS ####
    #######################
  def handle_2pc(self, msg):
    typ = msg["type"]
    elif typ == "START":
        #START PAXOS ON INTERPROCESS (keys: MERGE_REQ, MERGE_ID, SPLIT, value:START)
        #ONCE PAXOS FINISHED, SEND READY ( in )
        #BLOCK
        self.req.send_json({"destination": [self.group.leader], "type": "PROPOSE", "key": "START", "value": ,msg["value"]})

    elif typ == "START_PAXOSED":
      #IN LEARN PHASE, SEND_PAXOSED to LEADER
      #type start_paxosed, key start, value split,merge_id

      if msg["value"] == "SPLIT_ID":
        new_msg = {"type": "READY", "destination": [self.lgroup.leader], "source": [self.name], "key": "SPLIT", "value": "SPLIT_ID"}
        self.req.send_json(new_msg)
        new_msg["destination"] = [self.rgroup.leader]
        self.req.send_json(new_msg)

      elif msg["key"] == "MERGE_ID":
        if len(self.group.members) + len(self.lgroup.members) < MAX_GROUP and len(self.lgroup.members) < len(self.rgroup.members):
           #new_msg1 = {"type": "READY", "destination": [self.lgroup.leader], "source": [self.name], "key": "MERGE_REQ", "value": "READY"}
           new_msg2 = {"type": "READY", "destination": [self.rgroup.leader], "source": [self.name], "key": "MERGE_ID", "value": "READY"}
        elif len(self.group.members) + len(self.rgroup.members) < MAX_GROUP :
           #new_msg1 = {"type": "READY", "destination": [self.rgroup.leader], "source": [self.name], "key": "MERGE_REQ", "value": "READY"}
           new_msg2 = {"type": "READY", "destination": [self.lgroup.leader], "source": [self.name], "key": "MERGE_ID", "value": "READY"}
        else:
          #dont merge
          return

        #self.req.send_json(new_msg1)
        self.req.send_json(new_msg2)

    elif typ == "READY":
      pass

    elif typ == "READY_PAXOSED":
      pass

    elif typ == "YES":
      #type yes, key split,merge, val split,merge_id,merge_req,merge_fwd
      if msg["key"] == "MERGE_REQ":
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
  

        learn_msg = ({"destination": self.group.members, "source" : [self.name], "type": "LEARN", "key": "GROUPS", "value": (self.lgroup,self.group,self.rgroup)})
        self.req.send_json(learn_msg)

        commit_msg = ({"destination": msg["source"], "type": "COMMIT", "key": "MERGE_REQ", "value": (self.lgroup,self.group,self.rgroup)})
        self.req.send_json(commit_msg)

        neighbor_msg = ({"destination": [neighbor], "type": "COMMIT", "key": "MERGE_ID","which": which, "value": (self.group)})
        self.req.send_json(neighbor_msg)

        neighbor2_msg = ({"destination": [neighbor], "type": "COMMIT", "key": "MERGE_FWD","which": which, "value": (self.group)})
        self.req.send_json(neighbor2_msg)

      else:
        self.req.send_json({"destination": [self.group.leader], "type": "PROPOSE", "key": "YES","value": msg["value"]})

    elif typ == "YES_PAXOSED":
      if msg["key"] == "SPLIT":
        ###############################33
        #################################33
        #################################
        # IF 2nd YES....
        # SEND LEFT NEIGHBOR LEFT GROUP
        # SEND RIGHT NEIGHBOR RIGHT GROUP
        # SPLIT AND UPDATE INTERNAL GROUPS
        pass
      elif msg["key"] == "MERGE_ID":
        new_msg = {"type": "READY", "destination": [self.lgroup.leader], "source": [self.name], "key": "MERGE", "value": "MERGE_REQ"}
        self.req.send_json(new_msg)

      elif msg["key"] == "MERGE_FWD":
        if msg["source"][0] == self.rgroup.leader:
          groupInfo = self.rgroup
          dest = self.lgroup.leader
        elif msg["source"][0] == self.lgroup.leader:
          groupInfo = self.lgroup
          dest = self.rgroup.leader
        else:
          #ERROR
          pass
        new_msg = {"type": "YES", "destination": [dest], "source": [self.name], "key": "MERGE", "value": "MERGE_REQ", "newNeighbor" : groupInfo}
        self.req.send_json(new_msg)


    ###############
    #### READY ####
    ###############
    elif typ == "READY":
      self.req.send_json({"destination": [self.group.leader], "type": "PROPOSE", "key": "READY", "value": msg["value"]})

    elif typ == "READY_PAXOSED":
        if msg["key"] == "SPLIT":
          response = {"destination": msg["source"], "source": [self.name], "type" : "YES", "key": "SPLIT", "value": "SPLIT"}
        elif msg["key"] == "MERGE":
          response = {"destination": msg["source"], "source": [self.name], "type" : "YES", "key": "MERGE", "value": msg["value"]}
      self.req.send_json(response) 

    #######################
    ###### NO & WAIT ######
    #######################
    elif typ == "NO" or typ == "WAIT":
      self.loop.add_timeout(time.time() + .5, lambda: self.req.send_json({"type": "START", "destination":[self.group.leader], "source": [self.name], "key": msg["key"], "value": msg["value"]}))
    ################
    #### COMMIT ####
    ################
    elif typ == "COMMIT":
        '''
        if msg["key"] == "SPLIT":
          response = {"destination": msg["source"], "source": [self.name], "type" : "YES", "key": "SPLIT", "value": "SPLIT"}
        elif msg["key"] == "MERGE_ID":
          response = {"destination": msg["source"], "source": [self.name], "type" : "YES", "key": "MERGE", "value": msg["value"]}
        elif msg["key"] == "MERGE_REQ":
          response = {"destination": msg["source"], "source": [self.name], "type" : "YES", "key": "MERGE", "value": "MERGE_REQ"}
        elif msg["key"] == "MERGE_FWD":
          response = {"destination": msg["source"], "source": [self.name], "type" : "YES", "key": "MERGE", "value": "MERGE_FWD"}
        self.req.send_json(response) 
        #when this is committed and its a merge, make sure to pass on a new left or right group in paxos with a propose message
        self.req.send_json({"type": "PROPOSE", "destination": [self.group.leader], "key": msg["key"], "value": msg["value"]})
        '''
    ################################################
    #--------------- UNKNOWN EVENT ----------------#
    ################################################
    else:
      self.req.send_json({'type': 'log', 'debug': {'event': 'unknown', 'node': self.name}})
