from __future__ import division
import math
proposal_id = 1

class EqualityMixin(object):
    def __eq__(self, other):
        for key, value in self.__dict__.items():
            if other.__dict__[key] != value:
                return False
        return True

class Message(EqualityMixin):
    def __init__(self, value, typ, src, dst, n, prior_proposal):
        self.value = value 
        self.typ = typ #string PROPOSE, PREPARE, PROMISE, ACCEPT, ACCEPTED, REJECTED
        self.src = src #tuple (P or A, ID)
        self.dst = dst #tuple (P or A, ID)
        self.n = n #proposal_id
        self.prior_proposal = prior_proposal #the highest numbered prior proposal (val,n) or None

    def __repr__(self):
        FMT = "Message(value={}, typ={}, src={}, dst={}, n={}, prior_proposal={})"
        
        return FMT.format(self.value, self.typ, self.src, self.dst, 
                          self.n, self.prior_proposal)
    def print_msg(self):
        ret = ""
        if self.typ == "PROPOSE":
            ret += "    -> P%d  PROPOSE v=%d" %(self.dst[1], self.value)
        elif self.typ == "PREPARE":
            ret += " P%d -> A%d  PREPARE n=%d" %(self.src[1], self.dst[1], self.n)
        elif self.typ == "PROMISE":
            if self.prior_proposal != None:
                prop_s = "n={}, v={}".format(self.prior_proposal[1], self.prior_proposal[0])
            else:
                prop_s = self.prior_proposal
            ret += " A%d -> P%d  PROMISE n=%d (Prior: %s)" %(self.src[1], self.dst[1], self.n, prop_s)
        elif self.typ == "ACCEPT":
            ret += " P%d -> A%d  ACCEPT n=%d v=%d" %(self.src[1], self.dst[1], self.n, self.value)
        elif self.typ == "ACCEPTED":
            ret += " A%d -> P%d  ACCEPTED n=%d v=%d" %(self.src[1], self.dst[1], self.n, self.value)
        elif self.typ == "REJECTED":
            ret += " A%d -> P%d  REJECTED n=%d" %(self.src[1], self.dst[1], self.n)    
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
   
    def deliver_message(self, N, msg):
        global proposal_id
        if msg.typ == "PROPOSE":
            if proposal_id not in self.proposals:
                self.proposals[proposal_id] = msg.value
            for c_a in self.accs:
                new_msg = Message(msg.value, "PREPARE", ('P',self.ID), ('A',c_a.ID), proposal_id, None)
                queue_message(N, new_msg)
            self.promises[proposal_id] = []
            proposal_id += 1 
        
        elif msg.typ == "PROMISE":
            if msg.n not in self.promises:
                self.promises[msg.n] = []
            if (msg.prior_proposal): 
                self.promises[msg.n].append(msg.prior_proposal)
            else:
                self.promises[msg.n].append((msg.value, msg.n))
            
            if (len(self.promises[msg.n]) == self.majority):
                pick_tup = sorted(self.promises[msg.n], key=lambda x: x[1])[0]
               
                for c_a in self.accs:
                    new_msg = Message(pick_tup[0], "ACCEPT", ('P',self.ID), ('A',c_a.ID), msg.n, None)
                    queue_message(N, new_msg)
        
        elif msg.typ == "REJECTED":
            if msg.n in self.rejects:
                self.rejects[msg.n].append((msg.value, msg.n))
            else:
                self.rejects[msg.n] = [(msg.value, msg.n)]
            if (len(self.rejects[msg.n]) == self.majority):
                if proposal_id not in self.proposals:
                    self.proposals[proposal_id] = msg.value
                for c_a in self.accs:
                    new_msg = Message(msg.value, "PREPARE", ('P',self.ID), ('A',c_a.ID),  proposal_id, None)
                    queue_message(N, new_msg)
                self.promises[proposal_id] = []
                proposal_id += 1
        
        elif msg.typ == "ACCEPTED":
            if msg.n in self.accepts:
                self.accepts[msg.n].append((msg.value, msg.n))
            else:
                self.accepts[msg.n] = [(msg.value, msg.n)]
            if (len(self.accepts[msg.n]) == self.majority):
                if msg.n not in self.props_accepted:
                    self.props_accepted[msg.n] = (self.proposals[msg.n] , msg.value)
        else:
            print "This is not a type of message a Proposer should be receiving"
            

class Acceptor(object):
    def __init__(self, ID):
        self.ID = ID
        self.failed = False
        self.n_int = 0 #the highest prepare request it has responded to
        self.accs = [] #list of tuples values accepted (value, n) 

    def deliver_message(self, N, msg):
        if msg.typ == "PREPARE":
            if msg.n >= self.n_int:
                if len(self.accs): 
                    high_p = sorted(self.accs, key=lambda x: x[1])[-1]
                    self.n_int = high_p[1]
                else:
                    high_p = None
                    self.n_int = msg.n
                new_msg = Message(msg.value, "PROMISE", ('A',self.ID), msg.src, msg.n, high_p)
                queue_message(N, new_msg)

        elif msg.typ == "ACCEPT":
            
            if self.n_int <= msg.n:
                new_msg = Message(msg.value, "ACCEPTED", ('A',self.ID), msg.src, msg.n, None)
                self.accs.append((msg.value, msg.n)) 
            else:
                new_msg = Message(msg.value, "REJECTED", ('A',self.ID), msg.src, msg.n, None)
            queue_message(N, new_msg)
        else:
            print "This is not a type of message an Acceptor should be receiving"

