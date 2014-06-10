import math

'''
#PUT THE PROPOSAL NUMBER IN THE GROUP STRUCTURE
Node attributes to add:
self.state
# Proposer attributes:

# Acceptor attributes
self.n_int #dictionary of nightest prepare requests responded to hashed on the key
self.acced = {} #dictionary of tuples values accepted hashed on key, (value, n)

# Proposer attributes
self.accs = [m for m in self.group.members if m != self.name] #these are the members of the group that are not the leader
self.proposals = {} #dictionary of proposals
self.promises = {} #lists of promises hashed on p_num
self.rejects = {} #(value, n) of rejected msgs hashed by n
self.accepts = {} #(value, n) of accepted msgs hashed by n
self.props_accepted = {} #concensus values indexed by msg.n, (proposed, accepted) tuples
self.redirects = {} #dictionary of dictionaries keys key dictionaries n key for second layer values are n

'''
def make_paxos_msg(typ, dst, src, key, value, p_num, prior_proposal):
    return {"type": typ, "destination": dst, "source": src, "key": key, "value": value, 
            "p_num": p_num, "prior_proposal": prior_proposal}

def handle_paxos(msg):
    majority = math.ceil(len(self.group.members) / 2)
    typ = msg["type"]
    key = msg["key"]
    n = msg["p_num"]
    self.accs = [m for m in self.group.members if m != self.name]
    if self.group.leader == self.name:
        if typ == "PROPOSE":        
            if self.group.p_num not in self.proposals:
                self.proposals[self.group.p_num] = msg["value"]
            for member in self.accs:
                new_msg = make_paxos_msg("PREPARE", [member], [self.name], key, msg["value"], self.group.p_num, None)
                self.req.send_json(new_msg)
            self.promises[self.group.p_num] = []
            self.group.p_num += 1

        elif typ == "PROMISE":
            if n not in self.promises:
                self.promises[n] = [] #this actually should be an error
            if (msg["prior_proposal"]):
                self.promises[n].append(msg["prior_proposal"])
            else:
                self.promises[n].append((msg["value"], n))

            if (len(self.promises[n]) == majority):
                pick_tup = sorted(self.promises[n], key-lambda x: x[1])[0]
                
                for member in self.accs:
                    new_msg = make_paxos_msg("ACCEPT", [member], [self.name], key, msg["value"], n, None)
                    self.req.send_json(new_msg)
                
        elif typ == "REJECTED":
            if n in self.rejects:
                self.rejects[n].append((msg["value"], n))
            else:
                self.rejects[n] = [(msg["value"], n)]

            if (len(self.rejects[n]) == majority):
                if self.group.p_num not in self.proposals: 
                    self.proposals[self.group.p_num] = msg["value"]
                for member in self.accs:
                    new_msg = make_paxos_msg("PREPARE", [member], [self.name], key, msg["value"], self.group.p_num, None)
                    self.req.send_json(new_msg)
                self.promises[self.group.p_num] = []
                self.group.p_num += 1
                
        elif typ == "ACCEPTED":
            if n in self.accepts:
                self.accepts[n].append((msg["value"], n))
            else:
                self.accepts[n] = [(msg["value"], n)]

            if (len(self.accepts[n]) == majority):
                if n not in self.props_accepted:
                    self.props_accepted[msg.n] = (self.proposals[n], msg["value"])
                    if key == "START":
                        self.req.send_json({"type": "START_PAXOSED", "destination": [self.group.leader], 
                                            "source": [self.name], "value": msg["value"], "key": key})
                    elif key == "READY":
                        self.req.send_json({"type": "READY_PAXOSED", "destination": [self.group.leader], 
                                            "source": [self.name], "value": msg["value"], "key": key})
                    elif key == "YES":
                        self.req.send_json({"type": "YES_PAXOSED", "destination": [self.group.leader], 
                                            "source": [self.name], "value": msg["value"], "key": key})
                    else:
                        for member in self.accs:
                            new_msg = make_paxos_msg("LEARN", [member], [self.name], key, msg["value"], n, None)
                            self.req.send_json(new_msg)
                        
        elif typ == "REDIRECT":
            if key not in self.redirects:
                self.redirects[key] = []
            if n not in self.redirects[key]:
                self.redirects[key].append(n)
                new_msg = make_paxos_msg("PROPOSE", msg["source"], [self.name], key, msg["value"], n, None)
        else:
            print "This is not the typ eof message a proposer should be recieving"
    else:
        if typ == "PREPARE":
            self.group.p_num += 1
            if key not in self.n_int:
                self.n_int[msg.key] = -1 #initialize
            if n >= self.n_int[key]:
                if key in self.acced: # proposals that have been accepted for that key
                    high_p = sorted(self.acced[key], key=lambda x: x[1])[-1]
                    self.n_int[msg.key] = high_p[1] #send the latest (greatest) n
                else:
                    high_p = None
                    self.n_int[key] = n
                new_msg = make_paxos_msg("PROMISE", msg["source"], [self.name], msg["value"], n, high_p)
                self.req.send_json(new_msg)
        elif typ == "ACCEPT":
            if self.n_int[key] <= n:
                new_msg = make_paxos_msg("ACCEPTED", msg["source"], [self.name], msg["value"], n, None) 
                if key not in self.acced:
                    self.acced[key] = []
                self.acced[key].append((msg["value"], n))
            else:
                new_msg = make_paxos_msg("REJECTED", msg["source"], self.name, msg["value"], n, None)
            self.req.send_json(new_msg)
                                      
        elif typ == "LEARN":
            if key == ELECTION_ID:
                self.group.leader = msg["value"]
                self.leaderLease = dt.now() + LEADER_LEASE_TIME
                del self.acced[ELECTION_ID]
            elif key == ADD_ID:
                pass
            elif key == "GROUPS":
                self.lgroup = msg["value"][0]
                self.group = msg["value"][1]
                self.rgroup = msg["value"][2]
           
            else:
                self.store[long(key)] = msg["value"]
        else:
            print "This is not the type of message an acceptor should be receiving"
