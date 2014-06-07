

def receive_msg(other, msg):
    '''
    types of messages: START, READY, YES, NO, COMMIT, DONE
    '''
    typ = msg['type']
    new_msg = { 'destination': [other], 'source': [self.name], 'key': msg['key'], 'value': msg['value']}
    if typ == "START":
        new_msg['type'] = 'READY'
    else:
        to_paxos = {'type': "PROPOSE", "destination": [self.name], 'source': None, 'key': msg['key'], "value": msg["value"]}
        if typ == "READY":
        #if the length of the members group isnt too long for merges, isnt too small for splits etc.
            self.req.send_json(to_paxos)
            #if we reached concensus, else 'NO'
            if self.proposer.props_accepted[msg["key"]]:
                new_msg['type'] = 'YES'
            else:
                mew_msg['type'] = 'NO'
            self.req.send_json(new_msg)
            
        elif typ == "YES":
            self.req.send_json(to_paxos)
            if self.proposer.props_accepted[msg["key"]]:
                for m in self.group.members:
                    self.req.send_json({"type": "LEARN", "destination": [m], "source": [self.name], "key": msg["key"], "value": msg["value"]})
            new_msg['type'] = 'COMMIT'
        elif typ == "COMMIT":
            self.req.send_json(to_paxos)
            if self.proposer.props_accepted[msg["key"]]:
                new_msg['type'] = "DONE"
                self.req.send_json(new_msg)
    #check if all the paxos worked
 
   
