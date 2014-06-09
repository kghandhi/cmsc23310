import math

'''
Node attributes to add:
self.state
# Proposer attributes:

# Acceptor attributes
self.n_int #dictionary of nightest prepare requests responded to hashed on the key
self.acced = {} #dictionary of tuples values accepted hashed on key, (value, n)

# Proposer attributes
self.accs = [m for m in self.group.members if m != self.name] #these are the members of the group that are not the leader
self.proposals = {} #dictionary of p
'''
def make_paxos_msg(typ, dst, src, key, value, p_num, prior_proposals):
    return {"type": typ, "destination": dst, "source": src, "key": key, "value": value, 
            "p_num": p_num, "prior_proposals": prior_proposals}

def handle_paxos(msg):
    majority = math.ceil(len(self.group.members) / 2)
    typ = msg["type"]
    key = msg["key"]
    n = msg["p_num"]
    if self.group.leader == self.name:
        if typ == "PROPOSE":
            pass
        elif typ == "PROMISE":
            pass
        elif typ == "REJECTED":
            pass
        elif typ == "ACCEPTED":
            pass
        elif typ == "REDIRECT":
            pass
        else:
            print "This is not the typ eof message a proposer should be recieving"
    else:
        if typ == "PREPARE":
            if key not in self.n_int:
                self.n_int[msg.key] = -1 #initialize
            if n >= self.n_int[key]:
                if key in self.acced: # proposals that have been accepted for that key
                    high_p = sorted(self.acced[key], key=lambda x: x[1])[-1]
                    self.n_int[msg.key] = high_p[1] #send the latest (greatest) n
                else:
                    high_p = None
                    self.n_int[key] = n
                new_msg = {"destination": msg["source"], "source" = [self.name], "p_num": n, "prior_proposals": high_p, 
                           "key": key, "value": msg["value"], "type": "PROMISE"}
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
            pass
        else:
            print "This is not the type of message an acceptor should be receiving"
