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
 
   
