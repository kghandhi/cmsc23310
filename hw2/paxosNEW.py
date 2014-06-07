from __future__ import division
import math


#TODO
#implement leader reapplys for leaderlease a couple secs
#   before lease expires
#nodes appy for leadership couple secs after lease ends
#   check diff b/w lease and now(), if now > lease apply
#                                   else delay
#upon learns, update group info
#upon election, leader 2PC his identity w/ neighbor leaders
#handle accept case in ACCEPTED in Proposer to...
#	2PC with neighbors about new leader
#	DO complicated things

from datetime import datetime as dt
from datetime import timedelta
# t = str(dt.now())
# dt.strptime( t , "%Y-%m-%d %H:%M:%S.%f")
# timedelta(seconds=20)

#Paxos propNum Dictionary key values
ELECTION_ID = "ELECTION_ID"
SPLIT_ID = "SPLIT_ID"
MERGE_ID = "MERGE_ID"
ADD_ID = "ADD_ID"
REMOVE_ID = "REMOVE_ID"
# + hashed keys (for groups keyspace)
# + nodes names (for add join)

#leader elections
LEADER_LEASE_TIME = timedelta(seconds=1)


proposal_id = 1

class EqualityMixin(object):
    def __eq__(self, other):
        for key, value in self.__dict__.items():
            if other.__dict__[key] != value:
                return False
        return True

def from_json(msg_frames): 
    #TODO: figure out if this should just be something we process in handle...
    assert len(msg_frames) == 3
    assert msg_frames[0] == self.name
    msg = json.loads(msg_frames[2])
    if msg["source"] and msg["destination"]:
        return Message(msg["value"], msg["key"], msg["type"], msg["source"][0], msg["destination"][0], msg["id"], msg["prior"])
    else:
        return Message(msg["value"], msg["key"], msg["type"], [], msg["destination"][0], msg["id"], msg["prior"])
  

class Message(EqualityMixin):
    def __init__(self, value, key, typ, src, dst, n, prior_proposal):
        self.value = value 
        self.key = key #election, actualKey, merge, split
        self.typ = typ #string PROPOSE, PREPARE, PROMISE, ACCEPT, ACCEPTED, REJECTED, REDIRECT
        self.src = src #tuple (P or A, ID)
        self.dst = dst #tuple (P or A, ID)
        self.n = n #proposal_id
        #the highest numbered prior proposal (val,n) or None
        self.prior_proposal = prior_proposal 

    def __repr__(self):
        FMT = "Message(value={}, typ={}, src={}, dst={}, n={}, prior_proposal={})"
        
        return FMT.format(self.value, self.typ, self.src, self.dst, 
                          self.n, self.prior_proposal)

    def to_json(self): #so we want self.dst.name to be the name of the node and self.src.name to be the name of the node
        return {"type": self.typ, "destination": [self.dst.name], "source": [self.src.name], "id" : self.n, "key": self.key, "value": self.value, "prior": self.prior_proposal}

    
    #this returns a string that should be printed in the simulate function w/time
    def print_msg(self):
        ret = ""
        if self.typ == "PROPOSE":
            ret += "    -> P%d  PROPOSE v=%d key=%s" %(self.dst[1], self.value, self.key)
        elif self.typ == "PREPARE":
            ret += " P%d -> A%d  PREPARE n=%d key=%s" %(self.src[1], self.dst[1], self.n, self.key)
        elif self.typ == "PROMISE":
            if self.prior_proposal != None:
                prop_s = "n={}, v={}".format(self.prior_proposal[1], self.prior_proposal[0])
            else:
                prop_s = self.prior_proposal
            ret += " A%d -> P%d  PROMISE n=%d key=%s (Prior: %s)" %(self.src[1], self.dst[1], self.n, self.key, prop_s)
        elif self.typ == "ACCEPT":
            ret += " P%d -> A%d  ACCEPT n=%d key=%s v=%d" %(self.src[1], self.dst[1], self.n, self.key, self.value)
        elif self.typ == "ACCEPTED":
            ret += " A%d -> P%d  ACCEPTED n=%d key=%s v=%d" %(self.src[1], self.dst[1], self.n, self.key, self.value)
        elif self.typ == "REJECTED":
            ret += " A%d -> P%d  REJECTED n=%d key=%s" %(self.src[1], self.dst[1], self.n, self.key)    
        elif self.typ == "LEARN":
            ret += " P%d -> A%d  LEARN n=%d key=%s" %(self.src[1], self.dst[1], self.n, self.key)
        elif self.typ == "REDIRECT":
            ret += "    -> P%d  REDIRECT n=%d key=%s to P%d" %(self.dst[1], self.n, self.key,self.src[1])
        return ret

#Adds message m to the end of the queue.
def queue_message(N, m):
    N.append(m)

#finds the first message m in the queue st m.src.failed 
def extract_message(N, accs, props): 
    for message in N:
        if message.src[0] == 'A':
            src = accs[message.src[1] - 1]
        else:
            src = props[message.src[1] - 1]
        if message.dst[0] == 'A':
            dst = accs[message.dst[1] - 1]
        else:
            dst = props[message.dst[1] - 1]
        
        if (src.failed == False) and (dst.failed == False):
            msg = message
            N.remove(msg)
            return msg
        
            
    return 0 #consider creating a length of message function 
           
class Proposer(object):
    def __init__(self, ID, accs):
        self.ID = ID
        self.failed = False
        self.accs = accs #list of acceptors
        self.promises = {} #keys are proposal_id, items are lists of promises for that id.
        self.rejects = {} # (msg.value, msg.n) of rejceted msgs indexed by n
        self.majority = math.ceil(len(self.accs) / 2)
        self.accepts = {} #(msg.value, msg.n) of accepted msgs indexed by n
        self.props_accepted = {} #concensus values indexed by msg.n, (proposed, accepted) tuples
        self.proposals = {} #dictionary of PROPOSE msgs => key, msg.n, value, msg.value
	self.redirects = {}
   
    def deliver_message(self, N, msg):
        global proposal_id
        if msg.typ == "PROPOSE":
            if proposal_id not in self.proposals:
                self.proposals[proposal_id] = msg.value
            #send prepare to all acceptors with the global proposal_id
            for c_a in self.accs:
                new_msg = Message(msg.value, msg.key, "PREPARE", ('P',self.ID), ('A',c_a.ID), proposal_id, None)
                queue_message(N, new_msg)
            self.promises[proposal_id] = []
            proposal_id += 1 
        
        elif msg.typ == "PROMISE":
            if msg.n not in self.promises:
                self.promises[msg.n] = [] #not actually necessary
            if (msg.prior_proposal): #if there is an accepted value, remember that
                self.promises[msg.n].append(msg.prior_proposal)
            else: #otherwise remember them agreeing to your value
                self.promises[msg.n].append((msg.value, msg.n))
            
            #once the majority have promised, take the value associated with 
            #greatest proposal_id and issue ACCEPT requests to everyone
            if (len(self.promises[msg.n]) == self.majority): 
                pick_tup = sorted(self.promises[msg.n], key=lambda x: x[1])[0]
               
                for c_a in self.accs:
                    new_msg = Message(pick_tup[0], msg.key, "ACCEPT", ('P', self.ID), ('A', c_a.ID), msg.n, None)
                    queue_message(N, new_msg)
        
        elif msg.typ == "REJECTED":
            if msg.n in self.rejects:
                self.rejects[msg.n].append((msg.value, msg.n))
            else:
                self.rejects[msg.n] = [(msg.value, msg.n)]

            #if the majoirty of responses are rejection, try again w/new n
            if (len(self.rejects[msg.n]) == self.majority):
                if proposal_id not in self.proposals:
                    self.proposals[proposal_id] = msg.value
                for c_a in self.accs:
                    new_msg = Message(msg.value, msg.key, "PREPARE", ('P', self.ID), ('A', c_a.ID), proposal_id, None)
                    queue_message(N, new_msg)
                self.promises[proposal_id] = []
                proposal_id += 1
        
        #once the majority respond with ACCEPTED, consensus is reached!
        elif msg.typ == "ACCEPTED":
            if msg.n in self.accepts:
                self.accepts[msg.n].append((msg.value, msg.n))
            else:
                self.accepts[msg.n] = [(msg.value, msg.n)]
            if (len(self.accepts[msg.n]) == self.majority):
                if msg.n not in self.props_accepted:
                    self.props_accepted[msg.n] = (self.proposals[msg.n], msg.value)
                    for c_a in self.accs:
                        new_msg = Message(msg.value, msg.key, "LEARN", ('P', self.ID), ('A', c_a.ID), proposal_id, None)
                        queue_message(N, new_msg)
		    #IF PASSED  VAL IS A "SET VAL"
		    #    ADJUST MY NODE.VALUES
		    #CHANGE LEADER, ETC
	elif msg.typ == "REDIRECT":
	    if msg.key not in self.redirects:
	    	self.redirects[msg.key] = []
	    if msg.n not in self.redirects[msg.key]:
	        self.redirects[msg.key].append(msg.n)
	        new_msg = Message(msg.value, msg.key, "PROPOSE", ('P', self.ID), msg.src, proposal_id, None)
	        queue_message(N,new_msg)
	else:
            print "This is not a type of message a Proposer should be receiving"
            

class Acceptor(object):
    def __init__(self, ID):
        self.ID = ID
        self.failed = False
        self.n_int = {} #the highest prepare request it has responded to
        self.acced = {} #list of tuples values accepted (value, n) 

        self.leader = None
        self.leaderLease = dt.now()

    def deliver_message(self, N, msg):
      if (msg.src[1] == self.leader) or (dt.now() > self.leaderLease): 
        if msg.typ == "PREPARE":    
                #if the new proposal has proposal_id >= the largest promised proposal
                if msg.key not in self.n_int:
                    self.n_int[msg.key] = -1
                
                if msg.n >= self.n_int[msg.key]:
                    if msg.key in self.acced: #if any other proposals have been accepted for that key
                        high_p = sorted(self.acced[msg.key], key=lambda x: x[1])[-1]
                        self.n_int[msg.key] = high_p[1] #send the latest (greatest n)
                    else:
                        high_p = None
                        self.n_int[msg.key] = msg.n
                    new_msg = Message(msg.value, msg.key, "PROMISE", ('A', self.ID), msg.src, msg.n, high_p)
                    queue_message(N, new_msg)

        elif msg.typ == "ACCEPT":
            #if the proposal number is <= the highest numbered poposal promised:
            if self.n_int[msg.key] <= msg.n:
                new_msg = Message(msg.value, msg.key, "ACCEPTED", ('A', self.ID), msg.src, msg.n, None)
		if msg.key not in self.acced:
		    self.acced[msg.key] = []

                self.acced[msg.key].append((msg.value, msg.n)) 

            else:
                new_msg = Message(msg.value, msg.key, "REJECTED", ('A', self.ID), msg.src, msg.n, None)
            queue_message(N, new_msg)

	elif msg.typ == "LEARN":
                if (msg.key == ELECTION_ID):
                    self.leader = msg.value
                    self.leaderLease = dt.now() + LEADER_LEASE_TIME
                    print "SET LEASE", self.leaderLease
		    del self.acced[ELECTION_ID]
		elif (msg.key == ADD_ID):
		   pass
		elif (msg.key == REMOVE_ID):
		   pass
		elif (msg.key == SPLIT_ID):
		   pass
		elif (msg.key == MERGE_ID):
		   pass
		else:
		   del self.acced[msg.key]
		   #ADD KEY VALUES TO NODE.VALUES
		   pass
		    
        else:
            print "This is not a type of message an Acceptor should be receiving"
      else:
	print "YOU ARE NOT LEADER"
	new_msg = Message(msg.value, msg.key, "REDIRECT", ('P', self.leader), msg.src, msg.n, None)
	queue_message(N, new_msg)

